"""The account panel every signed-in user reaches, ported from ui_shell.py's
shared "⚙️ Account & Preferences" popover (the one function used from all
eighteen Streamlit pages) - update your own name/username/PIN, upload an
avatar, pick a theme, and submit feedback to IT.

The theme dropdown DOES land here now (an earlier pass in this port left it
disabled, on the theory that one fixed Formlabs Forge look was enough - it
wasn't: different rooms and different eyes read a screen differently, and
picking your own look was the actual point for a lot of people). Unlike the
original's 34 hand-injected CSS themes, the curated set this port offers
lives entirely as data in frontend/src/palettes.ts and is applied as CSS
custom properties (frontend/src/ThemeRoot.tsx) - this endpoint only ever
stores the chosen theme's NAME on the account, exactly as
crud.update_user_theme always did, and never validates it against that list
itself (the frontend is the one place that has to agree with itself about
what's offered; an old or unrecognized name here just falls back to the
default palette when rendered).

The glove-mode/night-dim display toggles are still not ported - a separate
CSS undertaking across every component rather than an account-panel
feature.

PIN policy and username-collision checks live in crud.update_user_credentials
itself (the same function every other self-service and admin credential
path already goes through) - nothing here duplicates that logic.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

import crud
import utils
from api.deps import SESSION_COOKIE, get_current_user
from api.schemas.account import MyFeedbackOut, SubmitFeedbackRequest, UpdateCredentialsRequest, UpdateThemeRequest
from api.schemas.auth import UserOut

router = APIRouter(prefix="/account", tags=["account"])

ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024

# The original page's st.selectbox options, in the same order - the category
# picker was never validated server-side (a Streamlit selectbox can't send
# anything else); this port checks it anyway, the same way audit.py checks
# AUDIT_TYPES.
FEEDBACK_CATEGORIES = ("Feature Request", "App Bug / Error", "Plant Floor Issue", "General Feedback")


class _BufferedUpload:
    """The `.getbuffer()` shape crud.update_user_avatar expects (Streamlit's
    UploadedFile interface) - see api/uploads.py for the general version;
    this one skips the `.name` attribute update_user_avatar never reads."""
    def __init__(self, data: bytes):
        self._data = data

    def getbuffer(self) -> bytes:
        return self._data


def _opt(value):
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    return str(value)


def _iso(value):
    if value is None or (isinstance(value, float) and value != value):
        return None
    ts = pd.Timestamp(value)
    return None if pd.isna(ts) else ts.isoformat()


def _refreshed_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    user = crud.get_user_by_session_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.put("/credentials", response_model=UserOut)
def update_credentials(body: UpdateCredentialsRequest, request: Request, user: dict = Depends(get_current_user)):
    ok, msg = crud.update_user_credentials(user["id"], body.username, body.pin, body.full_name)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return _refreshed_user(request)


@router.put("/theme", response_model=UserOut)
def update_theme(body: UpdateThemeRequest, request: Request, user: dict = Depends(get_current_user)):
    if not body.theme.strip():
        raise HTTPException(status_code=400, detail="Pick a theme.")
    crud.update_user_theme(user["id"], body.theme.strip())
    return _refreshed_user(request)


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(request: Request, file: UploadFile, user: dict = Depends(get_current_user)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Avatars must be a PNG, JPG, or WEBP image.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="No file received.")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar image is too large (5 MB max).")
    filename = crud.update_user_avatar(user["id"], _BufferedUpload(data))
    if not filename:
        raise HTTPException(status_code=500, detail="Could not save avatar.")
    return _refreshed_user(request)


@router.get("/avatar/{filename}")
def avatar(filename: str, user: dict = Depends(get_current_user)):
    """Any signed-in user can view any avatar - matches the original, which
    shows avatars in the sidebar and the suggestions inbox with no ability
    check of its own. See cleanliness.py's /photos/{filename} for the same
    traversal-guard pattern this mirrors."""
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Not a valid filename.")
    path = utils.get_avatar_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return FileResponse(path)


@router.post("/feedback")
def submit_feedback(body: SubmitFeedbackRequest, user: dict = Depends(get_current_user)):
    if body.category not in FEEDBACK_CATEGORIES:
        raise HTTPException(status_code=400, detail="Not a recognized feedback category.")
    if not body.suggestion.strip():
        raise HTTPException(status_code=400, detail="Description can't be empty.")
    if not crud.add_suggestion(user["full_name"], user["role"], body.category, body.suggestion.strip()):
        raise HTTPException(status_code=500, detail="Could not submit feedback.")
    return {"ok": True}


@router.get("/feedback", response_model=list[MyFeedbackOut])
def my_feedback(user: dict = Depends(get_current_user)):
    """Matched by the submitter's current display name, same as the
    original (Suggestion has no FK to users) - a rename mid-history shows
    nothing for the old name, same limitation as everywhere else this
    name-matching is used."""
    df = crud.get_all_suggestions_df()
    if df.empty:
        return []
    mine = df[df["user_name"] == user["full_name"]]
    return [
        MyFeedbackOut(id=int(r["id"]), timestamp=_iso(r.get("timestamp")), category=r["category"],
                     suggestion=r["suggestion"], status=r["status"], admin_notes=_opt(r.get("admin_notes")))
        for _, r in mine.iterrows()
    ]
