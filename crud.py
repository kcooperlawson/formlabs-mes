



import os
import uuid
import subprocess
from datetime import datetime, date, timedelta
import secrets
import pandas as pd
import bcrypt
from sqlalchemy import desc, text, func, or_

from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion, UserSession)
from app_logger import logger

# --- DIRECTORY SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cleanliness")
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# --- BASELINE DATA ---
MASTER_FORMLABS_CATALOG = (
    ("V2", "RS-C2-GPCL-05", "FLGPCL05", "24", "Standard Clear V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
    ("V2", "RS-C2-GPBK-05", "FLGPBK05", "24", "Standard Black V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
)

# Set True by init_db() after its first successful run in this process — see
# the guard inside init_db() for why repeat calls need to be a no-op.
_schema_ready = False

def init_db():
    """Brings the database schema up to date via Alembic.

    Replaces the old pattern of Base.metadata.create_all() plus a
    hand-maintained, ever-growing list of raw ALTER TABLE strings wrapped in
    a silent try/except (which couldn't tell "column already exists" from a
    real failure). Schema changes now live as versioned files in
    migrations/versions/ — see migrations/versions/0001_baseline_schema.py
    for the full history up to the point Alembic was introduced.

    Handles the one-time transition automatically, so this still self-heals
    on every boot the way the old init_db() did:
      - Brand-new, empty database: runs every migration from scratch.
      - Existing database that already has the app's tables (built by the
        pre-Alembic init_db()) but was never stamped with a migration
        version: gets stamped at the baseline instead of re-running
        CREATE TABLE against tables that already exist. This assumes the
        existing schema is fully caught up with the old ALTER TABLE list —
        true for any database this app has been booted against, since that
        list ran on every prior boot.
      - Already stamped (normal case after the first boot on this version):
        just applies any migrations added since.

    Idempotent within a process: unlike the old raw-SQL version, Alembic's
    command.upgrade()/command.stamp() aren't designed to be re-entered
    multiple times in one running process (its internal EnvironmentContext
    teardown breaks the second time around — surfaces as a stray
    `KeyError: 'script'`). Streamlit re-executes Home.py's script on every
    rerun, and this function is called both from crud.py's own module-level
    bootstrap and explicitly from Home.py, so without this guard the real
    Alembic call could fire many times over a single session. The guard
    below makes every call after the first a no-op.
    """
    global _schema_ready
    if _schema_ready:
        return

    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect

    alembic_cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BASE_DIR, "migrations"))

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "alembic_version" not in existing_tables and "users" in existing_tables:
        command.stamp(alembic_cfg, "0001_baseline")
    else:
        command.upgrade(alembic_cfg, "head")

    _schema_ready = True


# --- FOREIGN KEY RESOLUTION HELPERS ---
# The tables above still carry the original free-text name columns
# (operator_name, pump_station, resin_type, ...) so nothing that reads
# them breaks. These helpers resolve a name to its matching row's id at
# write time, so new records get a real FK alongside the legacy string.
# A name with no match (e.g. the "System Auto-Reconciliation" pseudo-operator
# used for adjustment entries) simply resolves to None — that's expected,
# not an error, since not every name string corresponds to a real row.
def _resolve_user_id(session, full_name: str):
    if not full_name:
        return None
    name = str(full_name).strip().lower()
    user = session.query(User).filter(func.lower(User.full_name) == name).first()
    return user.id if user else None


def _resolve_pump_id(session, station_name: str):
    if not station_name:
        return None
    name = str(station_name).strip().lower()
    pump = session.query(PumpStation).filter(func.lower(PumpStation.station_name) == name).first()
    return pump.id if pump else None


def _resolve_resin_id(session, resin_name: str):
    if not resin_name:
        return None
    name = str(resin_name).strip().lower()
    resin = session.query(ResinSpec).filter(func.lower(ResinSpec.resin_name) == name).first()
    return resin.id if resin else None


def backfill_foreign_keys():
    """One-time (but safe-to-rerun) pass that fills in the new *_id FK columns
    on rows that predate them, by matching the legacy name strings. Only
    touches rows where the FK is still NULL, so after the first run it's a
    cheap no-op scan. Call this after seed_initial_data() so the pump/resin/
    user reference rows it matches against already exist."""
    session = ScopedSession()
    try:
        user_map = {u.full_name.strip().lower(): u.id for u in session.query(User).all()}
        pump_map = {p.station_name.strip().lower(): p.id for p in session.query(PumpStation).all()}
        resin_map = {r.resin_name.strip().lower(): r.id for r in session.query(ResinSpec).all()}

        def uid(name): return user_map.get(str(name or "").strip().lower())
        def pid(name): return pump_map.get(str(name or "").strip().lower())
        def rid(name): return resin_map.get(str(name or "").strip().lower())

        for log in session.query(ProductionLog).filter(or_(
                ProductionLog.operator_id.is_(None), ProductionLog.pump_station_id.is_(None),
                ProductionLog.resin_spec_id.is_(None))).all():
            if log.operator_id is None: log.operator_id = uid(log.operator_name)
            if log.pump_station_id is None: log.pump_station_id = pid(log.pump_station)
            if log.resin_spec_id is None: log.resin_spec_id = rid(log.resin_type)

        for log in session.query(DowntimeLog).filter(or_(
                DowntimeLog.operator_id.is_(None), DowntimeLog.pump_station_id.is_(None))).all():
            if log.operator_id is None: log.operator_id = uid(log.operator_name)
            if log.pump_station_id is None: log.pump_station_id = pid(log.pump_station)

        for run in session.query(AssignedRun).filter(or_(
                AssignedRun.resin_spec_id.is_(None), AssignedRun.operator_id.is_(None),
                AssignedRun.pump_station_id.is_(None))).all():
            if run.resin_spec_id is None: run.resin_spec_id = rid(run.resin_type)
            if run.operator_id is None: run.operator_id = uid(run.assigned_operator)
            if run.pump_station_id is None: run.pump_station_id = pid(run.pump_station)

        for chk in session.query(DailyChecklist).filter(DailyChecklist.operator_id.is_(None)).all():
            chk.operator_id = uid(chk.operator_name)

        for aud in session.query(CleanlinessAudit).filter(or_(
                CleanlinessAudit.operator_id.is_(None), CleanlinessAudit.pump_station_id.is_(None),
                CleanlinessAudit.resin_spec_id.is_(None))).all():
            if aud.operator_id is None: aud.operator_id = uid(aud.operator_name)
            if aud.pump_station_id is None: aud.pump_station_id = pid(aud.pump_station)
            if aud.resin_spec_id is None: aud.resin_spec_id = rid(aud.resin_type)

        for msg in session.query(FloorMessage).filter(or_(
                FloorMessage.operator_id.is_(None), FloorMessage.sender_id.is_(None))).all():
            if msg.operator_id is None: msg.operator_id = uid(msg.operator_name)
            if msg.sender_id is None: msg.sender_id = uid(msg.sender_name)

        for reactor in session.query(Reactor).filter(or_(
                Reactor.current_resin_id.is_(None), Reactor.assigned_pump_id.is_(None))).all():
            if reactor.current_resin_id is None and reactor.current_resin:
                reactor.current_resin_id = rid(reactor.current_resin)
            if reactor.assigned_pump_id is None and reactor.assigned_pump:
                reactor.assigned_pump_id = pid(reactor.assigned_pump)

        session.commit()
    except Exception:
        session.rollback()
        logger.exception("backfill_foreign_keys() failed; FK columns may be incomplete until the next boot")
    finally:
        session.close()


