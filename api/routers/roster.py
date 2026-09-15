"""Floor Personnel Administration, ported from pages/Mgr_Roster.py - the
manager side of provisioning operators/packers, distinct from Admin
Panel's own account management (this page can only create/reset floor
roles; IT Admins handle management accounts and terminations elsewhere,
per the original page's own on-screen notice).

One fix made during this port, not a pre-existing behavior kept on
purpose: neither crud.create_user nor crud.update_user_pin enforces
crud.pin_policy_error internally, and this page never called it either -
unlike update_user_credentials and Admin Panel's own provision/reset
flows, which the 3.47 changelog specifically says do. A manager could set
a one-character PIN for an operator through this exact page. Fixed here
and in pages/Mgr_Roster.py itself (same crud.pin_policy_error call both
places), not just in the new API - porting the gap forward while fixing
it "for the new frontend only" would leave the old page still open until
Streamlit is fully retired.
"""
from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.roster import FloorUserOut, ProvisionRequest, ResetPinRequest

router = APIRouter(prefix="/roster", tags=["roster"])

FLOOR_ROLES = ("operator", "packer")


@router.get("", response_model=list[FloorUserOut])
def roster(user: dict = Depends(require_ability("manage_people"))):
    df = crud.get_all_users_df()
    floor = df[df["role"].isin(FLOOR_ROLES)]
    return [FloorUserOut(id=int(r["id"]), full_name=r["full_name"], username=r["username"],
                         role=r["role"], shift=r["shift"]) for _, r in floor.iterrows()]


@router.post("/provision", status_code=201)
def provision(body: ProvisionRequest, user: dict = Depends(require_ability("manage_people"))):
    role = body.role.lower().strip()
    if role not in FLOOR_ROLES:
        raise HTTPException(status_code=400, detail="This page can only provision operators or packers.")
    pin_err = crud.pin_policy_error(role, body.pin)
    if pin_err:
        raise HTTPException(status_code=400, detail=pin_err)
    ok = crud.create_user(body.username, body.email, body.pin, body.full_name, role,
                          body.target_lph, body.shift)
    if not ok:
        raise HTTPException(status_code=400, detail="Username or email already exists.")
    return {"ok": True}


@router.post("/reset-pin")
def reset_pin(body: ResetPinRequest, user: dict = Depends(require_ability("manage_people"))):
    df = crud.get_all_users_df()
    row = df[df["id"] == body.user_id]
    if row.empty or row.iloc[0]["role"] not in FLOOR_ROLES:
        raise HTTPException(status_code=404, detail="No such floor personnel account.")
    pin_err = crud.pin_policy_error(row.iloc[0]["role"], body.new_pin)
    if pin_err:
        raise HTTPException(status_code=400, detail=pin_err)
    crud.update_user_pin(body.user_id, body.new_pin)
    return {"ok": True}
