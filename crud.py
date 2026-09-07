



import os
import re
import uuid
import calendar
import subprocess
from datetime import datetime, date, timedelta
import secrets
import pandas as pd
import bcrypt
from sqlalchemy import desc, text, func, or_

import bulk_pour as _bulk
from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion, UserSession,
                    LotVerification)
from reactor_vessel import resolve_vessel_type
from app_logger import logger

# --- DIRECTORY SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cleanliness")
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
LOT_PHOTO_DIR = os.path.join(BASE_DIR, "uploads", "lot_labels")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(LOT_PHOTO_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# --- BASELINE DATA ---
MASTER_FORMLABS_CATALOG = (
    ("V2", "RS-C2-GPCL-05", "FLGPCL05", "24", "Standard Clear V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, None),
    ("V2", "RS-C2-GPBK-05", "FLGPBK05", "24", "Standard Black V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, None),
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

    Every one of those three paths ends at head. That was not true until it
    was tested: stamping used to be an `else` branch, so a pre-Alembic
    database got marked as being at the baseline and then ran the rest of that
    boot against a schema seven revisions behind the models. It died on the
    first settings query with "column plant_settings.shift_count does not
    exist" - and the way to reach it is to restore an older backup onto a new
    machine and start the app, which is exactly what somebody setting up a
    second PC does. Stamping says where the database already is; it is not a
    substitute for bringing it up to date.

    The stamp is written as a plain INSERT rather than through
    `command.stamp`, because Alembic's environment is not re-entrant within
    one process (see below) and this path has to run a real upgrade
    immediately afterwards.

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
        # A database the old pre-Alembic init_db() built: the tables are there
        # and are caught up with that era's ALTER TABLE list, so record where
        # it stands rather than re-running CREATE TABLE against tables that
        # already exist.
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
            conn.execute(text("INSERT INTO alembic_version (version_num) "
                              "VALUES ('0001_baseline')"))

    # Always, from whichever of the three starting points. An empty database
    # runs all of them; a just-stamped one runs everything after the baseline;
    # an up-to-date one does nothing.
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





# Litres in one container of each format. A production log counts containers
# and a reactor is measured in litres, so this is the only place the two meet.
# It was written out inline in six places, each deciding for itself what a jug
# holds; the reactor page then applied ONE of those multipliers to a total that
# had been summed across every format, so a tank drawn down by a mix of
# cartridges and jugs was scaled by whichever format happened to be on the
# work order.
CONTAINER_LITRES = {"RPS": 5.0, "PIGMENT": 0.124}
CARTRIDGE_LITRES = 1.0          # V1 and V2 are 1 L cartridges


def container_litres(cartridge_type) -> float:
    """Litres held by one container of this format."""
    fmt = str(cartridge_type or "").strip().upper()
    for key, litres in CONTAINER_LITRES.items():
        if key in fmt:
            return litres
    return CARTRIDGE_LITRES


def log_litres(bottles_filled, cartridge_type, litres_poured=None) -> float:
    """How many litres one log row represents.

    The single definition, used by the tank levels, the shift totals, the wall
    display and the exports. A measured amount wins outright when a row has
    one; everything else is the old count-times-format, unchanged. Everywhere
    that used to multiply inline now calls this, because a bulk pour counted
    by one screen and not another is two plausible-looking numbers and no way
    to tell which is wrong.
    """
    return _bulk.log_litres(bottles_filled, cartridge_type, litres_poured,
                            container_litres)


# Lot values that are not a real lot: the app's own placeholders and the
# marker the level calibrations write when there is no run to borrow one from.
_NON_LOTS = {"", "n/a", "none", "null", "recon-adj"}


def _is_real_lot(value) -> bool:
    v = str(value or "").strip().lower()
    return bool(v) and v not in _NON_LOTS and not is_placeholder_lot(value)


def reactor_draw_litres(resin_name: str, pump_station: str = "") -> tuple[float, str]:
    """Litres drawn from a tank since it was last filled, and the lot in it.

    A tank is refilled when a new lot starts coming out of it - and the
    operators already tell us when that happens, because the lot goes on every
    hourly log and the lot check makes them read it off the container. So the
    current batch is the newest lot logged at this pump, and everything logged
    since that lot started is what has been drawn from the tank.

    This used to be read off the work order instead. The run supplied the lot
    to scope by and the container format to size the units with, and neither
    has a substitute when a plant does not dispatch runs: with no lot the tank
    summed every log ever recorded for that resin and pump, so it drained to
    empty and stayed there, and with no format every unit was assumed to be a
    1 L cartridge, so a tank drawn down in 5 L jugs emptied five times too
    slowly. Deriving it from the lot costs a manager nothing and reads the same
    in either mode - a plant that does dispatch runs puts the same lot on the
    run and on the log, so the answer does not change.

    Returns (litres_drawn, current_lot). No logs means a full tank.
    """
    session = ScopedSession()
    try:
        t_name = str(resin_name or "").strip().lower()
        t_pump = str(pump_station or "").strip().lower()
        if not t_name:
            return 0.0, ""

        rows = session.query(ProductionLog).filter(
            ProductionLog.log_type.in_(["Hourly Bottle Count", "System Calibration"])
        ).order_by(ProductionLog.timestamp.asc(), ProductionLog.id.asc()).all()

        mine = [r for r in rows
                if str(r.resin_type or "").strip().lower() == t_name
                and (not t_pump or str(r.pump_station or "").strip().lower() == t_pump)]
        if not mine:
            return 0.0, ""

        current_lot = ""
        for row in reversed(mine):
            if _is_real_lot(row.lot_number):
                current_lot = str(row.lot_number).strip()
                break

        # Walk back from the newest log and stop at the first one carrying a
        # DIFFERENT real lot - that is the moment this batch started. Logs with
        # no real lot are kept: a level calibration writes no lot of its own
        # and belongs to whatever batch was running when somebody took it.
        batch = []
        for row in reversed(mine):
            if current_lot and _is_real_lot(row.lot_number) \
                    and str(row.lot_number).strip().lower() != current_lot.lower():
                break
            batch.append(row)

        drawn = sum(log_litres(r.bottles_filled, r.cartridge_type,
                               getattr(r, "litres_poured", None))
                    for r in batch)
        return float(drawn), current_lot
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


def update_assigned_run_progress(run_id: int, delta_units: int, operator_name: str = "Manual Adjustment"):
    """Adds delta_units to a run's progress AND writes a matching
    ProductionLog row (log_type="System Calibration", same resin/
    cartridge/pump/lot as the run) so this survives the very next page
    load. get_assigned_runs_df(auto_sync=True) recomputes current_units
    from scratch from logged production every time it's called (see
    calculate_logged_units_for_resin) — a bare `current_units +=` with no
    corresponding log row looked, to that recompute, like it never
    happened, and got silently reverted on the next rerun.
    """
    session = ScopedSession()
    try:
        run = session.query(AssignedRun).filter(AssignedRun.id == run_id).first()
        if run:
            run.current_units = max(0, run.current_units + delta_units)
            if run.current_units >= run.target_units and run.target_units > 0:
                run.status = "Done"
            if delta_units:
                session.add(ProductionLog(
                    log_type="System Calibration",
                    operator_name=operator_name,
                    pump_station=run.pump_station,
                    shift="System",
                    cartridge_type=run.cartridge_type,
                    resin_type=run.resin_type,
                    lot_number=run.lot_number,
                    bottles_filled=delta_units,
                    scrap_empty=0, scrap_filled=0,
                    notes=f"Manual +{delta_units} adjustment via Assigned Runs progress button.",
                    operator_id=_resolve_user_id(session, operator_name),
                    pump_station_id=run.pump_station_id,
                    resin_spec_id=run.resin_spec_id,
                ))
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
                # Only overwrite the colour when the caller actually sent one.
                # This function is fed a hand-built dict from more than one
                # screen, and a form that doesn't show the colour field must
                # not blank out a colour somebody chose on another screen.
                if "color_tag" in row and str(row.get("color_tag") or "").strip():
                    spec.color_tag = str(row["color_tag"]).strip()
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


def add_reactor(reactor_name: str, max_capacity_l: int, vessel_type: str = "",
                asset_tag: str = "", bay_marker: str = ""):
    """Register a physical vessel.

    The vessel type falls back to the capacity band rather than to nothing, so
    a tank added in a hurry still draws as something sensible and a manager
    only has to correct the ones that guessed wrong.
    """
    session = ScopedSession()
    try:
        if not session.query(Reactor).filter(Reactor.reactor_name == reactor_name.strip()).first():
            session.add(Reactor(
                reactor_name=reactor_name.strip(), max_capacity_l=max_capacity_l,
                vessel_type=resolve_vessel_type(vessel_type, max_capacity_l),
                asset_tag=str(asset_tag or "").strip() or None,
                bay_marker=str(bay_marker or "").strip().upper() or None))
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


def update_reactor_identity(reactor_id: int, vessel_type: str = None,
                            asset_tag: str = None, bay_marker: str = None) -> bool:
    """What a vessel is and what it is called out on the floor.

    Kept apart from update_reactor_config on purpose: that one changes what a
    vessel is doing this week, and this one changes what the vessel *is*. They
    are edited by different people at different times, and a save of one
    should never quietly overwrite the other.
    """
    session = ScopedSession()
    try:
        r = session.query(Reactor).filter(Reactor.id == reactor_id).first()
        if not r:
            return False
        if vessel_type is not None:
            r.vessel_type = resolve_vessel_type(vessel_type, r.max_capacity_l)
        if asset_tag is not None:
            r.asset_tag = str(asset_tag).strip()[:30] or None
        if bay_marker is not None:
            r.bay_marker = str(bay_marker).strip().upper()[:10] or None
        session.commit()
        return True
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


def _calibrate_reactor(reactor_name: str, remaining_l: float, operator_name: str,
                       note: str) -> bool:
    """Correct a tank to the level somebody has just read off its gauge.

    The level is derived, not stored: it is the capacity less what the logs say
    has come out since the tank was last filled (see reactor_draw_litres). So a
    calibration cannot set the level directly - it writes the difference into
    the record as one adjustment row, and the level follows from the record as
    it always does.

    The row is written in litres, as a 1 L format, because litres are what a
    gauge reads and what a tank holds. It carries no lot of its own: an
    adjustment is part of the batch it was taken during, not a new fill, and
    RECON-ADJ is the marker that says so.
    """
    session = ScopedSession()
    try:
        reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_name).first()
        if not reactor or not reactor.current_resin:
            return False

        capacity = float(reactor.max_capacity_l)
        pump = reactor.assigned_pump or ""
        remaining_l = max(0.0, min(capacity, float(remaining_l)))

        # Read the level before writing anything: reactor_draw_litres takes the
        # same thread-scoped session and closes it when it is done.
        drawn_now, _lot = reactor_draw_litres(reactor.current_resin, pump)
        adjustment_l = int(round((capacity - remaining_l) - drawn_now))

        session.add(ProductionLog(
            log_type="System Calibration",
            operator_name=operator_name,
            pump_station=pump or "Visual Check",
            shift="Shift 1",
            cartridge_type="V2",
            resin_type=reactor.current_resin,
            lot_number="RECON-ADJ",
            bottles_filled=adjustment_l,
            notes=note,
            operator_id=_resolve_user_id(session, operator_name),
            pump_station_id=_resolve_pump_id(session, pump),
            resin_spec_id=_resolve_resin_id(session, reactor.current_resin),
        ))

        # In execution mode a run is tracked in units of its own format, so it
        # is brought along in those units rather than in litres.
        active_run = session.query(AssignedRun).filter(
            AssignedRun.reactor_id == reactor_name,
            AssignedRun.status.in_(["Active", "Pouring"])).first()
        if active_run:
            per_unit = container_litres(active_run.cartridge_type)
            if per_unit > 0:
                active_run.current_units = int((capacity - remaining_l) / per_unit)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def reconcile_reactor_level(reactor_name: str, visual_fill_pct: float, operator_name: str, notes: str = "") -> bool:
    """Calibrate from a percentage read off the sight glass."""
    session = ScopedSession()
    try:
        reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_name).first()
        capacity = float(reactor.max_capacity_l) if reactor else 0.0
    finally:
        session.close()
    return _calibrate_reactor(
        reactor_name, capacity * (float(visual_fill_pct) / 100.0), operator_name,
        f"👀 VISUAL LEVEL CALIBRATION: Set to {visual_fill_pct}%. {notes}".strip())


# ============================================================================
# CARTRIDGE LOT VERIFICATION
# ----------------------------------------------------------------------------
# The lot printed on the bottom of a V1/V2/Pigment cartridge is stamped as
#   L-2411A0742
#   E-11/2026
# while the manager creating the run types the bare number into the run's
# lot field. Every comparison in this module therefore happens on a
# normalized form so an operator can type the stamp verbatim (prefix and
# all) and still match a run whose lot was entered bare.
#
# This applies to every container format. RPS jugs used to be excluded, on the
# understanding that they carried no label - they always have carried one, and
# the plant now requires the tag to be on the jug before pouring starts, which
# is what let the check be turned on for that format too.
# ============================================================================

# Lots the app invented for itself because no active run matched the
# station/resin/cartridge combination. There is nothing physical behind these,
# so a mismatch against one means nothing and must never be reported as one.
_PLACEHOLDER_LOT_RE = re.compile(r"^LOT-?\d{6,8}-?\d*$", re.IGNORECASE)

# Expiry within this many days still lets the pour happen but raises a flag.
EXPIRY_SOON_DAYS = 60


def normalize_lot(value) -> str:
    """Reduce a lot string to the form used for comparison.

    Uppercases, strips an `L-` / `E-` / `LOT-` stamp prefix (the colon form is
    accepted too, since the stamp has been seen printed both ways), and drops every
    character that isn't a letter or digit. That makes all of these equal:
        "L-2411A0742"  "l- 2411a0742"  "L:2411A0742"  "2411A0742"
    """
    s = str(value or "").strip().upper()
    s = re.sub(r"^(?:LOT|L|E)\s*[:#\-]?\s*", "", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def is_placeholder_lot(value) -> bool:
    """True when this lot is the app's own generated stand-in, not a real one."""
    s = str(value or "").strip()
    if not s or s.lower() in ("n/a", "none", "recon-adj"):
        return True
    return bool(_PLACEHOLDER_LOT_RE.match(s))


def lots_match(expected, entered) -> bool:
    """Compare a run's lot to what the operator read off the container."""
    e, t = normalize_lot(expected), normalize_lot(entered)
    return bool(e) and bool(t) and e == t


# Every container format the plant pours now carries a lot the operator can
# read, so the gate applies to all of them. RPS jugs were previously excluded
# because the jug itself was not being labelled at the station; the plant now
# requires the tag to be on before pouring, which is what made the check
# possible on that format.
GATED_FORMATS = ("V1", "V2", "Pigment", "RPS")

# What the operator picks, and what it is stored as. A table rather than a
# chain of substring tests, because the chain that used to do this read "Bulk"
# out of "RPS (5L Bulk Jug)" the moment a bulk option was added and silently
# turned every 5-litre jug into a measured pour. It was correct for years and
# wrong the day a new option shared a word with an old one, which is the whole
# argument for spelling the mapping out.
CONTAINER_FORMATS = {
    "V2 (1L Cartridge)": "V2",
    "V1 (1L Cartridge)": "V1",
    "RPS (5L Bulk Jug)": "RPS",
    "Pigment": "Pigment",
    "Drum / Tote (measured amount)": "Bulk",
}
BULK_FORMAT_LABEL = "Drum / Tote (measured amount)"


def format_choices(bulk_enabled: bool = False) -> tuple:
    """The Container Format options for this plant, in order.

    The measured-amount option is absent unless the plant has switched it on,
    so a floor that only ever fills cartridges and jugs sees exactly the four
    entries it has always seen.
    """
    labels = [k for k in CONTAINER_FORMATS if k != BULK_FORMAT_LABEL]
    if bulk_enabled:
        labels.append(BULK_FORMAT_LABEL)
    return tuple(labels)


def format_code(label) -> str:
    """The stored code for a Container Format label."""
    return CONTAINER_FORMATS.get(str(label or "").strip(), "V2")


def can_administer(role, simple_mode) -> bool:
    """Whether this role reaches the administration console.

    In logging mode there is no separate IT role. A plant that runs this as a
    record has one person in charge of it, and that person is the manager:
    resetting a PIN, adding a pump or taking a backup should not require a
    second account that a plant of this size does not have. Switching to
    execution mode restores the separation and the console goes back to
    administrators only.

    Both arguments are required rather than the mode being read in here, so
    that every caller is explicit about which plant's mode it is applying and
    the rule itself can be tested without a database. database.py carries the
    one-argument form for pages, which reads the mode from the cached
    settings.
    """
    r = str(role or "").strip().lower()
    if r == "admin":
        return True
    return bool(simple_mode) and r == "manager"


def container_words(cart_code) -> dict:
    """What to call the container in the operator's hands. Only the noun.

    Cartridges and jugs carry the same kind of lot label in the same place -
    on the bottom of the empty, applied before it is filled - so the check, the
    instruction and the action are identical and only the word for the thing
    changes. Two earlier versions of this got that wrong in opposite
    directions: one sent operators hunting for a tag on the side of a jug, the
    other invented a distinction between a stamped cartridge and a labelled jug
    that does not exist. Both would have been noticed at the pump and nowhere
    else, which is the argument for keeping the difference down to one word.
    """
    noun = "jug" if str(cart_code or "").strip().upper() == "RPS" else "cartridge"
    return {
        "noun": noun,
        "where": f"Turn the {noun} over. The lot label on the bottom reads `L-` "
                 "followed by the lot.",
        "field": f"L- — lot on the {noun} bottom label",
        "still_reads": f"{noun.capitalize()} in my hand still reads",
    }


def parse_expiry(value):
    """Parse the `E-` stamp into a date, tolerating how it gets typed.

    Accepts MM/YYYY, MM-YY, YYYY-MM, MMYYYY, MMYY, MM/DD/YYYY and YYYYMMDD.
    A month-only stamp resolves to the LAST day of that month, because a
    cartridge stamped E-11/2026 is good through the end of November.

    Returns (status, parsed_date) where status is one of:
        ok | soon | expired | unreadable
    """
    raw = str(value or "").strip().upper()
    raw = re.sub(r"^(?:EXP|E)\s*[:#\-]?\s*", "", raw)
    digits = re.sub(r"[^0-9]", "", raw)
    parts = [p for p in re.split(r"[^0-9]+", raw) if p]

    y = m = d = None
    try:
        if len(parts) == 3:
            a, b, c = parts
            if len(a) == 4:            # YYYY-MM-DD
                y, m, d = int(a), int(b), int(c)
            else:                      # MM/DD/YYYY
                m, d, y = int(a), int(b), int(c)
        elif len(parts) == 2:
            a, b = parts
            if len(a) == 4:            # YYYY-MM
                y, m = int(a), int(b)
            else:                      # MM/YYYY or MM/YY
                m, y = int(a), int(b)
        elif len(parts) == 1:
            if len(digits) == 8:       # YYYYMMDD
                y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:])
            elif len(digits) == 6:     # MMYYYY
                m, y = int(digits[:2]), int(digits[2:])
            elif len(digits) == 4:     # MMYY
                m, y = int(digits[:2]), int(digits[2:])
            else:
                return "unreadable", None
        else:
            return "unreadable", None

        if y is None or m is None:
            return "unreadable", None
        if y < 100:
            y += 2000
        if not (1 <= m <= 12) or not (2000 <= y <= 2099):
            return "unreadable", None
        if d is None:
            d = calendar.monthrange(y, m)[1]
        if not (1 <= d <= calendar.monthrange(y, m)[1]):
            return "unreadable", None
        parsed = date(y, m, d)
    except (ValueError, TypeError):
        return "unreadable", None

    today = date.today()
    if parsed < today:
        return "expired", parsed
    if (parsed - today).days <= EXPIRY_SOON_DAYS:
        return "soon", parsed
    return "ok", parsed


def save_lot_photo(uploaded_file) -> str:
    """Persist a cartridge-stamp photo and return its filename (or None)."""
    if uploaded_file is None:
        return None
    name = getattr(uploaded_file, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "heic", "heif"):
        ext = "jpg"
    fname = f"lot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    with open(os.path.join(LOT_PHOTO_DIR, fname), "wb") as f:
        f.write(uploaded_file.getbuffer())
    return fname


def _build_lot_verification(session, v: dict, production_log_id=None) -> LotVerification:
    """Turn the dict the operator form assembles into a LotVerification row."""
    return LotVerification(
        operator_name=v.get("operator_name", "Unknown"),
        operator_id=_resolve_user_id(session, v.get("operator_name")),
        pump_station=v.get("pump_station", "Unknown"),
        pump_station_id=_resolve_pump_id(session, v.get("pump_station")),
        shift=v.get("shift", "Shift 1"),
        cartridge_type=v.get("cartridge_type", "V2"),
        resin_type=v.get("resin_type"),
        resin_spec_id=_resolve_resin_id(session, v.get("resin_type")),
        expected_lot=(v.get("expected_lot") or "")[:50] or None,
        entered_lot=(v.get("entered_lot") or "")[:50] or None,
        entered_expiry=(v.get("entered_expiry") or "")[:20] or None,
        expiry_status=v.get("expiry_status"),
        result=v.get("result", "recorded"),
        check_level=v.get("check_level", "full"),
        reason=v.get("reason") or None,
        photo_filename=v.get("photo_filename"),
        production_log_id=production_log_id,
    )


def add_lot_verification(verification: dict) -> int:
    """Record a standalone check with no production behind it.

    This is what a successful catch looks like: the operator read the stamp,
    it was the wrong lot, and they pulled the cartridge instead of pouring
    it. There is no ProductionLog to attach it to, and that absence is the
    point - these rows are the saves, not the misses.
    """
    session = ScopedSession()
    try:
        row = _build_lot_verification(session, verification)
        session.add(row)
        session.commit()
        return row.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_lot_verifications_df(days: int = 30, result: str = None) -> pd.DataFrame:
    """All lot checks in the trailing window, newest first."""
    session = ScopedSession()
    try:
        q = session.query(LotVerification)
        if days:
            q = q.filter(LotVerification.timestamp >= datetime.utcnow() - timedelta(days=int(days)))
        if result:
            q = q.filter(LotVerification.result == result)
        return pd.read_sql(q.order_by(desc(LotVerification.timestamp)).statement, session.bind)
    finally:
        session.close()


def add_hourly_log(
        operator_name: str, pump_station: str, shift: str, cartridge_type: str,
        resin_type: str, lot_number: str, bottles: int, scrap_empty: int,
        scrap_filled: int, notes: str = "", log_type: str = "Hourly Bottle Count",
        verification: dict = None, weight: dict = None,
        litres_poured: float = None, pour_note: str = ""
) -> bool:
    """Returns True if this log was matched to (and credited toward) an
    active AssignedRun's live progress tracker, False otherwise — the
    ProductionLog row is written either way, this only reports whether a
    specific run's counter moved, so the caller can tell the operator when
    it didn't (previously this failed completely silently, which is why a
    trailing space or case difference in a lot number could make a run's
    "current_units" quietly stop climbing with no indication why).

    Matching is case-/whitespace-insensitive and treats a blank lot number
    on either side as a wildcard, mirroring
    calculate_logged_units_for_resin()'s tolerance — an exact, case-
    sensitive match was too strict given pump/resin/cartridge values both
    ultimately come from the same dropdowns but lot numbers are free-typed
    by both the manager (creating the run) and the operator (logging
    against it).

    `verification` is the cartridge lot check the operator completed for
    this log, as assembled by the pouring form (see add_lot_verification
    for the shape and the meaning of each result). It is optional so that
    every existing caller - the Admin Panel, reconciliation, and the
    Device Gateway writer - keeps working untouched.

    `litres_poured` is a measured volume, for the pours that are an amount
    rather than a count of containers - so many litres decanted into a drum.
    It is None on an ordinary cartridge log, which is the common case, and
    when it is set it is what every total reads instead of multiplying the
    container count by the format size. `pour_note` is what it went into, in
    the operator's words, and nothing parses it. Both are optional so that
    every existing caller - the Admin Panel, reconciliation, and the Device
    Gateway writer - keeps working untouched.

    `weight` is the fill-weight reading for this log, as returned by
    fill_weight.judge(), or None when the operator did not take one - which
    is the common case and is fine. Unlike the lot check it is purely a
    measurement: nothing about it can prevent the log being written. Its
    status was judged against the resin's window at the moment of capture
    and is stored as given, so editing a spec later cannot retrospectively
    re-judge a reading somebody already took.
    """
    session = ScopedSession()
    matched_run = False
    try:
        log_row = ProductionLog(
            log_type=log_type, operator_name=operator_name, pump_station=pump_station, shift=shift,
            cartridge_type=cartridge_type, resin_type=resin_type, lot_number=lot_number, bottles_filled=bottles,
            scrap_empty=scrap_empty, scrap_filled=scrap_filled, notes=notes,
            operator_id=_resolve_user_id(session, operator_name),
            pump_station_id=_resolve_pump_id(session, pump_station),
            resin_spec_id=_resolve_resin_id(session, resin_type),
            verify_status=(verification or {}).get("result"),
            check_weight_g=(weight or {}).get("measured"),
            weight_deviation_g=(weight or {}).get("deviation"),
            weight_status=(weight or {}).get("status"),
            # Only ever a positive number or nothing. A zero stored here would
            # read as "this pour was measured at nothing" and beat the count,
            # which is the one way this column could lose data that was
            # recorded correctly.
            litres_poured=(float(litres_poured)
                           if litres_poured is not None and float(litres_poured) > 0
                           else None),
            pour_note=(str(pour_note).strip()[:120] or None) if pour_note else None,
        )
        session.add(log_row)

        # The cartridge check and the log it belongs to are written in one
        # transaction on purpose: a log that exists without its verification
        # row (or the reverse) would quietly undermine the whole audit trail.
        # The flush is only here to get log_row.id for the foreign key.
        if verification:
            session.flush()
            session.add(_build_lot_verification(session, verification, log_row.id))
        if log_type == "Hourly Bottle Count":
            t_pump = str(pump_station or "").strip().lower()
            t_resin = str(resin_type or "").strip().lower()
            t_cart = str(cartridge_type or "").strip().lower()
            t_lot = str(lot_number or "").strip().lower()

            active_run = None
            for run in session.query(AssignedRun).filter(AssignedRun.status.in_(["Active", "Pouring"])).all():
                if str(run.pump_station or "").strip().lower() != t_pump:
                    continue
                if str(run.resin_type or "").strip().lower() != t_resin:
                    continue
                if str(run.cartridge_type or "").strip().lower() != t_cart:
                    continue
                r_lot = str(run.lot_number or "").strip().lower()
                if t_lot and r_lot and t_lot != r_lot:
                    continue
                active_run = run
                break

            if active_run:
                active_run.current_units += bottles
                if active_run.current_units >= active_run.target_units and active_run.target_units > 0:
                    active_run.status = "Done"
                matched_run = True
        session.commit()
        return matched_run
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


UNDO_WINDOW_SECONDS = 120


def undo_own_log(log_id: int, operator_name: str,
                 window_seconds: int = UNDO_WINDOW_SECONDS) -> tuple:
    """Let an operator reverse their own most recent entry. Returns (ok, message).

    A typo on an hourly count - 2500 where 250 was meant - currently needs a
    manager to open Log Management and delete the row, which means the wrong
    number sits in every dashboard until somebody is found. That is a long
    time for a figure the whole plant is measured on, and it teaches people
    that mistakes are expensive to admit.

    Three limits, and each one is doing a job:

      * **Your own row only.** Checked against the operator's name on the log
        rather than trusting the caller, so this can never become a way to
        delete somebody else's work from an unprivileged screen.
      * **Recent only.** Two minutes. Long enough to notice a fat-fingered
        number and act, short enough that this is a correction rather than a
        way to quietly rewrite a shift after the fact.
      * **The latest row only.** Undoing an older entry while newer ones exist
        would silently change what those newer ones were credited against.

    Anything already reviewed is off limits: a log carrying a lot-verification
    flag is evidence a manager may be looking at, so it is refused here and
    stays a manager's decision. Run progress is recomputed from the surviving
    logs afterwards, so the counter follows the deletion rather than drifting.
    """
    session = ScopedSession()
    try:
        log = session.query(ProductionLog).filter(ProductionLog.id == int(log_id)).first()
        if not log:
            return False, "That log no longer exists."

        if str(log.operator_name or "").strip().lower() != str(operator_name or "").strip().lower():
            return False, "That log belongs to someone else."

        age = (datetime.utcnow() - (log.timestamp or datetime.utcnow())).total_seconds()
        if age > window_seconds:
            return False, ("Too late to undo from here - ask a manager to remove it "
                           "from Log Management.")

        newer = session.query(ProductionLog).filter(
            ProductionLog.operator_name == log.operator_name,
            ProductionLog.pump_station == log.pump_station,
            ProductionLog.id > log.id,
        ).count()
        if newer:
            return False, "You've logged again since - only the most recent entry can be undone."

        if log.verify_status in ("mismatch", "expired", "rejected"):
            return False, ("That log is flagged for review, so it needs a manager. "
                           "The flag is the record of a cartridge problem.")

        units = int(log.bottles_filled or 0)
        session.query(LotVerification).filter(
            LotVerification.production_log_id == log.id
        ).update({"production_log_id": None}, synchronize_session=False)
        session.delete(log)
        session.commit()
    finally:
        session.close()

    # Recompute from what survives rather than subtracting - the same reason
    # the run counter is rebuilt anywhere else it can drift.
    try:
        sync_all_runs_with_logs()
    except Exception:
        logger.exception("undo_own_log: run resync failed after deleting log %s", log_id)
    return True, f"Removed your last entry of {units:,} units."


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
    """Calibrate from an exact volume read off the tank gauge."""
    return _calibrate_reactor(
        reactor_name, actual_liters, operator_name,
        f"👀 EXACT LITERS CALIBRATION: Set to {actual_liters}L remaining. {notes}".strip())


def has_completed_daily_checklist(operator_name: str, shift: str, pump_station: str = None) -> bool:
    """Has this operator validated the station they're standing at, today, on this shift?

    The station is part of the question. A checklist certifies the condition
    of one pump - bins staged, station clean - so an operator moved to a
    different pump has certified nothing about it and gets asked again.

    Rows recorded before daily_checklists carried a station have a NULL one
    and count for any station on their date. That's deliberate: it keeps the
    day this shipped from re-locking every operator who had already done
    their checklist an hour earlier. From the next day on, every row carries
    a station and the per-pump rule applies in full.
    """
    session = ScopedSession()
    try:
        q = session.query(DailyChecklist).filter(
            DailyChecklist.operator_name == operator_name,
            DailyChecklist.date == date.today(),
            DailyChecklist.shift == shift,
        )
        if pump_station:
            q = q.filter(or_(DailyChecklist.pump_station == pump_station,
                             DailyChecklist.pump_station.is_(None)))
        return q.first() is not None
    finally:
        session.close()


def submit_daily_checklist(operator_name: str, shift: str, pump_station: str = None) -> bool:
    """Records a completed startup checklist for one operator at one station."""
    session = ScopedSession()
    try:
        today_d = date.today()
        # Prevent double-logging - scoped to the station, so validating a
        # second pump on the same shift correctly writes a second row.
        dupe = session.query(DailyChecklist).filter(
            DailyChecklist.operator_name == operator_name,
            DailyChecklist.date == today_d,
            DailyChecklist.shift == shift,
        )
        if pump_station:
            dupe = dupe.filter(DailyChecklist.pump_station == pump_station)
        if dupe.first():
            return True

        new_check = DailyChecklist(
            operator_name=operator_name,
            shift=shift,
            pump_station=pump_station,
            pump_station_id=_resolve_pump_id(session, pump_station),
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
                   color_tag: str = None, units_per_skid: int = 500) -> bool:
    """Inserts a new proprietary resin formulation directly into PostgreSQL.

    color_tag defaults to None rather than a colour on purpose. A caller that
    doesn't care leaves it unset, and resin_palette derives the colour from
    the name - which for a new revision of an existing family (Black V6, say)
    is already the right answer. Storing a colour here is for the case where
    somebody deliberately picked one.
    """
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

def last_log_at():
    """When the record was last fed, or None if it never has been.

    One indexed max() over the production log. This is the only question that
    can tell the difference between a quiet plant and a system that stopped
    receiving anything hours ago, and the two look identical on every other
    screen.
    """
    session = ScopedSession()
    try:
        return session.query(func.max(ProductionLog.timestamp)).scalar()
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
                "enable_packing": bool(getattr(settings, 'enable_packing', 1)),
                # True on a row written before this column existed: an install
                # that has never been told it dispatches work orders is a log,
                # and should look like one rather than like a half-finished
                # copy of something bigger.
                "simple_mode": bool(getattr(settings, 'simple_mode', 1)),
                # Off on a row written before this column existed, and off on
                # a new one. A floor that never decants into drums should not
                # have to look at a control for it.
                "enable_bulk_pour": bool(getattr(settings, 'enable_bulk_pour', 0)),
                # shift_count was stored and saved but never read back out of
                # here, so every caller fell through to shifts.py's default of
                # two. That is the right answer for this plant today, which is
                # exactly why it went unnoticed - a plant that set three would
                # have saved it and watched the app ignore it.
                "shift_count": int(getattr(settings, 'shift_count', 2) or 2),
                "pump_form_url": (getattr(settings, 'pump_form_url', "") or ""),
                "pump_form_label": (getattr(settings, 'pump_form_label', "") or ""),
            }
        return {
            "target_lph": 400.0, "packing_target_uph": 500.0, "shift_1_start": "06:00", "shift_1_hours": 8.5,
            "shift_2_start": "14:30", "shift_2_hours": 8.5, "shift_3_start": "23:00", "shift_3_hours": 7.0,
            "yield_target_pct": 99.0, "packing_yield_target_pct": 99.5, "shift_1_break_mins": 60.0,
            "shift_2_break_mins": 60.0, "shift_3_break_mins": 60.0, "enable_packing": True,
            "shift_count": 2, "pump_form_url": "", "pump_form_label": "",
            "simple_mode": True, "enable_bulk_pour": False
        }
    finally:
        session.close()