def seed_initial_data():
    session = ScopedSession()
    try:
        if session.query(User).count() == 0:
            # Generate properly salted bcrypt hashes for the default accounts
            op_pin = bcrypt.hashpw("1234".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            admin_pin = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            users = [
                User(username="operator", pin=op_pin, full_name="Demo Operator", role="operator"),
                User(username="sasha", pin=op_pin, full_name="Sasha", role="operator"),
                User(username="manager", pin=admin_pin, full_name="Plant Lead", role="admin"),
                # Changed role to 'admin'
            ]
            session.add_all(users)

        if session.query(PumpStation).count() == 0:
            pumps = [
                PumpStation(station_name="New Pump #1", status="Active", notes="Automated Line 1"),
                PumpStation(station_name="New Pump #2", status="Active", notes="Automated Line 2"),
                PumpStation(station_name="Old Pump/Other", status="Active", notes="Manual / Backup"),
            ]
            session.add_all(pumps)

        if session.query(DowntimeReason).count() == 0:
            reasons = [
                DowntimeReason(reason_name="Break/Shift Change"),
                DowntimeReason(reason_name="Carts/Bins"),
                DowntimeReason(reason_name="Change-Over"),
                DowntimeReason(reason_name="Machine Maintenance / Pump Jam"),
                DowntimeReason(reason_name="Resin Spill"),
                DowntimeReason(reason_name="Scale Calibration / Tare"),
                DowntimeReason(reason_name="Waiting on Bulk Resin Tote")
            ]
            session.add_all(reasons)

        if session.query(ResinSpec).count() == 0:
            for (cart_type, sku_val, code_val, life_val, name_val, weight_val, min_w, max_w, range_val, mult_val,
                 color_val) in MASTER_FORMLABS_CATALOG:
                spec = ResinSpec(
                    cartridge_type=cart_type, sku=sku_val, resin_code=code_val, lifetime_months=life_val,
                    resin_name=name_val, actual_spec_g=float(weight_val), min_weight_g=float(min_w),
                    max_weight_g=float(max_w), acceptable_range=range_val, multiplier=float(mult_val),
                    color_tag=color_val
                )
                session.add(spec)

        if session.query(PlantSettings).count() == 0:
            session.add(PlantSettings())

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()





def calculate_logged_units_for_resin(resin_name: str, cartridge_type: str = "", pump_station: str = "",
                                     lot_number: str = "") -> int:
    session = ScopedSession()
    try:
        t_name = str(resin_name or "").strip().lower()
        t_pump = str(pump_station or "").strip().lower()
        t_cart = str(cartridge_type or "").strip().lower()
        t_lot = str(lot_number or "").strip().lower()

        # CRITICAL FIX: The tank must look for BOTH log types to calculate the level
        all_logs = session.query(ProductionLog).filter(
            ProductionLog.log_type.in_(["Hourly Bottle Count", "System Calibration"])
        ).all()

        total_poured = 0
        for log in all_logs:
            l_resin = str(log.resin_type or "").strip().lower()
            l_pump = str(log.pump_station or "").strip().lower()
            l_cart = str(log.cartridge_type or "").strip().lower()
            l_lot = str(log.lot_number or "").strip().lower()

            if t_name and t_name != l_resin: continue
            if t_pump and t_pump != l_pump: continue
            if t_cart and (t_cart not in l_cart and l_cart not in t_cart): continue
            if t_lot and t_lot not in ["n/a", "", "none"] and l_lot and l_lot not in ["n/a", "", "none"]:
                if t_lot != l_lot: continue

            total_poured += int(log.bottles_filled or 0)
        return total_poured
    finally:
        session.close()


def get_assigned_runs_df(auto_sync: bool = True) -> pd.DataFrame:
    session = ScopedSession()
    try:
        query = session.query(AssignedRun).order_by(desc(AssignedRun.created_at))
        df = pd.read_sql(query.statement, session.bind)

        if not df.empty and auto_sync:
            for idx, row in df.iterrows():
                actual_units = calculate_logged_units_for_resin(
                    str(row.get("resin_type", "")), str(row.get("cartridge_type", "")),
                    str(row.get("pump_station", "")), str(row.get("lot_number", ""))
                )
                df.at[idx, "current_units"] = int(actual_units)

                run_id = int(row["id"])
                db_run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
                if db_run:
                    db_run.current_units = int(actual_units)
                    if db_run.current_units >= db_run.target_units and db_run.target_units > 0:
                        db_run.status = "Done"
                        df.at[idx, "status"] = "Done"
            session.commit()
        return df
    finally:
        session.close()


def sync_all_runs_with_logs():
    session = ScopedSession()
    try:
        runs = session.query(AssignedRun).all()
        for r in runs:
            actual_logged = calculate_logged_units_for_resin(r.resin_type, r.cartridge_type, r.pump_station,
                                                             r.lot_number)
            r.current_units = int(actual_logged)
            if r.current_units >= r.target_units and r.target_units > 0:
                r.status = "Done"
        session.commit()
    finally:
        session.close()


def update_run_status(run_id: int, new_status: str):
    session = ScopedSession()
    try:
        run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
        if run:
            run.status = new_status
            session.commit()
    finally:
        session.close()


def delete_assigned_run(run_id: int) -> bool:
    session = ScopedSession()
    try:
        run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
        if run:
            session.delete(run)
            session.commit()
            return True
        return False
    finally:
        session.close()


def update_assigned_run_progress(run_id: int, delta_units: int):
    session = ScopedSession()
    try:
        run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
        if run:
            run.current_units = max(0, run.current_units + delta_units)
            if run.current_units >= run.target_units and run.target_units > 0:
                run.status = "Done"
            session.commit()
    finally:
        session.close()


def create_assigned_run(
        reactor_id: str, reactor_size_l: int, resin_type: str, cartridge_type: str,
        target_units: int, assigned_operator: str, pump_station: str, lot_number: str,
        notes: str, status: str = "Active", run_type: str = "Pouring"
) -> int:
    session = ScopedSession()
    try:
        auto_detected = calculate_logged_units_for_resin(resin_type, cartridge_type, pump_station, lot_number)
        new_status = "Done" if (auto_detected >= target_units and target_units > 0) else status

        new_run = AssignedRun(
            reactor_id=reactor_id, reactor_size_l=reactor_size_l, resin_type=resin_type, cartridge_type=cartridge_type,
            target_units=target_units, current_units=auto_detected, assigned_operator=assigned_operator,
            pump_station=pump_station, status=new_status, lot_number=lot_number, notes=notes, run_type=run_type,
            resin_spec_id=_resolve_resin_id(session, resin_type),
            operator_id=_resolve_user_id(session, assigned_operator),
            pump_station_id=_resolve_pump_id(session, pump_station),
        )
        session.add(new_run)

        if run_type == "Pouring" and new_status != "Done" and reactor_id != "Floor WIP":
            reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_id).first()
            if reactor:
                reactor.current_resin = resin_type
                reactor.assigned_pump = pump_station
                reactor.current_resin_id = _resolve_resin_id(session, resin_type)
                reactor.assigned_pump_id = _resolve_pump_id(session, pump_station)

        session.commit()
        return auto_detected
    finally:
        session.close()


