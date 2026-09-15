"""Quality Ops Canvas, ported from pages/Mgr_Scrap_Intel.py: scrap totals,
output by formulation, and downtime by reason. Read-only, so this router is
just crud's dataframes reduced to plain numbers - the resin colours are
computed here (reusing resin_palette.py exactly as the Streamlit page does)
rather than re-implemented in the frontend, so a resin is always the same
colour everywhere no matter which side renders it.
"""
from fastapi import APIRouter, Depends

import crud
from api.deps import require_ability
from api.schemas.scrap import DowntimeReason, ResinOutput, ScrapIntelOut, ScrapTotals
from resin_palette import resin_color_map, stored_color_map

router = APIRouter(prefix="/scrap-intel", tags=["scrap-intel"])


@router.get("", response_model=ScrapIntelOut)
def scrap_intel(user: dict = Depends(require_ability("view_manager_cockpit"))):
    df_logs = crud.get_production_logs_df()
    df_dt = crud.get_downtime_logs_df()

    empty_scrap = int(df_logs["scrap_empty"].sum()) if not df_logs.empty else 0
    filled_scrap = int(df_logs["scrap_filled"].sum()) if not df_logs.empty else 0

    by_resin: list[ResinOutput] = []
    if not df_logs.empty:
        resin_grp = df_logs.groupby("resin_type")["bottles_filled"].sum().reset_index()
        colors = resin_color_map(resin_grp["resin_type"].tolist(),
                                 stored_color_map(crud.get_all_resin_specs_df("ALL")))
        by_resin = [
            ResinOutput(resin_type=row["resin_type"], bottles_filled=int(row["bottles_filled"]),
                       color=colors.get(row["resin_type"], "#9AA3AE"))
            for _, row in resin_grp.iterrows()
        ]

    downtime_by_reason: list[DowntimeReason] = []
    if not df_dt.empty:
        dt_grp = df_dt.groupby("reason")["duration_min"].sum().reset_index()
        downtime_by_reason = [
            DowntimeReason(reason=row["reason"], duration_min=float(row["duration_min"]))
            for _, row in dt_grp.iterrows()
        ]

    return ScrapIntelOut(
        totals=ScrapTotals(empty_scrap=empty_scrap, filled_scrap=filled_scrap,
                           total_scrap=empty_scrap + filled_scrap),
        by_resin=by_resin,
        downtime_by_reason=downtime_by_reason,
    )
