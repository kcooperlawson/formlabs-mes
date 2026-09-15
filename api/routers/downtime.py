"""Downtime tab - ported from pages/operator_form/downtime_tab.py verbatim.
Already the simplest tab in the original (a plain st.form, no live
cross-widget behavior), so it stays simple here: one endpoint, one write.
"""
from fastapi import APIRouter, Depends

import crud
from api import realtime
from api.deps import get_current_user, resolve_operator_name
from api.schemas.downtime import DowntimeSubmitRequest

router = APIRouter(prefix="/downtime", tags=["downtime"])


@router.post("/submit")
def submit(body: DowntimeSubmitRequest, user: dict = Depends(get_current_user)):
    crud.add_downtime_log(
        operator_name=resolve_operator_name(user, body.as_operator), pump_station=body.station, shift=user["shift"] or "",
        reason=body.reason, duration_min=body.duration_min, notes=body.notes,
    )
    realtime.notify()
    return {"ok": True, "message": f"Recorded {body.duration_min} minutes downtime."}