def complete_run_with_custom_total(run_id: int, final_units: int):
    session = ScopedSession()
    try:
        run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
        if run:
            run.current_units = int(final_units)
            run.status = "Done"
            if run.run_type == "Pouring" and run.reactor_id != "Floor WIP":
                reactor = session.query(Reactor).filter(Reactor.reactor_name == run.reactor_id).first()
                if reactor and reactor.current_resin == run.resin_type:
                    reactor.current_resin = None
                    reactor.assigned_pump = None
                    reactor.current_resin_id = None
                    reactor.assigned_pump_id = None
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_all_resin_specs_df(cartridge_filter: str = "ALL") -> pd.DataFrame:
    session = ScopedSession()
    try:
        query = session.query(ResinSpec)
        if cartridge_filter != "ALL":
            query = query.filter(ResinSpec.cartridge_type.contains(cartridge_filter))
        query = query.order_by(ResinSpec.cartridge_type, ResinSpec.resin_name)
        return pd.read_sql(query.statement, session.bind)
    finally:
        session.close()


def bulk_update_resin_specs(df_updated: pd.DataFrame):
    session = ScopedSession()
    try:
        for _, row in df_updated.iterrows():
            spec = session.query(ResinSpec).filter(ResinSpec.id == int(row["id"])).first()
            if spec:
                spec.sku = str(row.get("sku", spec.sku))
                spec.resin_code = str(row.get("resin_code", spec.resin_code))
                spec.resin_name = str(row.get("resin_name", spec.resin_name))
                spec.actual_spec_g = float(row.get("actual_spec_g", spec.actual_spec_g))
                spec.min_weight_g = float(row.get("min_weight_g", spec.min_weight_g))
                spec.max_weight_g = float(row.get("max_weight_g", spec.max_weight_g))
                spec.acceptable_range = f"{int(spec.min_weight_g)}-{int(spec.max_weight_g)}"
                spec.multiplier = float(row.get("multiplier", spec.multiplier))
                spec.lifetime_months = str(row.get("lifetime_months", spec.lifetime_months))
        session.commit()
    finally:
        session.close()


def update_pump_status(pump_id: int, new_status: str, notes: str = None) -> bool:
    session = ScopedSession()
    try:
        pump = session.query(PumpStation).filter(PumpStation.id == pump_id).first()
        if pump:
            pump.status = new_status
            if notes is not None: pump.notes = notes
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_active_pumps() -> list:
    session = ScopedSession()
    try:
        pumps = session.query(PumpStation.station_name).filter(PumpStation.status == "Active").all()
        return [row[0] for row in pumps] if pumps else ["New Pump #1"]
    finally:
        session.close()


def get_all_pumps_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        query = session.query(PumpStation).order_by(PumpStation.station_name)
        return pd.read_sql(query.statement, session.bind)
    finally:
        session.close()


