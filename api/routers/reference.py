"""Read-only lookups the Operator Form needs before it can render anything:
pumps, resin specs, downtime reasons, the floor-relevant plant settings, and
an operator's last picks.

Mirrors database.py's @st.cache_data-wrapped reads, minus the Streamlit-only
caching decorator - TanStack Query does the equivalent job on the frontend
(request caching/dedup), so there is nothing to reimplement here.

/resins and /resin-lookup intentionally return the same shape from the same
query: /resins backs the inline target-weight caption every station/resin
picker shows today with no ability check at all (see pouring_tab.py), while
/resin-lookup backs the separate searchable "Station Tools -> Resin Lookup"
table and stays behind view_resin_lookup, matching Finding 11 in the
security posture doc. Neither ever includes sku/resin_code - the full
table with those stays manager-only, behind manage_resins, unchanged.
"""
from pathlib import Path

from fastapi import APIRouter, Depends

import crud
from resin_palette import resin_colors, stored_color_map
from api.deps import get_current_user, require_ability, require_role, resolve_operator_name
from api.schemas.reference import LastPicksOut, PlantSettingsPublic, ResinColor, ResinSpecOut

router = APIRouter(tags=["reference"])

_VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "VERSION"


def _resin_specs_out(cartridge_filter: str = "ALL") -> list[ResinSpecOut]:
    df = crud.get_all_resin_specs_df(cartridge_filter)
    colour_map = stored_color_map(df)
    out = []
    for _, row in df.iterrows():
        bg, fg, border = resin_colors(row["resin_name"], colour_map.get(str(row["resin_name"])))
        out.append(ResinSpecOut(
            cartridge_type=row["cartridge_type"],
            resin_name=row["resin_name"],
            target_g=row["actual_spec_g"],
            min_g=row["min_weight_g"],
            max_g=row["max_weight_g"],
            target_kg=round(row["actual_spec_g"] / 1000.0, 4),
            units_per_skid=int(row.get("units_per_skid") or 500),
            color=ResinColor(bg=bg, fg=fg, border=border),
        ))
    return out


@router.get("/reference/pumps", response_model=list[str])
def pumps(user: dict = Depends(get_current_user)):
    return crud.get_active_pumps()


@router.get("/reference/container-formats")
def container_formats(bulk_enabled: bool = False, user: dict = Depends(get_current_user)):
    """The Container Format picker's options, and the label->code mapping
    (crud.CONTAINER_FORMATS) the pouring submit endpoint expects a `code`
    from - kept server-side so the frontend never has to duplicate the
    substring-matching bug format_code's own docstring warns about."""
    labels = crud.format_choices(bulk_enabled)
    return {"labels": list(labels), "codes": {label: crud.format_code(label) for label in labels}}


@router.get("/reference/resins", response_model=list[ResinSpecOut])
def resins(user: dict = Depends(get_current_user)):
    return _resin_specs_out("ALL")


@router.get("/reference/resin-lookup", response_model=list[ResinSpecOut])
def resin_lookup(user: dict = Depends(require_ability("view_resin_lookup"))):
    return _resin_specs_out("ALL")


@router.get("/reference/downtime-reasons", response_model=list[str])
def downtime_reasons(user: dict = Depends(get_current_user)):
    return crud.get_downtime_reasons()


@router.get("/reference/active-operators", response_model=list[str])
def active_operators(user: dict = Depends(require_role("manager", "admin"))):
    """Backs the "Impersonate Operator for Testing" picker in Debug Mode -
    manager/admin only, matching Operator_Form.py's own selector, which
    only ever renders for those two roles."""
    return [n for n in crud.get_active_operators() if n != "No Operators Found"]


@router.get("/reference/plant-settings", response_model=PlantSettingsPublic)
def plant_settings(user: dict = Depends(get_current_user)):
    s = crud.get_plant_settings()
    return PlantSettingsPublic(
        simple_mode=s["simple_mode"],
        enable_bulk_pour=s["enable_bulk_pour"],
        enable_packing=s["enable_packing"],
        enable_device_gateway=bool(s.get("enable_device_gateway", False)),
        pump_form_url=s["pump_form_url"],
        pump_form_label=s["pump_form_label"],
    )


@router.get("/reference/user/last-picks", response_model=LastPicksOut)
def last_picks(as_operator: str | None = None, user: dict = Depends(get_current_user)):
    return crud.get_last_picks(resolve_operator_name(user, as_operator))


@router.get("/reference/app-version")
def app_version():
    """What update_guide.html tells the reader to check after a rollback -
    "the version is printed at the bottom of the sidebar" - which needs
    something on this end to print. No auth: knowing the version isn't
    sensitive, and a login screen crash is exactly when someone would want
    to check it.
    """
    try:
        return {"version": _VERSION_FILE.read_text(encoding="utf-8").strip()}
    except OSError:
        return {"version": ""}
