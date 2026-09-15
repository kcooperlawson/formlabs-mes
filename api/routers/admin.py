"""IT Admin Console, ported from pages/Admin_Panel.py - the five-tab console
for user management, the suggestions/crash inboxes, database utilities, and
plant-wide configuration. Gated by crud.can_administer (api.deps's
require_admin_console), not a plain ability: an admin always reaches it, and
so does a manager on a plant running in simple (logging) mode, where there is
deliberately no separate IT role.

Backup create/restore/prune shell out to pg_dump/psql against a fixed
"backups/" directory on disk (utils.py), not a per-database one - the same
directory a real plant's backup history already lives in. See
tests/test_api_admin.py for why the automated suite only exercises the
read-only backup endpoints.

Fixes one genuine bug found while porting: the original page's downtime-code
delete button passed a reason NAME into crud.delete_downtime_reason, which
filters by id - so deleting a downtime code from Admin Panel silently did
nothing. This port queries reasons with their id so delete actually works.
"""
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
import external_links
import pace
import shift_clock
import utils
from backup_policy import DUE_AFTER_HOURS, KEEP_BACKUPS, backup_state
from db_core import ScopedSession
from models import DowntimeReason
from api.deps import require_admin_console
from api.schemas.admin import (AbilityHistoryEntry, AbilityInfo, AddDowntimeReasonRequest,
                               AddPumpRequest, BackupStatusOut, CreateBackupOut, CreateUserRequest,
                               ErrorReportOut, PlantSettingsOut, PumpOut, ResetPinRequest,
                               ResolveErrorRequest, RestoreBackupRequest, SetPumpRateRequest,
                               SuggestionOut, UpdatePlantSettingsRequest, UpdatePlantSettingsResult,
                               UpdateRoleShiftRequest, UpdateSuggestionRequest, UserAbilitiesOut,
                               UserOut, WipStatusOut)

router = APIRouter(prefix="/admin", tags=["admin"])