def add_pump_station(station_name: str, notes: str = ""):
    session = ScopedSession()
    try:
        if not session.query(PumpStation).filter(PumpStation.station_name == station_name.strip()).first():
            session.add(PumpStation(station_name=station_name.strip(), status="Active", notes=notes))
            session.commit()
    finally:
        session.close()


def delete_pump_station(pump_id: int):
    session = ScopedSession()
    try:
        pump = session.query(PumpStation).filter(PumpStation.id == pump_id).first()
        if pump:
            session.delete(pump)
            session.commit()
    finally:
        session.close()


def get_downtime_reasons() -> list:
    session = ScopedSession()
    try:
        reasons = session.query(DowntimeReason.reason_name).all()
        return [row[0] for row in reasons] if reasons else ["Break"]
    finally:
        session.close()


def add_downtime_reason(reason_name: str):
    session = ScopedSession()
    try:
        if not session.query(DowntimeReason).filter(DowntimeReason.reason_name == reason_name.strip()).first():
            session.add(DowntimeReason(reason_name=reason_name.strip()))
            session.commit()
    finally:
        session.close()


def delete_downtime_reason(reason_id: int):
    session = ScopedSession()
    try:
        r = session.query(DowntimeReason).filter(DowntimeReason.id == reason_id).first()
        if r:
            session.delete(r)
            session.commit()
    finally:
        session.close()


def get_all_reactors_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        query = session.query(Reactor).order_by(Reactor.reactor_name)
        return pd.read_sql(query.statement, session.bind)
    finally:
        session.close()


def add_reactor(reactor_name: str, max_capacity_l: int):
    session = ScopedSession()
    try:
        if not session.query(Reactor).filter(Reactor.reactor_name == reactor_name.strip()).first():
            session.add(Reactor(reactor_name=reactor_name.strip(), max_capacity_l=max_capacity_l))
            session.commit()
    finally:
        session.close()


def delete_reactor(reactor_id: int):
    session = ScopedSession()
    try:
        r = session.query(Reactor).filter(Reactor.id == reactor_id).first()
        if r:
            session.delete(r)
            session.commit()
    finally:
        session.close()


def update_reactor_config(reactor_id: int, resin: str, pump: str):
    session = ScopedSession()
    try:
        r = session.query(Reactor).filter(Reactor.id == reactor_id).first()
        if r:
            r.current_resin = resin if resin != "None" else None
            r.assigned_pump = pump if pump != "None" else None
            session.commit()
    finally:
        session.close()


# --- LOGIN LOCKOUT SETTINGS ---
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def authenticate_user(username: str, pin: str) -> tuple[dict | None, str | None]:
    """Verifies credentials with a per-user lockout after repeated failures.

    Returns (user_dict, None) on success, or (None, error_message) on failure.
    The error message distinguishes "locked out" from "wrong credentials" so
    the UI can tell the operator how long to wait, without ever revealing
    whether the failure was a bad username or a bad PIN.
    """
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.username == username.lower().strip()).first()

        # Unknown username: don't leak whether the account exists.
        if not user:
            return None, "Invalid credentials."

        now = datetime.utcnow()

        # Already locked out? Tell them how much longer to wait.
        if user.locked_until and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() // 60) + 1
            return None, f"Account locked. Try again in {remaining} minute(s)."

        # Lock has expired naturally — clear it before checking the PIN.
        if user.locked_until and user.locked_until <= now:
            user.locked_until = None
            user.failed_login_attempts = 0

        try:
            pin_valid = bcrypt.checkpw(pin.strip().encode('utf-8'), user.pin.encode('utf-8'))
        except (ValueError, TypeError):
            # user.pin isn't a valid bcrypt hash — almost certainly a legacy
            # account whose PIN was never touched since before the bcrypt
            # migration (it's structurally impossible to convert an old
            # SHA-256 digest into a bcrypt hash without the original
            # plaintext PIN, so this can only be fixed with a manual reset).
            # No PIN will ever verify here, so don't count it against the
            # lockout threshold — that would just lock the account for a
            # problem retrying can't solve.
            session.commit()
            logger.error(
                f"authenticate_user(): user '{user.username}' has a malformed/legacy PIN hash "
                f"(pre-bcrypt) — needs an IT admin PIN reset, not a retry"
            )
            return None, "This account's PIN needs to be reset by an IT administrator."

        if pin_valid:
            # Success: reset the counter.
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()
            return {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "shift": user.shift,
                "preferred_theme": getattr(user, 'preferred_theme', "Default Dark"),
                "avatar_filename": user.avatar_filename,
            }, None

        # Wrong PIN: increment and lock if this tips over the threshold.
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            session.commit()
            return None, f"Too many failed attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."

        session.commit()
        remaining_tries = MAX_FAILED_LOGIN_ATTEMPTS - user.failed_login_attempts
        return None, f"Invalid credentials. {remaining_tries} attempt(s) remaining before lockout."
    finally:
        session.close()


