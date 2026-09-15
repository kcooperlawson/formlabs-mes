"""Cleanliness & Station Photo Gallery, ported from pages/Mgr_Cleanliness.py
- the manager-side review of every audit_tab.py/checklist.py photo audit.
Gated by view_manager_cockpit, same as the original.

Photos are served through /photos/{filename} rather than inlined as base64
in the audit list - a gallery can hold many, often phone-camera-sized,
photos, and a REST image endpoint lets the browser cache and lazy-load them
the normal way instead of bloating one JSON response. `filename` is
validated against path traversal (a stored filename is always a bare name
crud.py generated itself - see _audit_photo_name - never a path with
separators in it, so this is defense in depth, not something existing
data would ever trip).
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import crud
from api.deps import require_ability
from api.schemas.cleanliness import CleanlinessAuditOut, CleanlinessStats

router = APIRouter(prefix="/cleanliness", tags=["cleanliness"])


@router.get("/stats", response_model=CleanlinessStats)
def stats(user: dict = Depends(require_ability("view_manager_cockpit"))):
    df = crud.get_cleanliness_audits_df()
    if df.empty:
        return CleanlinessStats(total_audits=0, start_checks=0, end_checks=0, transfers=0, spills=0)
    return CleanlinessStats(
        total_audits=len(df),
        start_checks=int(df["audit_type"].str.contains("Start", na=False).sum()),
        end_checks=int(df["audit_type"].str.contains("End", na=False).sum()),
        transfers=int(df["audit_type"].str.contains("Transfer", na=False).sum()),
        spills=int((df["is_spill"] == "Yes").sum()),
    )


@router.get("/audits", response_model=list[CleanlinessAuditOut])
def audits(user: dict = Depends(require_ability("view_manager_cockpit"))):
    df = crud.get_cleanliness_audits_df()
    extra_photos = crud.get_cleanliness_audit_photos()
    out = []
    for _, row in df.iterrows():
        photos = [str(row["image_filename"])] if row.get("image_filename") else []
        photos += [str(f) for f in extra_photos.get(int(row["id"]), [])]
        out.append(CleanlinessAuditOut(
            id=int(row["id"]), audit_type=row["audit_type"], pump_station=row["pump_station"],
            operator_name=row["operator_name"], timestamp=row["timestamp"].isoformat() + "Z",
            notes=str(row.get("notes") or ""), is_spill=row["is_spill"] == "Yes", photos=photos,
        ))
    return out


@router.get("/photos/{filename}")
def photo(filename: str, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Not a valid filename.")
    path = os.path.join(crud.UPLOAD_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Photo not found on disk.")
    return FileResponse(path)


@router.delete("/audits/{audit_id}")
def delete(audit_id: int, user: dict = Depends(require_ability("view_manager_cockpit"))):
    ok = crud.delete_cleanliness_audit(audit_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No such audit.")
    return {"ok": True}
