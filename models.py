


from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey
from datetime import datetime, date
from db_core import Base
import secrets

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    pin = Column(String(50), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    target_lph = Column(Float, default=400.0)
    shift = Column(String(20), default="Shift 1")
    # NEW COLUMN FOR THEME ENGINE
    preferred_theme = Column(String(255), default="Default Dark")
    avatar_filename = Column(String(255), nullable=True)
    # --- LOGIN LOCKOUT ---
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

class ProductionLog(Base):
    __tablename__ = "production_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    log_type = Column(String(50), nullable=False)
    operator_name = Column(String(100), nullable=False, index=True)
    pump_station = Column(String(50), nullable=False, index=True)
    # FK columns added alongside the legacy string columns above (kept for
    # backward compatibility and for "System"-generated rows with no real
    # matching row, e.g. auto-reconciliation entries). Nullable by design.
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    resin_spec_id = Column(Integer, ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(20), default="Shift 1")
    cartridge_type = Column(String(20), default="V2")
    resin_type = Column(String(100), nullable=True)
    lot_number = Column(String(50), nullable=True)
    bottles_filled = Column(Integer, default=0)
    scrap_empty = Column(Integer, default=0)
    scrap_filled = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    # Cartridge lot verification outcome for this log. Denormalized onto the
    # log itself purely so dashboards can filter/count without joining
    # lot_verifications; that table remains the system of record.
    #   verified | mismatch | expired | recorded | fast_path | skipped
    verify_status = Column(String(20), nullable=True, index=True)

class DowntimeLog(Base):
    __tablename__ = "downtime_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    operator_name = Column(String(100), nullable=False)
    pump_station = Column(String(50), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(20), default="Shift 1")
    reason = Column(String(100), nullable=False)
    duration_min = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

class AssignedRun(Base):
    __tablename__ = "assigned_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reactor_id = Column(String(50), default="Reactor 1")
    reactor_size_l = Column(Integer, default=5000)
    resin_type = Column(String(100), nullable=False)
    cartridge_type = Column(String(20), default="V2")
    target_units = Column(Integer, nullable=False)
    current_units = Column(Integer, default=0)
    assigned_operator = Column(String(100), nullable=False)
    pump_station = Column(String(50), nullable=False)
    resin_spec_id = Column(Integer, ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="Active")
    lot_number = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    run_type = Column(String(20), default="Pouring")

class Reactor(Base):
    __tablename__ = "reactors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reactor_name = Column(String(100), unique=True, nullable=False)
    max_capacity_l = Column(Integer, default=5000)
    status = Column(String(20), default="Active")
    current_resin = Column(String(100), nullable=True)
    assigned_pump = Column(String(50), nullable=True)
    current_resin_id = Column(Integer, ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_pump_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)

class ResinSpec(Base):
    __tablename__ = "resin_specs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cartridge_type = Column(String(20), nullable=False)
    sku = Column(String(100), nullable=True)
    resin_code = Column(String(50), nullable=True)
    lifetime_months = Column(String(20), default="24")
    resin_name = Column(String(100), nullable=False)
    actual_spec_g = Column(Float, nullable=False)
    min_weight_g = Column(Float, nullable=False)
    max_weight_g = Column(Float, nullable=False)
    acceptable_range = Column(String(50), nullable=True)
    multiplier = Column(Float, default=1.0)
    color_tag = Column(String(20), default="#EA580C")
    units_per_skid = Column(Integer, default=500)

class PumpStation(Base):
    __tablename__ = "pump_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    station_name = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default="Active")
    notes = Column(String(255), nullable=True)

class DowntimeReason(Base):
    __tablename__ = "downtime_reasons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reason_name = Column(String(100), unique=True, nullable=False)

class DailyChecklist(Base):
    """Pre-shift startup validation, scoped to one operator at one station.

    The station is part of the key, not decoration: a checklist certifies
    the condition of the pump you are standing at, so moving to a different
    pump means a new checklist. Rows written before the station column
    existed carry NULL and still satisfy any station for the day they were
    made, so adding this never locked anyone out mid-shift.
    """
    __tablename__ = "daily_checklists"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, default=date.today, index=True)
    operator_name = Column(String(100), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station = Column(String(50), nullable=True, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class CleanlinessAudit(Base):
    __tablename__ = "cleanliness_audits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    audit_type = Column(String(50), nullable=False)
    operator_name = Column(String(100), nullable=False)
    pump_station = Column(String(50), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    resin_spec_id = Column(Integer, ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(20), default="Shift 1")
    resin_type = Column(String(100), nullable=True)
    image_filename = Column(String(255), nullable=True)
    is_spill = Column(String(10), default="No")
    notes = Column(Text, nullable=True)

class FloorMessage(Base):
    __tablename__ = "floor_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    operator_name = Column(String(100), nullable=False, index=True)
    sender_name = Column(String(100), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(Text, nullable=False)
    is_manager_reply = Column(Integer, default=0)

class PlantSettings(Base):
    __tablename__ = "plant_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    target_lph = Column(Float, default=400.0)
    packing_target_uph = Column(Float, default=500.0)
    shift_1_start = Column(String(10), default="06:00")
    shift_1_hours = Column(Float, default=8.5)
    shift_2_start = Column(String(10), default="14:30")
    shift_2_hours = Column(Float, default=8.5)
    shift_3_start = Column(String(10), default="23:00")
    shift_3_hours = Column(Float, default=7.0)
    yield_target_pct = Column(Float, default=99.0)
    packing_yield_target_pct = Column(Float, default=99.5)
    shift_1_break_mins = Column(Float, default=60.0)
    shift_2_break_mins = Column(Float, default=60.0)
    shift_3_break_mins = Column(Float, default=60.0)
    handover_emails = Column(Text, default="")
    enable_packing = Column(Integer, default=1)  # 1 = True, 0 = False

class Suggestion(Base):
    __tablename__ = "suggestions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_name = Column(String(100), nullable=False)
    user_role = Column(String(20), nullable=False)
    category = Column(String(50), default="Feature Request")
    suggestion = Column(Text, nullable=False)
    status = Column(String(20), default="Open")  # Open, In Review, Implemented, Dismissed
    admin_notes = Column(Text, nullable=True)

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

class LotVerification(Base):
    """One row per cartridge-lot check at the pouring station.

    Written for every check the operator completes, not just the failures —
    a pass is what proves the check actually happened, and the mismatches
    are the first real measurement of how often the wrong lot reaches the
    pour. `production_log_id` is NULL when the operator rejected the
    cartridge and set it aside instead of pouring it, which is a successful
    catch, not a missing log.

    result:
        verified  - typed lot matched the run's lot
        mismatch  - did not match; operator logged anyway with a reason
        expired   - lot matched but the E- date is past; logged with a reason
        rejected  - operator pulled the cartridge, no production logged
        recorded  - no real run lot to compare against, stamp captured only
    check_level:
        full   - typed the stamp and photographed it
        fast   - one-tap confirm, nothing had changed since the last full check
        record - stamp captured with no run lot to compare it to
    """
    __tablename__ = "lot_verifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    operator_name = Column(String(100), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    pump_station = Column(String(50), nullable=False, index=True)
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(20), default="Shift 1")
    cartridge_type = Column(String(20), default="V2")
    resin_type = Column(String(100), nullable=True)
    resin_spec_id = Column(Integer, ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True, index=True)
    expected_lot = Column(String(50), nullable=True)
    entered_lot = Column(String(50), nullable=True)      # raw, exactly as typed
    entered_expiry = Column(String(20), nullable=True)   # raw, exactly as typed
    expiry_status = Column(String(20), nullable=True)    # ok | soon | expired | unreadable
    result = Column(String(20), nullable=False, index=True)
    check_level = Column(String(20), default="full")
    reason = Column(Text, nullable=True)                 # required on mismatch/expired/rejected
    photo_filename = Column(String(255), nullable=True)
    ocr_lot = Column(String(50), nullable=True)          # phase 3, offline OCR cross-check
    ocr_conflict = Column(Integer, default=0)            # 1 = photo disagrees with what was typed
    production_log_id = Column(Integer, ForeignKey("production_logs.id", ondelete="SET NULL"),
                               nullable=True, index=True)


# Generic public placeholders (Safe for source code)
MASTER_FORMLABS_CATALOG = (
    ("V2", "RS-C2-GPCL-05", "FLGPCL05", "24", "Standard Clear V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
    ("V2", "RS-C2-GPBK-05", "FLGPBK05", "24", "Standard Black V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
)




