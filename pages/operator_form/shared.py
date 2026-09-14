"""Small helpers shared by more than one tab (or by the page chrome).

Moved out of Operator_Form.py verbatim - none of the logic below changed
in the split, only where it lives.
"""
import base64

import streamlit as st
import requests

from database import get_all_reactors_df, reactor_draw_litres


def _vessel_label(v: dict) -> str:
    """How a vessel reads in a picker, including where it is now.

    A tank already sitting on another pump is offered rather than hidden, so
    the label has to say so. Hiding it is what forced a manager to move it.
    """
    tag = str(v.get("asset_tag") or "").strip()
    name = f"{v['reactor_name']} ({tag})" if tag else str(v["reactor_name"])
    on = str(v.get("current_pump") or "").strip()
    return f"{name} · currently on {on}" if on else name


def display_lot(lot_value, cartridge_type=None):
    """Blind the run's lot for the people who have to read it off the container.

    `cartridge_type` used to buy an exemption for RPS, on the understanding
    that bulk jugs carried no label. They always have, and the plant now
    requires the tag to be on the jug before pouring, so the jug is read the
    same way a cartridge is - which means showing its lot on screen would
    defeat the check on that format exactly as it would on any other. The
    parameter is kept because callers pass it and a future format really might
    have nothing to read.
    """
    lot = str(lot_value or "N/A")
    if str(st.session_state.get("user_role", "operator")) in ("manager", "admin"):
        return lot
    return "•" * 9 if lot not in ("", "N/A", "None") else lot


def bulk_vessel_state(resin_name, pump_name):
    """Capacity and litres left for the tank feeding this station.

    Only so an amount that cannot be true can be caught at the keyboard: 1800
    typed instead of 180 looks perfectly ordinary in a number box and shows up
    an hour later as an empty vessel on the wall display. Returns (None, None)
    when no reactor is configured for this resin - an unknown tank is a reason
    to accept the number, not to refuse it.
    """
    try:
        fleet = get_all_reactors_df()
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
            drawn, _ = reactor_draw_litres(resin_name, assigned if assigned != "None" else "")
            return capacity, max(0.0, capacity - drawn)
    except Exception:
        # A check that cannot run must never be the reason a pour goes
        # unlogged. The record is the point; this is a courtesy on top of it.
        return None, None
    return None, None


def load_lottieurl(url):
    """Fetch the run-complete animation without ever taking the page down.

    This runs while the page script is still loading, so an unguarded
    requests.get here is a single point of failure for the whole operator
    terminal: a slow CDN, a proxy, or a plant PC that has lost its internet
    would hang the page and then raise before one widget rendered. The
    animation is decoration; the terminal is not. Every caller already
    checks `if lottie_success:` before rendering, so None is safe.
    """
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""
