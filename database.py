
"""
database.py - Facade Hub
This file safely routes all existing UI imports to our new modular architecture.
"""
from db_core import engine, ScopedSession, Base
from models import (User, ProductionLog, DowntimeLog, AssignedRun, Reactor,
                    ResinSpec, PumpStation, DowntimeReason, DailyChecklist,
                    CleanlinessAudit, FloorMessage, PlantSettings, Suggestion,
                    LotVerification)
from utils import esc, UPLOAD_DIR, AVATAR_DIR, LOT_PHOTO_DIR, BACKUP_DIR, create_database_backup, restore_database_backup, do_logout, check_authentication, get_avatar_path, get_avatar_data_uri

# The asterisk (*) imports every function from crud.py so your UI files can still find them!
from crud import *
# --- Device Gateway (protocol-agnostic machine integration) ---
from device_models import Device, DeviceTagMap, DeviceReading
from device_crud import *



# =============================================================================
# READ CACHING
# -----------------------------------------------------------------------------
# Streamlit re-executes a page top to bottom on every widget interaction, so
# without this every keystroke in a number box re-queries Postgres for the
# resin list, the pump list, the operator list and the plant settings. On the
# floor that shows up as lag between tapping and the screen responding.
#
# Only reference data is cached - the things that change when a manager edits
# configuration, not when an operator logs production. Production logs, runs
# and lot verifications are deliberately NOT cached: they have to be correct
# the instant after a write, and they are the whole point of the app.
#
# The writers below clear the caches they invalidate, so a configuration change
# is visible immediately rather than after a TTL expires. The TTL is a backstop
# for changes made in another browser session, not the primary mechanism.
#
# This lives here, in the UI-facing facade, on purpose: crud.py stays free of
# any Streamlit import, so the headless gateway process can keep importing it.
# =============================================================================
import streamlit as _st
import crud as _crud

_REFERENCE_TTL = 300          # seconds; cleared explicitly on write


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_all_resin_specs_df(cartridge_type: str = "ALL"):
    return _crud.get_all_resin_specs_df(cartridge_type)


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_active_pumps():
    return _crud.get_active_pumps()


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_all_pumps_df():
    return _crud.get_all_pumps_df()


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_downtime_reasons():
    return _crud.get_downtime_reasons()


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_active_operators():
    return _crud.get_active_operators()


@_st.cache_data(ttl=_REFERENCE_TTL, show_spinner=False)
def get_all_reactors_df():
    return _crud.get_all_reactors_df()


@_st.cache_data(ttl=60, show_spinner=False)
def get_plant_settings():
    # Shorter TTL: shift times and targets drive every pace figure on screen,
    # so a stale copy is more visible here than in the equipment lists.
    return dict(_crud.get_plant_settings())


def _clear_reference_caches():
    """Drop every cached reference read. Called after any config write."""
    for _fn in (get_all_resin_specs_df, get_active_pumps, get_all_pumps_df,
                get_downtime_reasons, get_active_operators, get_all_reactors_df,
                get_plant_settings):
        try:
            _fn.clear()
        except Exception:
            pass


def _invalidating(fn):
    """Wrap a writer so the reference caches are dropped after it succeeds."""
    def _wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        _clear_reference_caches()
        return result
    _wrapped.__name__ = getattr(fn, "__name__", "wrapped")
    _wrapped.__doc__ = getattr(fn, "__doc__", None)
    return _wrapped


# Every write that can change what the cached reads return.
add_pump_station = _invalidating(_crud.add_pump_station)
delete_pump_station = _invalidating(_crud.delete_pump_station)
update_pump_status = _invalidating(_crud.update_pump_status)
add_resin_spec = _invalidating(_crud.add_resin_spec)
delete_resin_spec = _invalidating(_crud.delete_resin_spec)
bulk_update_resin_specs = _invalidating(_crud.bulk_update_resin_specs)
add_reactor = _invalidating(_crud.add_reactor)
delete_reactor = _invalidating(_crud.delete_reactor)
update_reactor_config = _invalidating(_crud.update_reactor_config)
add_downtime_reason = _invalidating(_crud.add_downtime_reason)
delete_downtime_reason = _invalidating(_crud.delete_downtime_reason)
create_user = _invalidating(_crud.create_user)
delete_user = _invalidating(_crud.delete_user)
delete_user_by_username = _invalidating(_crud.delete_user_by_username)
update_user_role_and_shift = _invalidating(_crud.update_user_role_and_shift)
update_plant_settings = _invalidating(_crud.update_plant_settings)
