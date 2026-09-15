"""Packing tab - ported from pages/operator_form/packing_tab.py. The
packer's equivalent of the Pouring tab's submit, minus the lot gate and
changeover logic (packing has neither in the original). units_per_skid
for the "equates to N skids" caption travels on ResinSpecOut
(api/schemas/reference.py) rather than a separate endpoint - it's the same
resin-spec row the picker already fetches.
"""
from fastapi import APIRouter, Depends

import crud
from api.deps import get_current_user, resolve_operator_name
from api.schemas.packing import PackingSubmitRequest

router = APIRouter(prefix="/packing", tags=["packing"])


@router.post("/submit")
def submit(body: PackingSubmitRequest, user: dict = Depends(get_current_user)):
    crud.add_hourly_log(
        operator_name=resolve_operator_name(user, body.as_operator),
        pump_station="Pack-Out Station", shift=user["shift"] or "",
        cartridge_type=body.cartridge_type, resin_type=body.resin, lot_number=body.lot_number,
        bottles=body.units_packed, scrap_empty=0, scrap_filled=0, notes=body.notes,
        log_type="Packing Count",
    )
    return {"ok": True, "message": f"Packing saved. Recorded {body.units_packed} units."}
