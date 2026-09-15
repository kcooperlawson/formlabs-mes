"""Formlabs Master Resin Specification Lookup Table, ported from
pages/Mgr_Resin_Canvas.py: the manager-only table with SKU/resin code (the
public-facing /api/reference/resins never includes those, see that
router's own docstring) plus add/edit/delete. Gated by manage_resins on
every route, including the read - unlike most manager pages this one's
entire content, not just the write actions, is manager-only.

get_resin_spec_history exists in crud.py and was imported by the original
page, but never called anywhere in it - no history view was ever wired up,
so nothing is ported here either.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.resin_canvas import AddResinRequest, ResinCanvasRow, UpdateResinRequest
from resin_palette import resin_color

router = APIRouter(prefix="/resin-canvas", tags=["resin-canvas"])


def _row_out(r) -> ResinCanvasRow:
    return ResinCanvasRow(
        id=int(r["id"]), cartridge_type=r["cartridge_type"], sku=r["sku"] or "",
        resin_code=r["resin_code"] or "", resin_name=r["resin_name"],
        actual_spec_g=float(r["actual_spec_g"]), min_weight_g=float(r["min_weight_g"]),
        max_weight_g=float(r["max_weight_g"]), target_kg=round(float(r["actual_spec_g"]) / 1000.0, 4),
        multiplier=float(r["multiplier"]), lifetime_months=str(r["lifetime_months"] or ""),
        color=resin_color(r["resin_name"], r.get("color_tag")),
    )


@router.get("", response_model=list[ResinCanvasRow])
def list_specs(format: str = "ALL", search: str = "",
               user: dict = Depends(require_ability("manage_resins"))):
    df = crud.get_all_resin_specs_df(format)
    if search.strip():
        q = search.strip()
        df = df[
            df["resin_name"].str.contains(q, case=False, na=False) |
            df["sku"].str.contains(q, case=False, na=False) |
            df["resin_code"].str.contains(q, case=False, na=False)
        ]
    return [_row_out(r) for _, r in df.iterrows()]


@router.post("", status_code=201, response_model=ResinCanvasRow)
def add_spec(body: AddResinRequest, user: dict = Depends(require_ability("manage_resins"))):
    if not body.resin_name.strip():
        raise HTTPException(status_code=400, detail="Formulation name is required.")
    ok = crud.add_resin_spec(
        body.cartridge_type, body.sku, body.resin_code, body.resin_name,
        body.actual_spec_g, body.min_weight_g, body.max_weight_g,
        color_tag=body.color_tag, changed_by=user["full_name"])
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add resin. Check for duplicate names.")
    df = crud.get_all_resin_specs_df("ALL")
    row = df[df["resin_name"] == body.resin_name.strip()].iloc[-1]
    return _row_out(row)


@router.put("/{spec_id}", response_model=ResinCanvasRow)
def update_spec(spec_id: int, body: UpdateResinRequest, user: dict = Depends(require_ability("manage_resins"))):
    df = crud.get_all_resin_specs_df("ALL")
    match = df[df["id"] == spec_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="No such resin specification.")
    existing = match.iloc[0]
    crud.bulk_update_resin_specs(pd.DataFrame([{
        "id": spec_id, "sku": existing["sku"], "resin_code": existing["resin_code"],
        "resin_name": existing["resin_name"], "actual_spec_g": body.actual_spec_g,
        "min_weight_g": body.min_weight_g, "max_weight_g": body.max_weight_g,
        "multiplier": existing["multiplier"], "lifetime_months": existing["lifetime_months"],
        "color_tag": body.color_tag,
    }]), changed_by=user["full_name"])
    updated = crud.get_all_resin_specs_df("ALL")
    return _row_out(updated[updated["id"] == spec_id].iloc[0])


@router.delete("/{spec_id}")
def delete_spec(spec_id: int, user: dict = Depends(require_ability("manage_resins"))):
    ok = crud.delete_resin_spec(spec_id, changed_by=user["full_name"])
    if not ok:
        raise HTTPException(status_code=404, detail="No such resin specification.")
    return {"ok": True}
