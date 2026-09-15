"""Live Reactor Fleet - ported from pages/Live_Reactors.py. The tank wall
(GET /fleet) reuses reactor_vessel.vessel_svg() directly and ships the
rendered SVG string in the response - that function is already
"deliberately free of any Streamlit or database import" per its own
docstring, so there is real drawing code to reuse here, not just data.
React embeds it with dangerouslySetInnerHTML rather than re-implementing
tank geometry.

Access note: the original page has no explicit ability gate visible in its
own source (only check_authentication - any signed-in account that knew
the URL could reach it) - the manage_reactors gate only wraps the fleet-
editing panel and the bulk-pour panel, and mark-empty. The plain fleet VIEW
appears to rely entirely on the navigation menu not offering the link to
other roles, which is exactly the "the door and the link ask different
questions" pattern the rest of this codebase's own history warns about
(see CHANGELOG 3.39). Rather than reproduce that gap, GET /fleet here
requires view_scada - the same door Home.py itself uses for "the whole
plant at once" - so a role change to who reaches the manager UI can't
silently reopen this too.

The one-time "tank fills from empty on arrival" animation
(Live_Reactors.py's _fleet_arriving/reveal=True) is a Streamlit-page-load
nicety that doesn't translate to a page that polls every 10s - re-animating
every poll would look broken - so vessel_svg is always called with
reveal=False here.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import crud
from bulk_pour import DEFAULT_DENSITY_KG_L, check_pour, density_map, pour_litres, resin_density
from reactor_vessel import VESSEL_HELP, VESSEL_LABELS, VESSEL_TYPES, resolve_vessel_type, vessel_svg
from resin_palette import resin_color, stored_color_map
from api.deps import require_ability
from api.schemas.reactors import (
    AddReactorRequest, BatchInfo, BulkCandidate, BulkPourRequest, DrawInfo,
    ManageOptionsOut, ManageReactorRow, MarkEmptyOut, MarkFilledRequest, ReactorCard,
    UpdateReactorRequest, VesselTypeOption,
)

router = APIRouter(prefix="/reactors", tags=["reactors"])


def _s(value) -> str:
    """A DataFrame cell as a clean string, never "nan" or "None".

    pandas reads a NULL text column back as float('nan'), not None or "" -
    and nan is truthy in Python, so the usual `value or ""` idiom silently
    lets it through (nan is never falsy). Every reactor field that can be
    unset (asset_tag, bay_marker, assigned_pump, current_resin) goes through
    here before it reaches a Pydantic model or a comparison against "None".
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("none", "nan") else s


def _density_map():
    specs_df = crud.get_all_resin_specs_df("ALL")
    return (density_map(specs_df.to_dict("records"), crud.container_litres) if not specs_df.empty else {}), specs_df


