import os
import uuid
import subprocess
from datetime import datetime, date, timedelta

import pandas as pd
import bcrypt
from sqlalchemy import desc, text

from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion)

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

def init_db():
    Base.metadata.create_all(bind=engine)
    migrations = [
        "ALTER TABLE users ALTER COLUMN pin TYPE VARCHAR(255);",
        "ALTER TABLE users ADD COLUMN email VARCHAR(120);",
        "ALTER TABLE users ADD COLUMN target_lph FLOAT DEFAULT 400.0;",
        "ALTER TABLE users ADD COLUMN shift VARCHAR(20) DEFAULT 'Shift 1';",
        "ALTER TABLE resin_specs ADD COLUMN units_per_skid INTEGER DEFAULT 500;",
        "ALTER TABLE assigned_runs ADD COLUMN run_type VARCHAR(20) DEFAULT 'Pouring';",
        "ALTER TABLE plant_settings ADD COLUMN packing_target_uph FLOAT DEFAULT 500.0;",
        "ALTER TABLE plant_settings ADD COLUMN shift_3_start VARCHAR(10) DEFAULT '23:00';",
        "ALTER TABLE plant_settings ADD COLUMN shift_3_hours FLOAT DEFAULT 7.0;",
        "ALTER TABLE plant_settings ADD COLUMN packing_yield_target_pct FLOAT DEFAULT 99.5;",
        "ALTER TABLE reactors ADD COLUMN current_resin VARCHAR(100);",
        "ALTER TABLE reactors ADD COLUMN assigned_pump VARCHAR(50);",
        "ALTER TABLE plant_settings ADD COLUMN shift_1_break_mins FLOAT DEFAULT 60.0;",
        "ALTER TABLE plant_settings ADD COLUMN shift_2_break_mins FLOAT DEFAULT 60.0;",
        "ALTER TABLE plant_settings ADD COLUMN shift_3_break_mins FLOAT DEFAULT 60.0;",
        "ALTER TABLE plant_settings ADD COLUMN handover_emails TEXT DEFAULT '';",
        "ALTER TABLE users ADD COLUMN preferred_theme VARCHAR(50) DEFAULT 'Default Dark';",
        "ALTER TABLE plant_settings ADD COLUMN enable_packing INTEGER DEFAULT 1;",
        "ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255);"
    ]
    with engine.connect() as conn:
        for m in migrations:
            try:
                conn.execute(text(m))
                conn.commit()
            except Exception:
                conn.rollback()

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
            pump_station=pump_station, status=new_status, lot_number=lot_number, notes=notes, run_type=run_type
        )
        session.add(new_run)

        if run_type == "Pouring" and new_status != "Done" and reactor_id != "Floor WIP":
            reactor = session.query(Reactor).filter(Reactor.reactor_name == reactor_id).first()
            if reactor:
                reactor.current_resin = resin_type
                reactor.assigned_pump = pump_station

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


def authenticate_user(username: str, pin: str):
    session = ScopedSession()
    try:
        # Fetch the user purely by username first
        user = session.query(User).filter(User.username == username.lower().strip()).first()

        # Verify the PIN using bcrypt
        if user and bcrypt.checkpw(pin.strip().encode('utf-8'), user.pin.encode('utf-8')):
            return {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "shift": user.shift,
                "preferred_theme": getattr(user, 'preferred_theme', "Default Dark")
            }
        return None
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
            notes=f"👀 VISUAL LEVEL CALIBRATION: Set to {visual_fill_pct}%. {notes}".strip()
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
            scrap_empty=scrap_empty, scrap_filled=scrap_filled, notes=notes
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
                                duration_min=duration_min, notes=notes))
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
                             is_spill="Yes" if is_spill else "No", notes=notes))
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
                           operator=None) -> pd.DataFrame:
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
        if operator and operator != "All Operators":
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

def create_database_backup() -> str:
    filename = f"mes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    env = os.environ.copy()

    # Strictly pulling from .env, no fallback!
    env["PGPASSWORD"] = os.getenv("PG_PASS")

    try:
        subprocess.run(
            [r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe", "-U", "postgres", "-h", "localhost", "-p", "5432", "-d",
             "formlabs_mes", "-f", os.path.join(BACKUP_DIR, filename)], env=env, check=True)
        return filename
    except Exception:
        return None


def restore_database_backup(filename: str) -> bool:
    env = os.environ.copy()

    # Strictly pulling from .env, no fallback!
    env["PGPASSWORD"] = os.getenv("PG_PASS")

    try:
        subprocess.run(
            [r"C:\Program Files\PostgreSQL\18\bin\psql.exe", "-U", "postgres", "-h", "localhost", "-p", "5432", "-d",
             "formlabs_mes", "-f", os.path.join(BACKUP_DIR, filename)], env=env, check=True)
        return True
    except Exception:
        return False


def send_floor_message(operator_name: str, sender_name: str, message: str, is_manager: bool):
    session = ScopedSession()
    try:
        session.add(FloorMessage(operator_name=operator_name, sender_name=sender_name, message=message,
                                 is_manager_reply=1 if is_manager else 0))
        session.commit()
    finally:
        session.close()


def get_chat_history_df(operator_name: str) -> pd.DataFrame:
    session = ScopedSession()
    try:
        return pd.read_sql(session.query(FloorMessage).filter(FloorMessage.operator_name == operator_name).order_by(
            FloorMessage.timestamp).statement, session.bind)
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
            notes=f"🔄 AUTO-RECONCILIATION: Plant-wide adjustment of {delta} units to align with finalized packing skid count of {final_packed_qty}."
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
            notes=f"👀 EXACT LITERS CALIBRATION: Set to {actual_liters}L remaining. {notes}".strip()
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
            shift=shift
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
        return False
    finally:
        session.close()


def get_all_suggestions_df() -> pd.DataFrame:
    session = ScopedSession()
    try:
        return pd.read_sql(session.query(Suggestion).order_by(desc(Suggestion.timestamp)).statement, session.bind)
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

init_db()
seed_initial_data()