from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text
from datetime import datetime, date
from db_core import Base

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

class ProductionLog(Base):
    __tablename__ = "production_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    log_type = Column(String(50), nullable=False)
    operator_name = Column(String(100), nullable=False, index=True)
    pump_station = Column(String(50), nullable=False, index=True)
    shift = Column(String(20), default="Shift 1")
    cartridge_type = Column(String(20), default="V2")
    resin_type = Column(String(100), nullable=True)
    lot_number = Column(String(50), nullable=True)
    bottles_filled = Column(Integer, default=0)
    scrap_empty = Column(Integer, default=0)
    scrap_filled = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

class DowntimeLog(Base):
    __tablename__ = "downtime_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, default=date.today, index=True)
    operator_name = Column(String(100), nullable=False)
    pump_station = Column(String(50), nullable=False)
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
    __tablename__ = "daily_checklists"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, default=date.today, index=True)
    operator_name = Column(String(100), nullable=False, index=True)
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

# Generic public placeholders (Safe for source code)
MASTER_FORMLABS_CATALOG = (
    ("V2", "RS-C2-GPCL-05", "FLGPCL05", "24", "Standard Clear V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
    ("V2", "RS-C2-GPBK-05", "FLGPBK05", "24", "Standard Black V5", 1110.0, 1100.0, 1115.0, "1100-1115", 1.0, "#EA580C"),
)