def create_user(username: str, email: str, pin: str, full_name: str, role: str, target_lph: float = 400.0,
                shift: str = "Shift 1", theme: str = "Default Dark") -> bool:
    session = ScopedSession()
    try:
        if session.query(User).filter(
                (User.username == username.lower().strip()) | (User.email == email.lower().strip())).first():
            return False

        # Hash the PIN using bcrypt
        hashed_pin = bcrypt.hashpw(pin.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        session.add(User(
            username=username.lower().strip(),
            email=email.lower().strip(),
            pin=hashed_pin,
            full_name=full_name.strip(),
            role=role.lower().strip(),
            target_lph=target_lph,
            shift=shift,
            preferred_theme=theme
        ))
        session.commit()
        return True
    finally:
        session.close()


def update_user_target(user_id: int, target_lph: float):
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.target_lph = target_lph
            session.commit()
    finally:
        session.close()


def update_user_pin(user_id: int, new_pin: str) -> bool:
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            # Hash the new PIN using bcrypt before saving
            user.pin = bcrypt.hashpw(new_pin.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            # A PIN reset (e.g. by an IT admin) also clears any active lockout.
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()
            return True
        return False
    finally:
        session.close()


def update_user_theme(user_id: int, new_theme: str):
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.preferred_theme = new_theme
            session.commit()
    finally:
        session.close()


def unlock_user_account(user_id: int) -> bool:
    """Manually clears a lockout without touching the user's PIN — for IT admins
    who just need to let someone back in before the timer expires."""
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_all_users_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        return pd.read_sql(session.query(User).order_by(User.role, User.full_name).statement, session.bind)
    finally:
        session.close()


def get_active_operators() -> list:
    session = ScopedSession()
    try:
        ops = session.query(User.full_name).filter(User.role == "operator").all()
        return [row[0] for row in ops] if ops else ["No Operators Found"]
    finally:
        session.close()


def delete_user(user_id: int) -> bool:
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            session.delete(user)
            session.commit()
            return True
        return False
    finally:
        session.close()


def reconcile_reactor_level(reactor_name: str, visual_fill_pct: float, operator_name: str, notes: str = "") -> bool:
    session = ScopedSession()
    try:
        reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_name).first()
        if not reactor or not reactor.current_resin: return False
        capacity = float(reactor.max_capacity_l)
        vol_mult = 1.0
        active_run = session.query(AssignedRun).filter(AssignedRun.reactor_id == reactor_name,
                                                       AssignedRun.status.in_(["Active", "Pouring"])).first()
        if active_run and "RPS" in str(active_run.cartridge_type).upper(): vol_mult = 5.0

        target_units_poured = int(max(0.0, capacity - (capacity * (visual_fill_pct / 100.0))) / vol_mult)
        current_logged = calculate_logged_units_for_resin(resin_name=reactor.current_resin,
                                                          pump_station=reactor.assigned_pump or "")

        session.add(ProductionLog(
            log_type="Hourly Bottle Count", operator_name=operator_name,
            pump_station=reactor.assigned_pump or "Visual Check",
            shift="Shift 1", cartridge_type="V2" if vol_mult == 1.0 else "RPS", resin_type=reactor.current_resin,
            lot_number=(active_run.lot_number if active_run else "RECON-ADJ"),
            bottles_filled=target_units_poured - current_logged,
            notes=f"👀 VISUAL LEVEL CALIBRATION: Set to {visual_fill_pct}%. {notes}".strip(),
            operator_id=_resolve_user_id(session, operator_name),
            pump_station_id=_resolve_pump_id(session, reactor.assigned_pump or ""),
            resin_spec_id=_resolve_resin_id(session, reactor.current_resin),
        ))
        if active_run: active_run.current_units = target_units_poured
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def add_hourly_log(
        operator_name: str, pump_station: str, shift: str, cartridge_type: str,
        resin_type: str, lot_number: str, bottles: int, scrap_empty: int,
        scrap_filled: int, notes: str = "", log_type: str = "Hourly Bottle Count"
):
    session = ScopedSession()
    try:
        session.add(ProductionLog(
            log_type=log_type, operator_name=operator_name, pump_station=pump_station, shift=shift,
            cartridge_type=cartridge_type, resin_type=resin_type, lot_number=lot_number, bottles_filled=bottles,
            scrap_empty=scrap_empty, scrap_filled=scrap_filled, notes=notes,
            operator_id=_resolve_user_id(session, operator_name),
            pump_station_id=_resolve_pump_id(session, pump_station),
            resin_spec_id=_resolve_resin_id(session, resin_type),
        ))
        if log_type == "Hourly Bottle Count":
            active_run = session.query(AssignedRun).filter(
                AssignedRun.pump_station == pump_station, AssignedRun.resin_type == resin_type,
                AssignedRun.cartridge_type == cartridge_type, AssignedRun.lot_number == lot_number,
                AssignedRun.status.in_(["Active", "Pouring"])
            ).first()
            if active_run:
                active_run.current_units += bottles
                if active_run.current_units >= active_run.target_units and active_run.target_units > 0:
                    active_run.status = "Done"
        session.commit()
    finally:
        session.close()


def add_downtime_log(operator_name: str, pump_station: str, shift: str, reason: str, duration_min: int,
                     notes: str = ""):
    session = ScopedSession()
    try:
        session.add(DowntimeLog(operator_name=operator_name, pump_station=pump_station, shift=shift, reason=reason,
                                duration_min=duration_min, notes=notes,
                                operator_id=_resolve_user_id(session, operator_name),
                                pump_station_id=_resolve_pump_id(session, pump_station)))
        session.commit()
    finally:
        session.close()


def add_cleanliness_audit(audit_type: str, operator_name: str, pump_station: str, shift: str, resin_type: str,
                          notes: str, is_spill: bool, uploaded_file=None) -> bool:
    session = ScopedSession()
    try:
        saved_filename = None
        if uploaded_file is not None:
            saved_filename = f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{uploaded_file.name.split('.')[-1] if hasattr(uploaded_file, 'name') else 'jpg'}"
            with open(os.path.join(UPLOAD_DIR, saved_filename), "wb") as f: f.write(uploaded_file.getbuffer())
        session.add(
            CleanlinessAudit(audit_type=audit_type, operator_name=operator_name, pump_station=pump_station, shift=shift,
                             resin_type=resin_type if resin_type else None, image_filename=saved_filename,
                             is_spill="Yes" if is_spill else "No", notes=notes,
                             operator_id=_resolve_user_id(session, operator_name),
                             pump_station_id=_resolve_pump_id(session, pump_station),
                             resin_spec_id=_resolve_resin_id(session, resin_type)))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_cleanliness_audits_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        return pd.read_sql(session.query(CleanlinessAudit).order_by(desc(CleanlinessAudit.timestamp)).statement,
                           session.bind)
    finally:
        session.close()


def get_production_logs_df(start_date=None, end_date=None, shift=None, pump=None, resin=None,
                           operator=None, operator_id=None) -> pd.DataFrame:
    session = ScopedSession()
    try:
        query = session.query(ProductionLog)

        # Apply database-level filtering ONLY if the UI asks for it
        if start_date:
            query = query.filter(ProductionLog.date >= start_date)
        if end_date:
            query = query.filter(ProductionLog.date <= end_date)
        if shift and shift != "All Shifts":
            query = query.filter(ProductionLog.shift == shift)
        if pump and pump != "All Pumps":
            query = query.filter(ProductionLog.pump_station == pump)
        if resin and resin != "All Resins":
            query = query.filter(ProductionLog.resin_type == resin)
        # operator_id (FK) takes priority when given: it catches every row tied
        # to that person regardless of what name string was logged at the time,
        # so a mid-history rename doesn't silently drop old rows from the filter.
        # Falls back to the exact-string match for names with no resolved user
        # (e.g. a deleted account, or a legacy typo that never matched anyone).
        if operator_id:
            query = query.filter(ProductionLog.operator_id == operator_id)
        elif operator and operator != "All Operators":
            query = query.filter(ProductionLog.operator_name == operator)

        return pd.read_sql(query.order_by(desc(ProductionLog.timestamp)).statement, session.bind)
    finally:
        session.close()


def get_downtime_logs_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        return pd.read_sql(session.query(DowntimeLog).order_by(desc(DowntimeLog.timestamp)).statement, session.bind)
    finally:
        session.close()


def delete_production_log(log_id: int) -> bool:
    session = ScopedSession()
    try:
        log = session.query(ProductionLog).filter(ProductionLog.id == log_id).first()
        if log:
            session.delete(log)
            session.commit()
            sync_all_runs_with_logs()
            return True
        return False
    finally:
        session.close()


def delete_downtime_log(log_id: int) -> bool:
    session = ScopedSession()
    try:
        log = session.query(DowntimeLog).filter(DowntimeLog.id == log_id).first()
        if log:
            session.delete(log)
            session.commit()
            return True
        return False
    finally:
        session.close()


def delete_cleanliness_audit(audit_id: int) -> bool:
    session = ScopedSession()
    try:
        audit = session.query(CleanlinessAudit).filter(CleanlinessAudit.id == audit_id).first()
        if audit:
            session.delete(audit)
            session.commit()
            return True
        return False
    finally:
        session.close()

def send_floor_message(operator_name: str, sender_name: str, message: str, is_manager: bool):
    session = ScopedSession()
    try:
        session.add(FloorMessage(operator_name=operator_name, sender_name=sender_name, message=message,
                                 is_manager_reply=1 if is_manager else 0,
                                 operator_id=_resolve_user_id(session, operator_name),
                                 sender_id=_resolve_user_id(session, sender_name)))
        session.commit()
    finally:
        session.close()


def get_chat_history_df(operator_name: str) -> pd.DataFrame:
    session = ScopedSession()
    try:
        # Outer-joined against the sender's current avatar (by sender_id, the
        # FK resolved at write time in send_floor_message) so the chat UI can
        # show the real sender's profile picture instead of a generic icon.
        # LEFT join so messages whose sender account was deleted, or logged
        # before the FK backfill, still render (just with no avatar).
        return pd.read_sql(
            session.query(FloorMessage, User.avatar_filename.label("sender_avatar"))
            .outerjoin(User, User.id == FloorMessage.sender_id)
            .filter(FloorMessage.operator_name == operator_name)
            .order_by(FloorMessage.timestamp).statement,
            session.bind)
    finally:
        session.close()


def get_operators_with_messages() -> list:
    session = ScopedSession()
    try:
        return [row[0] for row in session.query(FloorMessage.operator_name).distinct().all()]
    finally:
        session.close()


def reconcile_pouring_to_packing(lot_number: str, final_packed_qty: int) -> bool:
    """Balances messy pouring logs against the finalized packing count by adding a single system adjustment."""
    session = ScopedSession()
    try:
        # 1. Grab all pouring logs for this specific lot
        pour_logs = session.query(ProductionLog).filter(
            ProductionLog.log_type == "Hourly Bottle Count",
            ProductionLog.lot_number == lot_number
        ).all()

        if not pour_logs:
            return False

        # 2. Calculate the variance (Delta)
        total_poured = sum(log.bottles_filled for log in pour_logs)
        delta = final_packed_qty - total_poured

        if delta == 0:
            return True  # It already balances perfectly!

        # 3. Create ONE system log to balance the plant totals, leaving operator metrics alone
        adj_log = ProductionLog(
            log_type="Hourly Bottle Count",
            operator_name="System Auto-Reconciliation",
            pump_station="System Reconciliation",
            shift="System",
            cartridge_type=pour_logs[0].cartridge_type,
            resin_type=pour_logs[0].resin_type,
            lot_number=lot_number,
            bottles_filled=delta,  # Assign the entire delta to the System
            notes=f"🔄 AUTO-RECONCILIATION: Plant-wide adjustment of {delta} units to align with finalized packing skid count of {final_packed_qty}.",
            resin_spec_id=_resolve_resin_id(session, pour_logs[0].resin_type),
        )
        session.add(adj_log)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def reconcile_reactor_liters(reactor_name: str, actual_liters: float, operator_name: str, notes: str = "") -> bool:
    session = ScopedSession()
    try:
        reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_name).first()
        if not reactor or not reactor.current_resin: return False

        capacity = float(reactor.max_capacity_l)
        vol_mult = 1.0

        active_run = session.query(AssignedRun).filter(AssignedRun.reactor_id == reactor_name,
                                                       AssignedRun.status.in_(["Active", "Pouring"])).first()
        if active_run and "RPS" in str(active_run.cartridge_type).upper():
            vol_mult = 5.0

        # Calculate poured units directly from the exact liters remaining
        remaining_liters = max(0.0, min(capacity, actual_liters))
        target_units_poured = int(max(0.0, capacity - remaining_liters) / vol_mult)

        current_logged = calculate_logged_units_for_resin(resin_name=reactor.current_resin,
                                                          pump_station=reactor.assigned_pump or "")

        session.add(ProductionLog(
            log_type="System Calibration",
            operator_name=operator_name,
            pump_station=reactor.assigned_pump or "Visual Check",
            shift="Shift 1",
            cartridge_type="V2" if vol_mult == 1.0 else "RPS",
            resin_type=reactor.current_resin,
            lot_number=(active_run.lot_number if active_run else "RECON-ADJ"),
            bottles_filled=target_units_poured - current_logged,
            notes=f"👀 EXACT LITERS CALIBRATION: Set to {actual_liters}L remaining. {notes}".strip(),
            operator_id=_resolve_user_id(session, operator_name),
            pump_station_id=_resolve_pump_id(session, reactor.assigned_pump or ""),
            resin_spec_id=_resolve_resin_id(session, reactor.current_resin),
        ))

        if active_run:
            active_run.current_units = target_units_poured

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def has_completed_daily_checklist(operator_name: str, shift: str) -> bool:
    """Checks if the operator has completed the checklist for the current date and shift."""
    session = ScopedSession()
    try:
        today_d = date.today()
        record = session.query(DailyChecklist).filter(
            DailyChecklist.operator_name == operator_name,
            DailyChecklist.date == today_d,
            DailyChecklist.shift == shift
        ).first()
        return record is not None
    finally:
        session.close()