@router.get("/fleet", response_model=list[ReactorCard])
def fleet(user: dict = Depends(require_ability("view_scada"))):
    df_reactors = crud.get_all_reactors_df()
    density_by_resin, specs_df = _density_map()
    colours = stored_color_map(specs_df)
    can_mark_empty = crud.user_can(user["id"], user["role"], "manage_reactors")

    out = []
    for _, reactor in df_reactors.iterrows():
        capacity_l = float(reactor["max_capacity_l"])
        r_resin = _s(reactor.get("current_resin"))
        r_pump = _s(reactor.get("assigned_pump"))
        is_idle = not r_resin

        if not is_idle:
            poured_l, lot = crud.reactor_draw_litres(r_resin, r_pump)
            remaining_l = max(0.0, capacity_l - poured_l)
            fill_pct = min(100.0, (remaining_l / capacity_l) * 100.0) if capacity_l > 0 else 100.0
            density = density_by_resin.get(r_resin.strip().lower(), DEFAULT_DENSITY_KG_L)
            remaining_kg = remaining_l * density
        else:
            fill_pct, remaining_l, remaining_kg, lot = 0.0, 0.0, 0.0, ""

        vessel_kind = resolve_vessel_type(reactor.get("vessel_type"), capacity_l)
        svg = vessel_svg(
            vessel_kind, fill_pct, capacity_l,
            resin_colour=resin_color(r_resin, colours.get(r_resin)) if not is_idle else "",
            asset_tag=_s(reactor.get("asset_tag")), bay_marker=_s(reactor.get("bay_marker")),
            idle=is_idle, key=str(reactor.get("id", "")), reveal=False,
        )

        batch_raw = crud.current_batch(reactor["reactor_name"])
        batch = BatchInfo(hours_in_reactor=batch_raw.get("hours_in_reactor"), qc_result=batch_raw.get("qc_result", ""),
                          qc_open=bool(batch_raw.get("qc_open")), hours_at_qc=batch_raw.get("hours_at_qc")) \
            if batch_raw else None

        out.append(ReactorCard(
            id=int(reactor["id"]), reactor_name=reactor["reactor_name"], capacity_l=capacity_l,
            asset_tag=_s(reactor.get("asset_tag")), bay_marker=_s(reactor.get("bay_marker")),
            current_resin=r_resin or None, assigned_pump=r_pump or None,
            is_idle=is_idle, remaining_l=remaining_l, remaining_kg=remaining_kg, fill_pct=fill_pct,
            lot=lot or "", svg=svg, batch=batch, can_mark_empty=can_mark_empty and batch is not None,
        ))
    return out


@router.get("/manage-options", response_model=ManageOptionsOut)
def manage_options(user: dict = Depends(require_ability("manage_reactors"))):
    specs_df = crud.get_all_resin_specs_df("ALL")
    resins = sorted(specs_df["resin_name"].dropna().astype(str).unique().tolist()) if not specs_df.empty else []
    settings = crud.get_plant_settings()
    return ManageOptionsOut(
        vessel_types=[VesselTypeOption(value=v, label=VESSEL_LABELS[v], help=VESSEL_HELP[v]) for v in VESSEL_TYPES],
        resins=resins, pumps=crud.get_active_pumps(),
        bulk_enabled=bool(settings.get("enable_bulk_pour", False)),
    )


@router.get("/manage-list", response_model=list[ManageReactorRow])
def manage_list(user: dict = Depends(require_ability("manage_reactors"))):
    df = crud.get_all_reactors_df()
    return [ManageReactorRow(
        id=int(r["id"]), reactor_name=r["reactor_name"], capacity_l=float(r["max_capacity_l"]),
        vessel_type=resolve_vessel_type(r.get("vessel_type"), r["max_capacity_l"]),
        asset_tag=_s(r.get("asset_tag")), bay_marker=_s(r.get("bay_marker")),
        assigned_pump=_s(r.get("assigned_pump")), current_resin=_s(r.get("current_resin")),
    ) for _, r in df.iterrows()]


@router.post("", status_code=201)
def add(body: AddReactorRequest, user: dict = Depends(require_ability("manage_reactors"))):
    if not body.reactor_name.strip():
        raise HTTPException(status_code=400, detail="Name the reactor.")
    crud.add_reactor(body.reactor_name, int(body.max_capacity_l), vessel_type=body.vessel_type,
                     asset_tag=body.asset_tag, bay_marker=body.bay_marker)
    return {"ok": True}


@router.delete("/{reactor_id}")
def remove(reactor_id: int, user: dict = Depends(require_ability("manage_reactors"))):
    crud.delete_reactor(reactor_id)
    return {"ok": True}


@router.put("/{reactor_id}")
def update(reactor_id: int, body: UpdateReactorRequest, user: dict = Depends(require_ability("manage_reactors"))):
    crud.update_reactor_identity(reactor_id, vessel_type=body.vessel_type, asset_tag=body.asset_tag,
                                 bay_marker=body.bay_marker)
    crud.update_reactor_config(reactor_id, body.current_resin, body.assigned_pump)
    return {"ok": True}


