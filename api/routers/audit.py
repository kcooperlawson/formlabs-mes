"""Audit tab - cleanliness, changeover and spill photo audits, ported from
pages/operator_form/audit_tab.py. Reuses the exact same crud.add_cleanliness_
audit + photo-adapter plumbing api/routers/checklist.py already established
for the pre-shift photo; this is the general-purpose version any operator
can file at any point in a shift, not just at startup.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import crud
from api.deps import get_current_user, resolve_operator_name
from api.uploads import to_streamlit_like_many

router = APIRouter(prefix="/audit", tags=["audit"])

AUDIT_TYPES = (
    "Start Of Shift (Cleanliness Check)",
    "End Of Shift (Cleanliness Check)",
    "Station / Pump Transfer Check",
    "Resin Spill / Containment Issue",
)


@router.post("/submit")
async def submit(
    audit_type: str = Form(...),
    station: str = Form(...),
    notes: str = Form(""),
    is_spill: bool = Form(False),
    photos: list[UploadFile] = File(default=[]),
    as_operator: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    if audit_type not in AUDIT_TYPES:
        raise HTTPException(status_code=400, detail="Not a recognized audit type.")
    saved = await to_streamlit_like_many(photos)
    ok = crud.add_cleanliness_audit(
        audit_type=audit_type, operator_name=resolve_operator_name(user, as_operator), pump_station=station,
        shift=user["shift"] or "", resin_type="", notes=notes, is_spill=is_spill,
        uploaded_files=saved,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to record photo audit. Please try again.")
    return {"ok": True, "message": "Photo audit recorded."}