def submit_daily_checklist(operator_name: str, shift: str) -> bool:
    """Logs the checklist completion for the operator."""
    session = ScopedSession()
    try:
        today_d = date.today()
        # Prevent double-logging
        if session.query(DailyChecklist).filter_by(operator_name=operator_name, date=today_d, shift=shift).first():
            return True

        new_check = DailyChecklist(
            operator_name=operator_name,
            shift=shift,
            operator_id=_resolve_user_id(session, operator_name),
        )
        session.add(new_check)
        session.commit()
        return True
    finally:
        session.close()


def get_todays_checklists_df() -> pd.DataFrame:
    """Fetches all completed startup checklists for the current day."""
    session = ScopedSession()
    try:
        today_d = date.today()
        query = session.query(DailyChecklist).filter(DailyChecklist.date == today_d)
        return pd.read_sql(query.statement, session.bind)
    finally:
        session.close()


def update_user_role_and_shift(user_id: int, new_role: str, new_shift: str) -> bool:
    """Updates an operator's active role and shift in the database."""
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.role = new_role.lower()
            user.shift = new_shift
            session.commit()
            return True
        return False
    finally:
        session.close()


def delete_user_by_username(username: str) -> bool:
    """Permanently deletes a user from the system."""
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user:
            session.delete(user)
            session.commit()
            return True
        return False
    finally:
        session.close()


