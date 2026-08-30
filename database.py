
"""
database.py - Facade Hub
This file safely routes all existing UI imports to our new modular architecture.
"""
from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion)
from utils import UPLOAD_DIR, AVATAR_DIR, BACKUP_DIR, create_database_backup, restore_database_backup, do_logout, check_authentication, get_avatar_path, get_avatar_data_uri

# The asterisk (*) imports every function from crud.py so your UI files can still find them!
from crud import *
# --- Device Gateway (protocol-agnostic machine integration) ---
from device_models import Device, DeviceTagMap, DeviceReading
from device_crud import *

