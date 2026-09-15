"""Cartridge Lot Verification, ported from pages/Mgr_Lot_Verification.py: the
manager-side review of every lot check pouring_tab.py's lot gate logs. This
is the audit trail for the mechanic already ported in api/routers/pouring.py
(_judge_lot et al) - every check that gate makes gets a row here, pass or
fail, which is what lets a manager tell "the gate rarely runs a full check
at this station" from "the gate is fine, this exact mix-up just keeps
happening".

CSV export (a plain download button in the original) is generated
client-side from the same /checks the table already renders, using the
display columns rather than every raw SQL column (resin_spec_id,
operator_id, ocr_lot, etc.) - those foreign keys serve no one reading an
export, and the page's own "Every Check" tab never showed them either.
"""
import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import crud
from api.deps import require_ability
from api.schemas.lot_verification import (LotCheckOut, LotVerificationOut,
                                          LotVerificationTotals, OperatorCoverage,
                                          StationCoverage)
from resin_palette import resin_color

router = APIRouter(prefix="/lot-verification", tags=["lot-verification"])

ALLOWED_WINDOWS = (7, 14, 30, 90)
FLAGGED_RESULTS = ("mismatch", "expired", "rejected")


def _opt_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    s = str(value).strip()
    return s or None


def _opt_int(value) -> int | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return int(value)


@router.get("", response_model=LotVerificationOut)
def lot_verification(days: int = 30, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if days not in ALLOWED_WINDOWS:
        raise HTTPException(status_code=400, detail=f"days must be one of {ALLOWED_WINDOWS}")

    df = crud.get_lot_verifications_df(days=days)
    if df.empty:
        return LotVerificationOut(
            totals=LotVerificationTotals(checks_logged=0, full_checks=0, pct_full=0,
                                        flagged=0, cartridges_pulled=0, flag_rate=0),
            checks=[], by_operator=[], by_station=[])

    total = len(df)
    full_mask = df["check_level"] == "full"
    flagged_mask = df["result"].isin(FLAGGED_RESULTS)
    catches_mask = df["result"] == "rejected"
    full_count = int(full_mask.sum())
    flagged_count = int(flagged_mask.sum())

    totals = LotVerificationTotals(
        checks_logged=total,
        full_checks=full_count,
        pct_full=round(full_count / total * 100, 0),
        flagged=flagged_count,
        cartridges_pulled=int(catches_mask.sum()),
        flag_rate=round(flagged_count / total * 100, 1),
    )

    checks = []
    for _, row in df.sort_values("timestamp", ascending=False).iterrows():
        resin = _opt_str(row["resin_type"])
        checks.append(LotCheckOut(
            id=int(row["id"]),
            timestamp=pd.Timestamp(row["timestamp"]).isoformat() + "Z",
            operator_name=row["operator_name"],
            pump_station=row["pump_station"],
            cartridge_type=row["cartridge_type"],
            resin_type=resin,
            resin_color=resin_color(resin) if resin else None,
            expected_lot=_opt_str(row["expected_lot"]),
            entered_lot=_opt_str(row["entered_lot"]),
            result=row["result"],
            check_level=row["check_level"],
            reason=_opt_str(row["reason"]),
            production_log_id=_opt_int(row["production_log_id"]),
            photo_filename=_opt_str(row["photo_filename"]),
        ))

    by_op_df = df.groupby("operator_name").agg(
        checks=("id", "count"),
        full=("check_level", lambda s: int((s == "full").sum())),
        fast=("check_level", lambda s: int((s == "fast").sum())),
        flags=("result", lambda s: int(s.isin(FLAGGED_RESULTS).sum())),
    ).reset_index().sort_values("checks", ascending=False)
    by_operator = [
        OperatorCoverage(operator_name=r["operator_name"], checks=int(r["checks"]),
                         full=int(r["full"]), fast=int(r["fast"]), flags=int(r["flags"]),
                         pct_full=round(r["full"] / r["checks"] * 100, 0) if r["checks"] else 0)
        for _, r in by_op_df.iterrows()
    ]

    by_station_df = df.groupby("pump_station").agg(
        checks=("id", "count"),
        flags=("result", lambda s: int(s.isin(FLAGGED_RESULTS).sum())),
    ).reset_index().sort_values("flags", ascending=False)
    by_station = [
        StationCoverage(pump_station=r["pump_station"], checks=int(r["checks"]), flags=int(r["flags"]))
        for _, r in by_station_df.iterrows()
    ]

    return LotVerificationOut(totals=totals, checks=checks, by_operator=by_operator, by_station=by_station)


@router.get("/photos/{filename}")
def photo(filename: str, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Not a valid filename.")
    path = os.path.join(crud.LOT_PHOTO_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Photo not found on disk.")
    return FileResponse(path)