def add_resin_spec(cartridge_type: str, sku: str, resin_code: str, resin_name: str,
                   actual_spec_g: float, min_weight_g: float, max_weight_g: float,
                   lifetime_months: str = "24", multiplier: float = 1.0,
                   color_tag: str = "#EA580C", units_per_skid: int = 500) -> bool:
    """Inserts a new proprietary resin formulation directly into PostgreSQL."""
    session = ScopedSession()
    try:
        acceptable_range = f"{int(min_weight_g)}-{int(max_weight_g)}"
        spec = ResinSpec(
            cartridge_type=cartridge_type,
            sku=sku.strip(),
            resin_code=resin_code.strip(),
            resin_name=resin_name.strip(),
            actual_spec_g=actual_spec_g,
            min_weight_g=min_weight_g,
            max_weight_g=max_weight_g,
            acceptable_range=acceptable_range,
            lifetime_months=lifetime_months,
            multiplier=multiplier,
            color_tag=color_tag,
            units_per_skid=units_per_skid
        )
        session.add(spec)
        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception(f"add_resin_spec() failed for resin_name={resin_name!r}")
        return False
    finally:
        session.close()


def delete_resin_spec(spec_id: int) -> bool:
    """Permanently deletes a resin specification from PostgreSQL."""
    session = ScopedSession()
    try:
        spec = session.query(ResinSpec).filter(ResinSpec.id == spec_id).first()
        if spec:
            session.delete(spec)
            session.commit()
            return True
        return False
    finally:
        session.close()


def add_suggestion(user_name: str, user_role: str, category: str, suggestion: str) -> bool:
    session = ScopedSession()
    try:
        session.add(Suggestion(
            user_name=user_name,
            user_role=user_role,
            category=category,
            suggestion=suggestion.strip()
        ))
        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception(f"add_suggestion() failed for user_name={user_name!r}")
        return False
    finally:
        session.close()


def get_all_suggestions_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        # Suggestion only ever stored a free-text submitter name (no FK, this
        # inbox predates the FK-backfill work), so the avatar match here is
        # necessarily best-effort by current display name -- same fallback
        # approach already used for legacy string-only lookups elsewhere in
        # the app. A renamed account or a name that no longer matches any
        # user just renders with no avatar rather than the wrong one.
        return pd.read_sql(
            session.query(Suggestion, User.avatar_filename.label("avatar_filename"))
            .outerjoin(User, User.full_name == Suggestion.user_name)
            .order_by(desc(Suggestion.timestamp)).statement,
            session.bind)
    finally:
        session.close()


def update_suggestion_status(suggestion_id: int, new_status: str, admin_notes: str = "") -> bool:
    session = ScopedSession()
    try:
        s = session.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
        if s:
            s.status = new_status
            if admin_notes:
                s.admin_notes = admin_notes
            session.commit()
            return True
        return False
    finally:
        session.close()