@router.get("/bulk-candidates", response_model=list[BulkCandidate])
def bulk_candidates(user: dict = Depends(require_ability("manage_reactors"))):
    df = crud.get_all_reactors_df()
    out = []
    for _, r in df.iterrows():
        resin = _s(r.get("current_resin"))
        if not resin:
            continue
        tag = _s(r.get("asset_tag"))
        label = f"{tag + ' — ' if tag else ''}{r['reactor_name']} · {resin}"
        out.append(BulkCandidate(id=int(r["id"]), reactor_name=r["reactor_name"], label=label,
                                 current_resin=resin))
    return out


def _live_reactor_row(reactor_id: int):
    """The reactor row for a bulk-pour target, or a 404/400 if it can't be one."""
    df = crud.get_all_reactors_df()
    row = df[df["id"] == reactor_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="No such reactor.")
    r = row.iloc[0]
    resin = _s(r.get("current_resin"))
    if not resin:
        raise HTTPException(status_code=400, detail="That reactor has no resin assigned yet.")
    return r, resin, _s(r.get("assigned_pump"))


@router.get("/{reactor_id}/draw-info", response_model=DrawInfo)
def draw_info(reactor_id: int, user: dict = Depends(require_ability("manage_reactors"))):
    r, resin, pump = _live_reactor_row(reactor_id)
    capacity_l = float(r["max_capacity_l"])
    drawn, lot = crud.reactor_draw_litres(resin, pump)
    density_by_resin, _ = _density_map()
    density = resin_density(resin, density_by_resin)
    return DrawInfo(capacity_l=capacity_l, current_resin=resin, lot=lot or "",
                    remaining_l=max(0.0, capacity_l - drawn), density_kg_l=density)


@router.post("/{reactor_id}/bulk-pour")
def bulk_pour(reactor_id: int, body: BulkPourRequest, user: dict = Depends(require_ability("manage_reactors"))):
    r, resin, pump = _live_reactor_row(reactor_id)
    capacity_l = float(r["max_capacity_l"])
    drawn, lot = crud.reactor_draw_litres(resin, pump)
    remaining_l = max(0.0, capacity_l - drawn)
    density_by_resin, _ = _density_map()
    density = resin_density(resin, density_by_resin)
    litres = pour_litres(body.containers, body.amount_each, body.unit, density)
    verdict = check_pour(litres, capacity_l=capacity_l, remaining_l=remaining_l)
    if verdict["blocked"]:
        raise HTTPException(status_code=400, detail=verdict["message"] or "That amount can't be logged.")

    crud.add_hourly_log(
        operator_name=user["full_name"], pump_station=pump or str(r["reactor_name"]),
        shift=user["shift"] or "", cartridge_type="Bulk", resin_type=resin, lot_number=lot or "",
        bottles=int(body.containers), scrap_empty=0, scrap_filled=0,
        notes="Bulk pour logged from the reactor page.", litres_poured=litres, pour_note=body.note,
    )
    return {"ok": True, "litres": litres}


@router.post("/{reactor_id}/mark-empty", response_model=MarkEmptyOut)
def mark_empty(reactor_id: int, user: dict = Depends(require_ability("manage_reactors"))):
    df = crud.get_all_reactors_df()
    row = df[df["id"] == reactor_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="No such reactor.")
    ok = crud.close_batch(row.iloc[0]["reactor_name"], by=user["full_name"])
    return MarkEmptyOut(ok=ok)


@router.post("/{reactor_id}/mark-filled", response_model=MarkEmptyOut)
def mark_filled(reactor_id: int, body: MarkFilledRequest, user: dict = Depends(require_ability("manage_reactors"))):
    if not body.resin_type.strip():
        raise HTTPException(status_code=400, detail="Pick a resin.")
    df = crud.get_all_reactors_df()
    row = df[df["id"] == reactor_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="No such reactor.")
    filled_at = None
    if body.filled_at:
        try:
            filled_at = datetime.fromisoformat(body.filled_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="filled_at must be ISO 8601.")
    ok = crud.mark_reactor_filled(
        row.iloc[0]["reactor_name"], body.resin_type, lot_number=body.lot_number,
        filled_at=filled_at, by=user["full_name"], note=body.note,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not mark that reactor filled.")
    return MarkEmptyOut(ok=ok)
