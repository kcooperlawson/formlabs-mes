"""Notes tab - a written note to the plant lead, ported from
pages/operator_form/notes_tab.py. Nobody is watching this in real time (see
that file's own docstring on why the caption says so) - it's read back
when a manager next opens their own copy of this screen.

Timestamps go out as plain UTC ISO 8601, not pre-formatted into a fixed
"America/New_York" string the way the Streamlit version's `st.write` loop
did - the browser's own locale/timezone is what actually matches the phone
in an operator's hand, which is the more correct behavior for any plant
this ever runs at that isn't already in US Eastern.
"""
from fastapi import APIRouter, Depends

import crud
from utils import get_avatar_data_uri
from api.deps import get_current_user, resolve_operator_name
from api.schemas.notes import NoteOut, NoteSubmitRequest

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
def list_notes(as_operator: str | None = None, user: dict = Depends(get_current_user)):
    df = crud.get_chat_history_df(resolve_operator_name(user, as_operator))
    out = []
    for _, row in df.iterrows():
        out.append(NoteOut(
            sender_name=row["sender_name"],
            message=row["message"],
            timestamp=row["timestamp"].isoformat() + "Z",
            is_manager_reply=bool(row["is_manager_reply"]),
            avatar_data_uri=get_avatar_data_uri(row.get("sender_avatar")),
        ))
    return out


@router.post("")
def send_note(body: NoteSubmitRequest, user: dict = Depends(get_current_user)):
    name = resolve_operator_name(user, body.as_operator)
    crud.send_floor_message(operator_name=name, sender_name=name, message=body.message, is_manager=False)
    return {"ok": True}
