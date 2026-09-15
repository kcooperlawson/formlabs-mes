"""Notes from the Floor - the manager side of the Notes tab, ported from
pages/Mgr_Floor_Comms.py. Reuses api/schemas/notes.py's NoteOut for the
thread response, since it's the exact same crud.get_chat_history_df/
send_floor_message plumbing the operator side (api/routers/notes.py) uses -
just keyed by whichever operator the manager picks instead of "yourself".

One pre-existing quirk preserved exactly, not fixed here: every manager's
reply is attributed to the literal sender_name "Plant Lead" (Mgr_Floor_
Comms.py:87), regardless of which manager account sent it. Changing that
is a real product decision (do operators want to know WHICH manager
replied?), not something to slip in as a side effect of this port.
"""
from fastapi import APIRouter, Depends

import crud
from api.deps import require_ability
from api.schemas.floor_comms import FloorReplyRequest, OperatorThreadSummary
from api.schemas.notes import NoteOut
from utils import get_avatar_data_uri

router = APIRouter(prefix="/floor-comms", tags=["floor-comms"])


@router.get("/operators", response_model=list[OperatorThreadSummary])
def operators(user: dict = Depends(require_ability("view_manager_cockpit"))):
    written = set(crud.get_operators_with_messages())
    all_ops = set(crud.get_active_operators()) - {"No Operators Found"}
    names = sorted(written | all_ops)
    return [OperatorThreadSummary(name=n, has_written=n in written) for n in names]


@router.get("/thread", response_model=list[NoteOut])
def thread(operator_name: str, user: dict = Depends(require_ability("view_manager_cockpit"))):
    df = crud.get_chat_history_df(operator_name)
    out = []
    for _, row in df.iterrows():
        out.append(NoteOut(
            sender_name=row["sender_name"], message=row["message"],
            timestamp=row["timestamp"].isoformat() + "Z",
            is_manager_reply=bool(row["is_manager_reply"]),
            avatar_data_uri=get_avatar_data_uri(row.get("sender_avatar")),
        ))
    return out


@router.post("/reply")
def reply(body: FloorReplyRequest, user: dict = Depends(require_ability("view_manager_cockpit"))):
    crud.send_floor_message(operator_name=body.operator_name, sender_name="Plant Lead",
                            message=body.message, is_manager=True)
    return {"ok": True}
