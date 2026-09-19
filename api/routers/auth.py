"""Login, logout, and session-restore - the entire auth surface.

Reuses crud.py's session model exactly as Streamlit's "remember this
device" cookie already does (crud.create_session/get_user_by_session_token
/delete_session, backed by the same user_sessions table) - the only
behavior change is that a session row is now created on every login, not
only when "remember" is ticked. A React SPA has no per-tab server memory
the way st.session_state gave a running Streamlit script, so a page reload
has nothing to restore identity from except the cookie; "remember" only
decides whether that cookie survives closing the browser.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

import crud
from api.deps import SESSION_COOKIE, get_current_user
from api.schemas.auth import LoginRequest, PlantModeOut, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE_REMEMBERED = 60 * 60 * 24 * crud.SESSION_LIFETIME_DAYS


def _set_session_cookie(request: Request, response: Response, token: str, remember: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE_REMEMBERED if remember else None,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


@router.get("/mode", response_model=PlantModeOut)
def mode():
    """Read before authentication, on purpose - Home.py's own login screen
    picks its title ("POURING LOG" vs "SCADA TERMINAL") from this before
    anyone has signed in, because it's the one screen that has to describe
    the plant to somebody who hasn't yet. Safe to leave unauthenticated:
    it reveals nothing beyond what the sign-in screen already shows anyone
    who loads it."""
    return PlantModeOut(simple_mode=bool(crud.get_plant_settings().get("simple_mode", True)))


@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    """Self-registration, ported from Home.py's "REGISTER ACCESS" tab - a
    new operator can create their own account, but only as Operator or
    Packer; the role picker never offers anything above that.

    Two bugs fixed from the original while porting: it hard-coded
    role="operator" regardless of what the picker actually selected (so
    "Packer" in the dropdown silently created an operator anyway), and it
    never checked pin_policy_error at all - a self-registered PIN could be
    a single character even though every other path that sets a PIN in
    this app enforces a 4-character minimum for floor roles.
    """
    if "@" not in body.email or "." not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address format.")
    if not (body.full_name.strip() and body.username.strip() and body.pin.strip() and body.email.strip()):
        raise HTTPException(status_code=400, detail="All clearance fields are required.")
    role = body.role.strip().lower()
    if role not in ("operator", "packer"):
        raise HTTPException(status_code=400, detail="Self-registration can only create Operator or Packer accounts.")
    pin_err = crud.pin_policy_error(role, body.pin)
    if pin_err:
        raise HTTPException(status_code=400, detail=pin_err)
    ok = crud.create_user(body.username, body.email, body.pin, body.full_name, role,
                          400.0, body.shift, "Formlabs Forge")
    if not ok:
        raise HTTPException(status_code=409, detail="Operator ID or email is already registered.")
    return {"ok": True}


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response):
    user, error = crud.authenticate_user(body.username, body.pin)
    if not user:
        raise HTTPException(status_code=401, detail=error)
    token = crud.create_session(user["id"])
    _set_session_cookie(request, response, token, body.remember)
    return {**user, "abilities": crud.effective_abilities(user["id"], user["role"])}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        crud.delete_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return {**user, "abilities": crud.effective_abilities(user["id"], user["role"])}
