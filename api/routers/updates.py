"""Auto-update: a plant PC finds out about a newer signed release on its
own and can apply it from the browser, instead of someone carrying a USB
stick in. See api/update_check.py for the GitHub-polling and apply logic
this router is a thin HTTP wrapper around, dev/update_publish.py (via
dev/make_update.py's build_release()) for the "push a release" half, and
setup/apply_update.py for the actual trusted install pipeline both the USB
path and this one now share unchanged.

Three routes:

  GET  /updates/status   - "is something newer available" (managers+admins,
                            same audience as the banner that reads this)
  POST /updates/apply    - downloads and installs the latest release
                            (admin console only - this restarts the server)
  POST /updates/publish  - builds a package from whatever has changed since
                            --from and uploads it to GitHub (admin console
                            only, and only does anything useful on a machine
                            that holds dev/update_signing_private.pem and a
                            GITHUB_RELEASE_TOKEN - see dev/update_publish.py)
"""
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api import update_check
from api.deps import require_admin_console, require_role
from api.schemas.updates import (ApplyUpdateOut, ApplyVersionRequest, AvailableUpdate,
                                 PublishUpdateOut, PublishUpdateRequest, UpdateSourceOut,
                                 UpdateSourceRequest, UpdateStatusOut)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "setup"))
sys.path.insert(0, str(ROOT / "dev"))

router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("/status", response_model=UpdateStatusOut)
def get_status(force: bool = False, user: dict = Depends(require_role("manager", "admin"))):
    return {**update_check.status(force=force),
            "publish_enabled": update_check.publish_enabled()}


@router.get("/source", response_model=UpdateSourceOut)
def get_source(user: dict = Depends(require_role("manager", "admin"))):
    return update_check.source_info()


@router.put("/source", response_model=UpdateSourceOut)
def set_source(body: UpdateSourceRequest, user: dict = Depends(require_admin_console)):
    """Point this PC at an update server - "192.168.0.15", or a full address.
    Blank goes back to GitHub. Written to this PC's .env, which no update
    ever overwrites."""
    try:
        return update_check.set_source(body.address, body.token)
    except update_check.CheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not write .env ({exc})")


@router.get("/available", response_model=list[AvailableUpdate])
def available(user: dict = Depends(require_role("manager", "admin"))):
    """Every version the source offers, newest first - older ones included,
    which is what you want on the day a new release turns out to be wrong."""
    try:
        return update_check.list_available()
    except update_check.CheckError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/apply", response_model=ApplyUpdateOut)
def apply_update_route(body: ApplyVersionRequest | None = None,
                       user: dict = Depends(require_admin_console)):
    body = body or ApplyVersionRequest()
    try:
        if body.version:
            result = update_check.apply_version(body.version, allow_older=body.allow_older)
        else:
            result = update_check.apply_latest()
    except update_check.CheckError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    mode = "manual"
    if result["ok"]:
        import self_restart  # setup/self_restart.py
        # Asked for right before this response goes out, not after: the
        # server stops a couple of seconds from now, and this response has
        # to be on its way before that happens.
        mode = self_restart.request_restart(root=ROOT)

    return ApplyUpdateOut(ok=result["ok"], version=result["version"],
                          log=result["log"], restarting=mode != "manual",
                          restart_mode=mode)


@router.post("/publish", response_model=PublishUpdateOut)
def publish_update_route(req: PublishUpdateRequest,
                         user: dict = Depends(require_admin_console)):
    if not update_check.publish_enabled():
        raise HTTPException(
            status_code=403,
            detail="Publishing is switched off on this machine. It signs a release that every "
                   "plant PC will trust, so it only runs where the signing key lives: set "
                   "MES_ALLOW_PUBLISH=1 in that PC's .env, or publish from the command line "
                   "with dev/make_update.py --publish.")

    try:
        import make_update  # dev/make_update.py
        import update_publish  # dev/update_publish.py
    except ImportError:
        # dev/ never ships in an update package, so a plant PC simply
        # doesn't have these - say that rather than raising a 500.
        raise HTTPException(status_code=409,
                            detail="This PC doesn't have the release-building tools (dev/), "
                                   "which only exist in the development copy of the project.")

    try:
        out, manifest = make_update.build_release(req.from_version, req.notes)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except FileNotFoundError as exc:
        # No signing key on this machine - see update_signing.sign()'s own
        # message, which already says exactly what to run and why.
        raise HTTPException(status_code=409, detail=str(exc))

    try:
        result = update_publish.publish_release(out, manifest)
    except update_publish.PublishError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return PublishUpdateOut(**result)
