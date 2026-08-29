"""
database.py - Facade Hub
This file safely routes all existing UI imports to our new modular architecture.
"""
from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion)
from utils import UPLOAD_DIR, AVATAR_DIR, BACKUP_DIR, create_database_backup, restore_database_backup

# The asterisk (*) imports every function from crud.py so your UI files can still find them!
from crud import *