def _opt(value):
    """A DataFrame cell as None-or-string, never "nan". See api/routers/reactors.py's
    _s() for the same trap - this variant keeps None distinct from "" for fields
    where the two mean different things (an unresolved crash's resolved_by, say)."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    return str(value)


def _iso(value) -> str | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return ts.isoformat()


# --- roster ------------------------------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(user: dict = Depends(require_admin_console)):
    df = crud.get_all_users_df()
    now = datetime.utcnow()
    out = []
    for _, r in df.iterrows():
        locked_until = r.get("locked_until")
        is_locked = pd.notna(locked_until) and pd.Timestamp(locked_until).to_pydatetime() > now
        minutes_left = None
        if is_locked:
            minutes_left = max(0, int((pd.Timestamp(locked_until).to_pydatetime() - now).total_seconds() // 60) + 1)
        out.append(UserOut(
            id=int(r["id"]), full_name=r["full_name"], username=r["username"], email=_opt(r.get("email")),
            role=r["role"], shift=_opt(r.get("shift")),
            target_lph=float(r["target_lph"]) if pd.notna(r.get("target_lph")) else None,
            is_locked=bool(is_locked), locked_minutes_left=minutes_left,
            failed_login_attempts=int(r.get("failed_login_attempts") or 0),
        ))
    return out


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: CreateUserRequest, user: dict = Depends(require_admin_console)):
    pin_err = crud.pin_policy_error(body.role, body.pin)
    if pin_err:
        raise HTTPException(status_code=400, detail=pin_err)
    ok = crud.create_user(body.username, body.email, body.pin, body.full_name, body.role.lower(),
                          body.target_lph, body.shift)
    if not ok:
        raise HTTPException(status_code=409, detail="Username or email already exists.")
    row = crud.get_all_users_df()
    row = row[row["username"] == body.username].iloc[0]
    return UserOut(id=int(row["id"]), full_name=row["full_name"], username=row["username"],
                  email=_opt(row.get("email")), role=row["role"], shift=_opt(row.get("shift")),
                  target_lph=float(row["target_lph"]) if pd.notna(row.get("target_lph")) else None,
                  is_locked=False, locked_minutes_left=None,
                  failed_login_attempts=0)


@router.put("/users/{user_id}/role-shift")
def update_role_shift(user_id: int, body: UpdateRoleShiftRequest, user: dict = Depends(require_admin_console)):
    if not crud.update_user_role_and_shift(user_id, body.role.lower(), body.shift):
        raise HTTPException(status_code=404, detail="User not found.")
    return {"ok": True}


@router.put("/users/{user_id}/pin")
def reset_pin(user_id: int, body: ResetPinRequest, user: dict = Depends(require_admin_console)):
    df = crud.get_all_users_df()
    row = df[df["id"] == user_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="User not found.")
    pin_err = crud.pin_policy_error(row.iloc[0]["role"], body.pin)
    if pin_err:
        raise HTTPException(status_code=400, detail=pin_err)
    crud.update_user_pin(user_id, body.pin)
    return {"ok": True}


@router.post("/users/{user_id}/unlock")
def unlock_user(user_id: int, user: dict = Depends(require_admin_console)):
    if not crud.unlock_user_account(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_admin_console)):
    df = crud.get_all_users_df()
    row = df[df["id"] == user_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="User not found.")
    username = row.iloc[0]["username"]
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    crud.delete_user_by_username(username)
    return {"ok": True}


# --- abilities -----------------------------------------------------------
@router.get("/users/{user_id}/abilities", response_model=UserAbilitiesOut)
def user_abilities(user_id: int, user: dict = Depends(require_admin_console)):
    df = crud.get_all_users_df()
    row = df[df["id"] == user_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="User not found.")
    role = row.iloc[0]["role"]
    held = crud.abilities_of(user_id, role)
    abilities = [
        AbilityInfo(key=key, label=label, help=help_text, status=held.get(key, ""),
                   can_grant=crud.user_can(user["id"], user["role"], key))
        for key, (label, help_text) in crud.ABILITIES.items()
    ]
    history = [
        AbilityHistoryEntry(
            ability=h["ability"], label=h["label"], granted_by=h.get("granted_by"),
            granted_at=h["granted_at"].isoformat() if h.get("granted_at") else None,
            revoked_by=h.get("revoked_by"),
            revoked_at=h["revoked_at"].isoformat() if h.get("revoked_at") else None,
            active=bool(h["active"]),
        )
        for h in crud.ability_history(user_id)
    ]
    return UserAbilitiesOut(user_id=user_id, full_name=row.iloc[0]["full_name"], role=role,
                            abilities=abilities, history=history)


@router.post("/users/{user_id}/abilities/{key}")
def grant_ability(user_id: int, key: str, user: dict = Depends(require_admin_console)):
    ok, msg = crud.grant_ability(user_id, key, by_name=user["full_name"], by_user_id=user["id"],
                                 by_role=user["role"])
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.delete("/users/{user_id}/abilities/{key}")
def revoke_ability(user_id: int, key: str, user: dict = Depends(require_admin_console)):
    ok, msg = crud.revoke_ability(user_id, key, by_name=user["full_name"])
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


# --- crash reports ---------------------------------------------------------
@router.get("/error-reports", response_model=list[ErrorReportOut])
def error_reports(include_resolved: bool = False, user: dict = Depends(require_admin_console)):
    df = crud.get_error_reports_df(include_resolved=include_resolved)
    out = []
    for _, r in df.iterrows():
        out.append(ErrorReportOut(
            id=int(r["id"]), ref_code=r["ref_code"], occurred_at=_iso(r.get("occurred_at")),
            last_seen_at=_iso(r.get("last_seen_at")), page=_opt(r.get("page")),
            user_name=_opt(r.get("user_name")), user_role=_opt(r.get("user_role")),
            app_version=_opt(r.get("app_version")), error_type=_opt(r.get("error_type")),
            message=_opt(r.get("message")), traceback=_opt(r.get("traceback")),
            hits=int(r.get("hits") or 1), resolved=bool(r.get("resolved")),
            resolved_at=_iso(r.get("resolved_at")), resolved_by=_opt(r.get("resolved_by")),
            note=_opt(r.get("note")),
        ))
    return out


@router.post("/error-reports/{report_id}/resolve")
def resolve_error_report(report_id: int, body: ResolveErrorRequest, user: dict = Depends(require_admin_console)):
    if not crud.resolve_error_report(report_id, resolved_by=user["full_name"], note=body.note):
        raise HTTPException(status_code=404, detail="Report not found.")
    return {"ok": True}


# --- suggestions -----------------------------------------------------------
@router.get("/suggestions", response_model=list[SuggestionOut])
def suggestions(user: dict = Depends(require_admin_console)):
    df = crud.get_all_suggestions_df()
    out = []
    for _, r in df.iterrows():
        out.append(SuggestionOut(
            id=int(r["id"]), timestamp=_iso(r.get("timestamp")), user_name=r["user_name"],
            user_role=r["user_role"], category=r["category"], suggestion=r["suggestion"],
            status=r["status"], admin_notes=_opt(r.get("admin_notes")),
            avatar_data_uri=utils.get_avatar_data_uri(_opt(r.get("avatar_filename"))),
        ))
    return out


@router.put("/suggestions/{suggestion_id}")
def update_suggestion(suggestion_id: int, body: UpdateSuggestionRequest, user: dict = Depends(require_admin_console)):
    if not crud.update_suggestion_status(suggestion_id, body.status, body.admin_notes):
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return {"ok": True}


@router.delete("/suggestions/{suggestion_id}")
def delete_suggestion(suggestion_id: int, user: dict = Depends(require_admin_console)):
    if not crud.delete_suggestion(suggestion_id):
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return {"ok": True}


# --- database utilities ---------------------------------------------------
@router.get("/wip", response_model=WipStatusOut)
def wip_status(user: dict = Depends(require_admin_console)):
    # ProductionLog.date is stamped from local date.today(), not UTC (see
    # models.py) - matching that here, rather than datetime.utcnow().date(),
    # is what "today" means. utcnow() rolls over to tomorrow several hours
    # before local midnight, which made WIP read as 0 every single evening
    # in that window even with real unpacked production sitting on the
    # floor - the one time a manager clearing WIP most needs the real number.
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    df = crud.get_production_logs_df()
    df_today = df[df["date"].astype(str) == today_str] if not df.empty else df
    poured = int(df_today[df_today["log_type"] == "Hourly Bottle Count"]["bottles_filled"].sum()) if not df_today.empty else 0
    packed = int(df_today[df_today["log_type"] == "Packing Count"]["bottles_filled"].sum()) if not df_today.empty else 0
    return WipStatusOut(poured_today=poured, packed_today=packed, wip=poured - packed)


@router.post("/wip/clear")
def clear_wip(user: dict = Depends(require_admin_console)):
    # See wip_status()'s own comment: local date, matching how
    # ProductionLog.date is actually stamped.
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    df = crud.get_production_logs_df()
    df_today = df[df["date"].astype(str) == today_str] if not df.empty else df
    poured = int(df_today[df_today["log_type"] == "Hourly Bottle Count"]["bottles_filled"].sum()) if not df_today.empty else 0
    packed = int(df_today[df_today["log_type"] == "Packing Count"]["bottles_filled"].sum()) if not df_today.empty else 0
    wip = poured - packed
    if wip > 0:
        crud.add_hourly_log(operator_name="System Admin", pump_station="Auto-Reconciliation", shift="System",
                            cartridge_type="V2", resin_type="WIP Clear", lot_number=f"WIP-CLR-{today_str}",
                            bottles=wip, scrap_empty=0, scrap_filled=0,
                            notes="System auto-generated packing log to clear Floor WIP.",
                            log_type="Packing Count")
    return {"cleared": wip}


@router.get("/backups/status", response_model=BackupStatusOut)
def backups_status(user: dict = Depends(require_admin_console)):
    state = backup_state(utils.list_backup_files())
    return BackupStatusOut(due_after_hours=DUE_AFTER_HOURS, keep_backups=KEEP_BACKUPS, **state)


@router.get("/backups", response_model=list[str])
def list_backups(user: dict = Depends(require_admin_console)):
    return sorted((f for f in utils.list_backup_files() if f.endswith(".sql")), reverse=True)


@router.post("/backups", response_model=CreateBackupOut)
def create_backup(user: dict = Depends(require_admin_console)):
    filename = utils.create_database_backup()
    if not filename:
        raise HTTPException(status_code=500, detail="Backup failed. Check pg_dump path.")
    utils.prune_old_backups()
    return CreateBackupOut(filename=filename)


@router.post("/backups/restore")
def restore_backup(body: RestoreBackupRequest, user: dict = Depends(require_admin_console)):
    existing = set(utils.list_backup_files())
    if body.filename not in existing:
        raise HTTPException(status_code=404, detail="Backup file not found.")
    if not utils.restore_database_backup(body.filename):
        raise HTTPException(status_code=500, detail="Restoration failed.")
    return {"ok": True}


# --- plant configuration ---------------------------------------------------
def _settings_out(s: dict) -> PlantSettingsOut:
    return PlantSettingsOut(
        shift_1_start=s.get("shift_1_start", "06:00"), shift_1_hours=float(s.get("shift_1_hours", 8.0)),
        shift_1_break_mins=int(s.get("shift_1_break_mins", 60)),
        shift_2_start=s.get("shift_2_start", "14:00"), shift_2_hours=float(s.get("shift_2_hours", 8.0)),
        shift_2_break_mins=int(s.get("shift_2_break_mins", 60)),
        shift_count=int(s.get("shift_count", 2)), target_lph=float(s.get("target_lph", 400.0)),
        yield_target_pct=float(s.get("yield_target_pct", 99.0)),
        enable_packing=bool(s.get("enable_packing", True)), enable_bulk_pour=bool(s.get("enable_bulk_pour", False)),
        enable_device_gateway=bool(s.get("enable_device_gateway", False)),
        operating_days=shift_clock.format_operating_days(shift_clock.parse_operating_days(s.get("operating_days"))),
        operating_days_desc=shift_clock.describe_operating_days(s.get("operating_days")),
        simple_mode=bool(s.get("simple_mode", True)), pump_form_url=s.get("pump_form_url") or "",
        pump_form_label=s.get("pump_form_label") or "",
    )


@router.get("/settings", response_model=PlantSettingsOut)
def get_settings(user: dict = Depends(require_admin_console)):
    return _settings_out(crud.get_plant_settings())


@router.put("/settings", response_model=UpdatePlantSettingsResult)
def update_settings(body: UpdatePlantSettingsRequest, user: dict = Depends(require_admin_console)):
    current = crud.get_plant_settings()
    simple_now = bool(current.get("simple_mode", True))
    use_orders = body.use_work_orders

    pump_clean, pump_problem = external_links.normalise(body.pump_form_url)

    mode_blocked = False
    no_admin_warning = None
    if simple_now and use_orders:
        users = crud.get_all_users_df()
        admins = 0 if users.empty else int((users["role"].astype(str).str.strip().str.lower() == "admin").sum())
        if admins == 0:
            mode_blocked = True
            no_admin_warning = (
                "This plant has no administrator account, and an execution system restricts this "
                "console to administrators — saving that would lock everyone out of it, including "
                "you. Give somebody the Administrator role under Personnel below, then set the mode "
                "again. Every other setting on this form was saved.")

    update_dict = {
        "shift_1_start": body.shift_1_start, "shift_1_hours": body.shift_1_hours,
        "shift_1_break_mins": body.shift_1_break_mins,
        "shift_2_start": body.shift_2_start, "shift_2_hours": body.shift_2_hours,
        "shift_2_break_mins": body.shift_2_break_mins,
        "shift_count": int(body.shift_count),
        "target_lph": body.target_lph, "yield_target_pct": body.yield_target_pct,
        "enable_packing": body.enable_packing, "enable_bulk_pour": body.enable_bulk_pour,
        "enable_device_gateway": body.enable_device_gateway,
        "operating_days": shift_clock.format_operating_days(set(body.operating_days)),
        "simple_mode": simple_now if mode_blocked else (not use_orders),
        "pump_form_url": pump_clean,
        "pump_form_label": (body.pump_form_label or "").strip()[:60],
    }
    crud.update_plant_settings(update_dict)

    orders_off_warning = None
    if simple_now is False and use_orders is False:
        runs = crud.get_assigned_runs_df()
        live = 0 if runs.empty else int(runs["status"].isin(["Active", "Pouring", "Queued"]).sum())
        if live:
            orders_off_warning = (
                f"{live} run{'s are' if live != 1 else ' is'} still open. They are hidden from the "
                "operator terminal now, and the lot check records what was poured instead of "
                "comparing it against an expected lot. Nothing was deleted — set the mode back to "
                "bring them back.")

    pump_form_warning = None
    if pump_problem:
        pump_form_warning = f"{pump_problem} That address was not saved, so no button will appear on the operator terminal."

    return UpdatePlantSettingsResult(
        saved=_settings_out(crud.get_plant_settings()), pump_form_warning=pump_form_warning,
        orders_off_warning=orders_off_warning, no_admin_warning=no_admin_warning,
    )


@router.get("/pumps", response_model=list[PumpOut])
def list_pumps(user: dict = Depends(require_admin_console)):
    df = crud.get_all_pumps_df()
    plant_lph = float(crud.get_plant_settings().get("target_lph", 400.0) or 400.0)
    measured = pace.measured_rates()
    out = []
    for _, p in df.iterrows():
        set_rate = float(p["target_lph"]) if pd.notna(p.get("target_lph")) and float(p.get("target_lph") or 0) > 0 else None
        m = measured.get(str(p["station_name"]))
        out.append(PumpOut(
            id=int(p["id"]), station_name=p["station_name"], status=p.get("status") or "Active",
            target_lph=set_rate, effective_lph=set_rate or plant_lph,
            measured_median_lph=m["median_lph"] if m else None, measured_samples=m["samples"] if m else None,
        ))
    return out


@router.post("/pumps", status_code=201)
def add_pump(body: AddPumpRequest, user: dict = Depends(require_admin_console)):
    if not body.station_name.strip():
        raise HTTPException(status_code=400, detail="Station name is required.")
    crud.add_pump_station(body.station_name)
    return {"ok": True}


@router.put("/pumps/{pump_id}/rate")
def set_pump_rate(pump_id: int, body: SetPumpRateRequest, user: dict = Depends(require_admin_console)):
    if not pace.set_pump_rate(pump_id, body.target_lph):
        raise HTTPException(status_code=404, detail="Pump not found.")
    return {"ok": True}


@router.delete("/pumps/{pump_id}")
def delete_pump(pump_id: int, user: dict = Depends(require_admin_console)):
    crud.delete_pump_station(pump_id)
    return {"ok": True}


@router.get("/downtime-reasons")
def list_downtime_reasons(user: dict = Depends(require_admin_console)):
    """Reason name AND id, unlike the public reference.py list - the Admin
    Panel needs the id to delete a specific one. See this module's docstring
    for the bug this fixes versus the original page."""
    session = ScopedSession()
    try:
        rows = session.query(DowntimeReason).order_by(DowntimeReason.reason_name).all()
        return [{"id": r.id, "reason_name": r.reason_name} for r in rows]
    finally:
        session.close()


@router.post("/downtime-reasons", status_code=201)
def add_downtime_reason(body: AddDowntimeReasonRequest, user: dict = Depends(require_admin_console)):
    if not body.reason_name.strip():
        raise HTTPException(status_code=400, detail="Reason name is required.")
    crud.add_downtime_reason(body.reason_name)
    return {"ok": True}


@router.delete("/downtime-reasons/{reason_id}")
def delete_downtime_reason(reason_id: int, user: dict = Depends(require_admin_console)):
    crud.delete_downtime_reason(reason_id)
    return {"ok": True}