def update_plant_settings(values: dict) -> bool:
    """Apply a partial update to the single plant settings row.

    Takes a dict of column name -> value and writes only the keys present.
    It used to take fifteen positional arguments while its only caller - the
    Admin Panel's "Save Operational Parameters" button - passed a single
    dict, so every save raised TypeError and no plant parameter could be
    changed from the interface at all. A dict is also what the caller wanted
    anyway: the form edits a subset of the fields, and a partial update lets
    it leave the rest alone instead of having to resend values it never
    showed the user.

    Unknown keys are ignored rather than raising, so a form that grows a
    field before the column exists degrades quietly instead of taking the
    admin page down.
    """
    session = ScopedSession()
    try:
        settings = session.query(PlantSettings).first()
        if not settings:
            settings = PlantSettings()
            session.add(settings)
        # The on/off settings are stored as INTEGER, and every caller is a
        # checkbox handing back a Python bool. Postgres will not widen one to
        # the other on its own - it raises DatatypeMismatch and the whole save
        # is lost, including the fields that had nothing to do with it. Cast
        # here rather than at each call site, because the next checkbox added
        # to that form would hit this again and the failure names a column
        # rather than the pattern.
        int_flags = {"enable_packing", "simple_mode", "enable_bulk_pour"}
        for key, value in (values or {}).items():
            if hasattr(settings, key) and key not in ("id",):
                if key in int_flags and isinstance(value, bool):
                    value = int(value)
                setattr(settings, key, value)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
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






