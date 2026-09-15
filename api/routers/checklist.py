"""The daily pre-shift gate - operators and packers cannot log anything
until this is satisfied for their station/shift/today. Ported from
pages/operator_form/checklist.py's render_checklist_gate(): same crud.py
calls, same rules. The client decides whether to show this gate or the
logging tabs (mirroring "Only enforced for Operators and Packers, not
Managers" from the original) - these endpoints don't need their own role
check, since a manager/admin session simply never calls them.

One deliberate hardening over the Streamlit version: whether today's
cleanliness photo was already submitted used to live in a browser cookie
(clean_chk_<user>_<station>, so a page reload didn't lose the flag mid-
flow). Here it's a real server-side query against cleanliness_audits, so
it survives a reload OR a different device/browser, and /submit checks it
itself rather than trusting whatever the client last rendered.
"""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import crud
from db_core import ScopedSession
from models import CleanlinessAudit
from api.shared import _vessel_label
from api.deps import get_current_user
from api.schemas.checklist import (
    ChecklistStatus, ChecklistSubmitRequest, MarkAlreadyDoneRequest,
    VesselOption, VesselOptionsOut,
)
from api.uploads import to_streamlit_like_many

router = APIRouter(prefix="/checklist", tags=["checklist"])

CLEANLINESS_AUDIT_TYPE = "Start Of Shift (Cleanliness Check)"


def _cleanliness_done_today(operator_name: str, station: str, shift: str) -> bool:
    session = ScopedSession()
    try:
        return session.query(CleanlinessAudit).filter(
            CleanlinessAudit.operator_name == operator_name,
            CleanlinessAudit.pump_station == station,
            CleanlinessAudit.shift == shift,
            CleanlinessAudit.date == date.today(),
            CleanlinessAudit.audit_type.in_(
                [CLEANLINESS_AUDIT_TYPE, crud.ALREADY_DONE_CHECKLIST_AUDIT_TYPE]),
        ).first() is not None
    finally:
        session.close()


@router.get("/status", response_model=ChecklistStatus)
def status(station: str, shift: str, user: dict = Depends(get_current_user)):
    return ChecklistStatus(
        checklist_done=crud.has_completed_daily_checklist(user["full_name"], shift, station),
        cleanliness_done_today=_cleanliness_done_today(user["full_name"], station, shift),
    )


@router.get("/vessel-options", response_model=VesselOptionsOut)
def vessel_options(station: str, user: dict = Depends(get_current_user)):
    """The "which tank feeds this pump?" question - asked only when the
    pump has no vessel linked yet (crud.vessels_on_pump is empty)."""
    if crud.vessels_on_pump(station):
        return VesselOptionsOut(has_vessel=True, options=[])
    opts = crud.vessels_for_pump_picker(station)
    return VesselOptionsOut(
        has_vessel=False,
        options=[VesselOption(value=v["reactor_name"], label=_vessel_label(v)) for v in opts],
    )


@router.post("/cleanliness")
async def submit_cleanliness(
    station: str = Form(...),
    shift: str = Form(...),
    notes: str = Form(""),
    skip_photo: bool = Form(False),
    photos: list[UploadFile] = File(default=[]),
    user: dict = Depends(get_current_user),
):
    saved = await to_streamlit_like_many(photos)
    if not saved and not skip_photo:
        raise HTTPException(status_code=400,
                            detail='A photo is required, or check "station is clean" to skip it.')
    ok = crud.add_cleanliness_audit(
        audit_type=CLEANLINESS_AUDIT_TYPE,
        operator_name=user["full_name"],
        pump_station=station,
        shift=shift,
        resin_type="",
        notes=notes,
        is_spill=False,
        uploaded_files=saved,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to record cleanliness audit.")
    return {"ok": True}


@router.post("/submit")
def submit(body: ChecklistSubmitRequest, user: dict = Depends(get_current_user)):
    if not (body.qr_checked and body.materials_checked):
        raise HTTPException(status_code=400, detail="Check every manual verification item first.")
    if not _cleanliness_done_today(user["full_name"], body.station, body.shift):
        raise HTTPException(status_code=400,
                            detail="Complete and submit the Morning Cleanliness Check first.")
    crud.submit_daily_checklist(user["full_name"], body.shift, body.station)
    if body.vessel_reactor_name:
        crud.link_vessel_to_pump(body.vessel_reactor_name, body.station)
    return {"ok": True}


@router.post("/mark-already-done")
def mark_already_done(body: MarkAlreadyDoneRequest, user: dict = Depends(get_current_user)):
    """The temporary override for the old, not-yet-individually-named pumps
    (see crud.py's has_completed_daily_checklist docstring and the 3.47
    changelog entry) - records who unlocked it and who they say actually
    did the work, then unlocks the same way a normal submit does."""
    who = body.already_who.strip()
    if not who:
        raise HTTPException(status_code=400, detail="Name who actually completed the checklist.")
    logged = crud.add_cleanliness_audit(
        audit_type=crud.ALREADY_DONE_CHECKLIST_AUDIT_TYPE,
        operator_name=user["full_name"],
        pump_station=body.station,
        shift=body.shift,
        resin_type="",
        notes=(f"{user['full_name']} unlocked {body.station} without redoing the checklist, "
               f"saying it was already completed today by: {who}."),
        is_spill=False,
    )
    if not logged:
        raise HTTPException(status_code=500, detail="Could not record the audit trail for this override.")
    crud.submit_daily_checklist(user["full_name"], body.shift, body.station)
    return {"ok": True}
