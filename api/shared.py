"""Small helpers shared by more than one pouring-related router.

Rescued from the old pages/operator_form/shared.py when the Streamlit UI was
retired: most of that file was Streamlit-specific (display_lot read
st.session_state, load_lottieurl/get_base64_image existed only to feed
Streamlit's own rendering), but _vessel_label and bulk_vessel_state are pure
business logic that api/routers/checklist.py and api/routers/pouring.py
still depend on - only the file, not the logic, was Streamlit-only.
"""
import crud


def _vessel_label(v: dict) -> str:
    """How a vessel reads in a picker, including where it is now.

    A tank already sitting on another pump is offered rather than hidden, so
    the label has to say so. Hiding it is what forced a manager to move it.
    """
    tag = str(v.get("asset_tag") or "").strip()
    name = f"{v['reactor_name']} ({tag})" if tag else str(v["reactor_name"])
    on = str(v.get("current_pump") or "").strip()
    return f"{name} · currently on {on}" if on else name


def bulk_vessel_state(resin_name, pump_name):
    """Capacity and litres left for the tank feeding this station.

    Only so an amount that cannot be true can be caught at the keyboard: 1800
    typed instead of 180 looks perfectly ordinary in a number box and shows up
    an hour later as an empty vessel on the wall display. Returns (None, None)
    when no reactor is configured for this resin - an unknown tank is a reason
    to accept the number, not to refuse it.
    """
    try:
        fleet = crud.get_all_reactors_df()
        if fleet.empty:
            return None, None
        target = str(resin_name or "").strip().lower()
        for _, row in fleet.iterrows():
            if str(row.get("current_resin") or "").strip().lower() != target:
                continue
            assigned = str(row.get("assigned_pump") or "").strip()
            if assigned and assigned != "None" and assigned.lower() != str(pump_name or "").strip().lower():
                continue
            capacity = float(row.get("max_capacity_l") or 0.0)
            drawn, _ = crud.reactor_draw_litres(resin_name, assigned if assigned != "None" else "")
            return capacity, max(0.0, capacity - drawn)
    except Exception:
        # A check that cannot run must never be the reason a pour goes
        # unlogged. The record is the point; this is a courtesy on top of it.
        return None, None
    return None, None