def delete_suggestion(suggestion_id: int) -> bool:
    session = ScopedSession()
    try:
        s = session.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
        if s:
            session.delete(s)
            session.commit()
            return True
        return False
    finally:
        session.close()

def update_user_avatar(user_id: int, uploaded_file) -> str | None:
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user and uploaded_file is not None:
            filename = f"avatar_{user_id}_{uuid.uuid4().hex[:6]}.png"
            filepath = os.path.join(AVATAR_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
            user.avatar_filename = filename
            session.commit()
            return filename
        return None
    finally:
        session.close()


def update_user_credentials(user_id: int, new_username: str = None, new_pin: str = None, new_fullname: str = None) -> \
tuple[bool, str]:
    session = ScopedSession()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User account not found."

        if new_username and new_username.lower().strip() != user.username:
            clean_user = new_username.lower().strip()
            existing = session.query(User).filter(User.username == clean_user).first()
            if existing:
                return False, "Username is already taken."
            user.username = clean_user

        if new_fullname and new_fullname.strip():
            user.full_name = new_fullname.strip()

        # Re-hash PIN with bcrypt if updated
        if new_pin and new_pin.strip():
            user.pin = bcrypt.hashpw(new_pin.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        session.commit()
        return True, "Account credentials updated successfully!"
    except Exception as e:
        session.rollback()
        return False, f"Database Error: {str(e)}"
    finally:
        session.close()

def get_plant_settings() -> dict:
    session = ScopedSession()
    try:
        settings = session.query(PlantSettings).first()
        if settings:
            return {
                "target_lph": settings.target_lph,
                "packing_target_uph": getattr(settings, 'packing_target_uph', 500.0),
                "shift_1_start": settings.shift_1_start,
                "shift_1_hours": settings.shift_1_hours,
                "shift_2_start": settings.shift_2_start,
                "shift_2_hours": settings.shift_2_hours,
                "shift_3_start": getattr(settings, 'shift_3_start', "23:00"),
                "shift_3_hours": getattr(settings, 'shift_3_hours', 7.0),
                "yield_target_pct": settings.yield_target_pct,
                "packing_yield_target_pct": getattr(settings, 'packing_yield_target_pct', 99.5),
                "shift_1_break_mins": getattr(settings, 'shift_1_break_mins', 60.0),
                "shift_2_break_mins": getattr(settings, 'shift_2_break_mins', 60.0),
                "shift_3_break_mins": getattr(settings, 'shift_3_break_mins', 60.0),
                "handover_emails": getattr(settings, 'handover_emails', ""),
                "enable_packing": bool(getattr(settings, 'enable_packing', 1))
            }
        return {
            "target_lph": 400.0, "packing_target_uph": 500.0, "shift_1_start": "06:00", "shift_1_hours": 8.5,
            "shift_2_start": "14:30", "shift_2_hours": 8.5, "shift_3_start": "23:00", "shift_3_hours": 7.0,
            "yield_target_pct": 99.0, "packing_yield_target_pct": 99.5, "shift_1_break_mins": 60.0,
            "shift_2_break_mins": 60.0, "shift_3_break_mins": 60.0, "handover_emails": "", "enable_packing": True
        }
    finally:
        session.close()

def update_plant_settings(
    target_lph: float | int, packing_target_uph: float | int, s1_start: str, s1_hrs: float | int,
    s2_start: str, s2_hrs: float | int, s3_start: str, s3_hrs: float | int, yield_tgt: float | int,
    packing_yield_tgt: float | int, s1_break: float | int = 60.0, s2_break: float | int = 60.0,
    s3_break: float | int = 60.0, emails: str = "", enable_packing: int = 1
):
    session = ScopedSession()
    try:
        settings = session.query(PlantSettings).first()
        if settings:
            settings.target_lph = target_lph
            settings.packing_target_uph = packing_target_uph
            settings.shift_1_start = s1_start
            settings.shift_1_hours = s1_hrs
            settings.shift_2_start = s2_start
            settings.shift_2_hours = s2_hrs
            settings.shift_3_start = s3_start
            settings.shift_3_hours = s3_hrs
            settings.yield_target_pct = yield_tgt
            settings.packing_yield_target_pct = packing_yield_tgt
            settings.shift_1_break_mins = s1_break
            settings.shift_2_break_mins = s2_break
            settings.shift_3_break_mins = s3_break
            settings.handover_emails = emails
            settings.enable_packing = enable_packing
            session.commit()
    finally:
        session.close()

SESSION_LIFETIME_DAYS = 30

def create_session(user_id: int) -> str:
    """Issues a random, unguessable session token and stores it server-side."""
    session = ScopedSession()
    try:
        token = secrets.token_urlsafe(32)
        session.add(UserSession(
            token=token,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(days=SESSION_LIFETIME_DAYS)
        ))
        session.commit()
        return token
    finally:
        session.close()

def get_user_by_session_token(token: str) -> dict | None:
    """Validates a session token server-side and returns the user, or None."""
    if not token:
        return None
    session = ScopedSession()
    try:
        sess = session.query(UserSession).filter(UserSession.token == token).first()
        if not sess or sess.expires_at < datetime.utcnow():
            if sess:  # expired — clean it up
                session.delete(sess)
                session.commit()
            return None

        user = session.query(User).filter(User.id == sess.user_id).first()
        if not user:
            return None

        return {
            "id": user.id, "username": user.username, "full_name": user.full_name,
            "role": user.role, "shift": user.shift,
            "preferred_theme": getattr(user, "preferred_theme", "Default Dark"),
            "avatar_filename": user.avatar_filename,
        }
    finally:
        session.close()

def delete_session(token: str):
    """Revokes a single session token (used on logout)."""
    if not token:
        return
    session = ScopedSession()
    try:
        sess = session.query(UserSession).filter(UserSession.token == token).first()
        if sess:
            session.delete(sess)
            session.commit()
    finally:
        session.close()

init_db()
seed_initial_data()
backfill_foreign_keys()






