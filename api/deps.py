"""Who is this, and what can they do - the one implementation of both.

Replaces two Streamlit-only things that had drifted into several copies:
utils.check_authentication() (Home.py kept its own duplicated inline copy
of the cookie-restore logic instead of calling it) and database.py's
can(), which reads st.session_state implicitly and so only ever worked
inside a running Streamlit script. Every route here asks these two
functions instead - crud.get_user_by_session_token/crud.user_can are
already framework-agnostic, so there is nothing Streamlit-shaped to port.
"""
from fastapi import Depends, HTTPException, Request

import crud
from api.backup_scheduler import maybe_run_scheduled_backup

SESSION_COOKIE = "mes_session"


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    user = crud.get_user_by_session_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Rides on every authenticated request the same way Home.py's own check
    # rides on every page load - see api/backup_scheduler.py for why.
    maybe_run_scheduled_backup()
    return user


def resolve_operator_name(user: dict, as_operator: str | None) -> str:
    """The name a write gets attributed to: the picked operator when a
    manager/admin is using Debug Mode, otherwise the caller's own name.

    Mirrors Operator_Form.py's current_user - once a manager/admin picks a
    name from the "Impersonate Operator for Testing" selector, every write
    the rest of that page makes (pours, packing, downtime, audits, notes,
    undo) is attributed to that name instead of their own, so a manager can
    log or review as if they were standing at that operator's station.
    Operators and packers can never override their own name - the override
    is silently ignored for them, the same way the selector never renders
    for them in the original.
    """
    if as_operator and as_operator.strip() and user["role"] in ("admin", "manager"):
        return as_operator.strip()
    return user["full_name"]


def require_ability(ability: str):
    """A route dependency: 403s unless the signed-in user has this ability."""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if not crud.user_can(user["id"], user["role"], ability):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep


def require_role(*roles: str):
    """A route dependency: 403s unless the signed-in user's role is listed."""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep


def require_admin_console(user: dict = Depends(get_current_user)) -> dict:
    """The Admin Panel's own gate: crud.can_administer, not a plain ability.

    Mirrors database.py's role_can_administer(role) - admin always reaches
    it, and so does a manager on a plant running in simple (logging) mode,
    where there is deliberately no separate IT role.
    """
    settings = crud.get_plant_settings()
    if not crud.can_administer(user["role"], settings.get("simple_mode", True)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_device_gateway(user: dict = Depends(require_admin_console)) -> dict:
    """Device Registry's gate: an admin console user, AND the gateway switch
    itself has to be on. Mirrors pages/Device_Registry.py's own two checks -
    kept separate from require_admin_console so a caller that only needs to
    report the switch is off (not actually list/edit devices) can still use
    require_admin_console alone and give a clear message instead of a 403.
    """
    if not bool(crud.get_plant_settings().get("enable_device_gateway", False)):
        raise HTTPException(status_code=403, detail="The hardware gateway is switched off for this plant.")
    return user
