
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import types

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# --- NEW IMPORTS FOR ANIMATION ---
# st_lottie is the actual render function this page calls (see the
# "Mark Done" button below) — `import streamlit_lottie` alone only binds
# the module name, not st_lottie itself, which is what was crashing every
# "Mark Done" click with NameError: name 'st_lottie' is not defined.
from streamlit_lottie import st_lottie

from database import (
    get_assigned_runs_df,
    update_assigned_run_progress,
    update_run_status,
    get_all_resin_specs_df,
    container_litres,
    get_active_pumps,
    get_downtime_reasons,
    get_active_operators,
    get_production_logs_df,
    get_all_reactors_df,
    reconcile_reactor_liters,
    update_user_role_and_shift,
    get_plant_settings,
    can,
    set_cookie,
    draw_flashes,
    do_logout,
    check_authentication,
)
from database import esc
from print_build import screen_sweep
from components import empty_state, render_feedback_box
from resin_palette import resin_chip, resin_colors, stored_color_map
from shifts import picker_options as shift_picker_options
import external_links
from bulk_pour import density_map

from pages.operator_form.shared import (
    display_lot as _display_lot,
    get_base64_image,
    load_lottieurl,
)
from pages.operator_form import (
    checklist, pouring_tab, packing_tab, downtime_tab, audit_tab, notes_tab, summary_tab,
)

import extra_streamlit_components as stx
cookie_manager = stx.CookieManager(key="op_cookies")

# Fetched once per session rather than on every rerun - Streamlit re-executes
# this script top to bottom on every widget interaction, and an operator
# should not be waiting on a CDN round trip each time they touch a number.
if "lottie_success" not in st.session_state:
    st.session_state["lottie_success"] = load_lottieurl(
        "https://assets10.lottiefiles.com/packages/lf20_lk80fpsm.json")
lottie_success = st.session_state["lottie_success"]

logo_b64 = get_base64_image("assets/formlabs_logo.png")

st.set_page_config(page_title="Pouring Log | Formlabs", page_icon="static/app-icon.png", layout="wide")


st.logo("assets/formlabs_logo.png")

# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {"Formlabs Forge": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Formlabs Forge")
if active_theme not in THEMES:
    active_theme = "Formlabs Forge"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
# ===================================================================

st.markdown(f"""
<div style="display:flex; align-items:center; margin-bottom: 5px;">
    <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain; margin-right: 15px;">
    <h1 style="margin:0; padding:0; font-size: clamp(1.25rem, 4.2vw, 2.2rem); white-space: nowrap;">📝 Operator Workstation</h1>
    <!-- The guide, one tap away and out of the way. Top right, small, opens in
         its own tab so nothing half-typed on this page is lost. It is the
         eleven-page guide written to be read at the pump, not the handbook -
         an operator has no use for the manager's document. -->
    <a href="./app/static/Formlabs_MES_Operator_Guide.pdf" target="_blank"
       title="Operator guide — how to log an hour, and what to do when something is not right"
       style="margin-left:auto; flex:0 0 auto; width:38px; height:38px;
              display:flex; align-items:center; justify-content:center;
              border-radius:50%; border:1px solid currentColor; opacity:0.45;
              color:inherit; text-decoration:none; font-weight:800;
              font-size:1.05rem;">?</a>
</div>
""", unsafe_allow_html=True)

# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

# 1. Initialize User & Role FIRST
current_user = st.session_state.get("user_name") or "Keagan C."
current_role = st.session_state.get("user_role") or "operator"
current_shift = st.session_state.get("user_shift") or "Shift 1"

# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

from ui_shell import nav_bar
nav_bar()


# ===================== SIDEBAR: PROFILE & SETTINGS =====================
with st.sidebar:
    st.markdown("---")
    from database import get_avatar_path
    _avatar_path = get_avatar_path(st.session_state.get("avatar_filename"))
    if _avatar_path:
        _av_col, _name_col = st.columns([1, 4])
        with _av_col:
            st.image(_avatar_path, width=48)
        with _name_col:
            st.markdown(f"### {st.session_state.get('user_name', 'Operator')}")
    else:
        st.markdown(f"### 👤 {st.session_state.get('user_name', 'Operator')}")
    st.caption(
        f"Role: `{str(st.session_state.get('user_role', 'unknown')).upper()}` | Shift: `{st.session_state.get('user_shift', 'Unknown')}`")

    # nav_menu() (ui_shell.py) already appends an "IT Admin" link here
    # whenever role_can_administer() is true - see ui_shell.nav_links(). A
    # second, separately-gated IT Admin link used to be added right after it
    # by hand, so a manager/admin viewing this page saw the same destination
    # listed twice in one sidebar. Removed rather than re-added: one list,
    # one place it's built, same as every other page's sidebar.
    from ui_shell import nav_menu
    nav_menu()

    st.markdown("---")
    # --------------------------

    # UNIFIED SETTINGS POPOVER
    with st.popover("⚙️ Account & Preferences", use_container_width=True):
        set_tab1, set_tab2, set_tab3 = st.tabs(["🔑 Security", "🎨 Theme & Avatar", "💡 Feedback"])

        # TAB 1: USERNAME & PIN
        with set_tab1:
            st.markdown("#### Update Account Credentials")
            with st.form("user_cred_form"):
                acc_name = st.text_input("Full Display Name", value=st.session_state.get("user_name", ""))
                acc_user = st.text_input("Username / ID", value=st.session_state.get("username", ""))
                acc_pin = st.text_input("New PIN / Password", type="password",
                                        placeholder="Leave blank to keep current PIN")

                if st.form_submit_button("💾 Save Credentials", type="primary", use_container_width=True):
                    from database import update_user_credentials

                    success, msg = update_user_credentials(
                        user_id=st.session_state["user_id"],
                        new_username=acc_user,
                        new_pin=acc_pin,
                        new_fullname=acc_name
                    )
                    if success:
                        st.session_state["user_name"] = acc_name.strip()
                        st.session_state["username"] = acc_user.lower().strip()
                        st.toast(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # TAB 2: THEME & AVATAR
        with set_tab2:
            st.markdown("#### Interface Preferences")
            current_t = st.session_state.get("preferred_theme", "Formlabs Forge")
            chosen_t = st.selectbox("System Theme", list(THEMES.keys()),
                                    index=list(THEMES.keys()).index(current_t) if current_t in THEMES else 0)

            if chosen_t != current_t:
                from database import update_user_theme

                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
                set_cookie(cookie_manager, "formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
                st.rerun()

            st.markdown("---")
            st.markdown("#### Display")
            # Stored on the DEVICE, not the account - same cookie names and
            # same logic as ui_shell.render_shell()'s copy of this, which is
            # what every manager-side page already offers. This page never
            # had it: an operator standing at a pump with gloves on, or
            # working a night shift, had no way to reach either setting from
            # the one page they actually use. Glove mode is a property of
            # where you are standing, not of who you are - a shared floor
            # terminal wants big targets for whoever signs in next, and the
            # same person at a desk with a mouse wants the density back.
            # Tying it to the login would get it wrong for both.
            _glove_now = st.session_state.get("glove_mode", False)
            _glove = st.toggle(
                "🧤 Glove mode", value=_glove_now,
                help="Larger buttons, inputs and steppers for gloved hands. "
                     "Remembered for this terminal, not for your account.")
            if _glove != _glove_now:
                st.session_state["glove_mode"] = _glove
                set_cookie(cookie_manager, "formlabs_mes_glove", "1" if _glove else "0",
                                   expires_at=datetime.now() + timedelta(days=365),
                                   key="glove_cookie_set")
                st.rerun()

            _dim_now = st.session_state.get("night_dim", True)
            _dim = st.toggle(
                "🌙 Dim outside the day shift", value=_dim_now,
                help="Takes the glare off the screen once the day shift ends, "
                     "using the shift times set in the admin panel. Colours are "
                     "kept intact so the lot check still reads correctly.")
            if _dim != _dim_now:
                st.session_state["night_dim"] = _dim
                set_cookie(cookie_manager, "formlabs_mes_dim", "1" if _dim else "0",
                                   expires_at=datetime.now() + timedelta(days=365),
                                   key="dim_cookie_set")
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            _current_avatar = get_avatar_path(st.session_state.get("avatar_filename"))
            if _current_avatar:
                st.image(_current_avatar, width=64, caption="Current Avatar")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar

                    st.session_state["avatar_filename"] = update_user_avatar(st.session_state["user_id"], new_avatar)
                    st.toast("✅ Avatar updated!")
                    st.rerun()

        # TAB 3: FEEDBACK & CHANGELOG
        with set_tab3:
            render_feedback_box(st.session_state.get("user_name"), st.session_state.get("user_role"))

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LAUNCH TV MODE ---
    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        # switch_page raises to navigate, so an st.rerun() after it never ran.
        st.switch_page("Home.py")


# ===================== MANAGER & ADMIN DEBUG / IMPERSONATION MODE =====================
if current_role in ["manager", "admin"]:
    st.markdown("""
    <div style='background-color: rgba(245, 158, 11, 0.1); border: 1px solid #F59E0B; border-radius: 8px; padding: 12px; margin-bottom: 16px;'>
        <b style='color: #F59E0B;'>🛠️ Superuser Debug Mode Active</b><br>
        <span style='color: #E2E8F0; font-size: 0.85rem;'>Signed in as Management/Admin. Select an operator below to view their active runs and submit logs for system testing.</span>
    </div>
    """, unsafe_allow_html=True)

    op_list = get_active_operators()
    if current_user not in op_list:
        op_list.insert(0, current_user)

    current_user = st.selectbox("Impersonate Operator for Testing:", op_list)
else:
    st.caption(f"Logged in as: **{current_user}** ({current_role.upper()}) | Live Machine Sync Active")

# ===================== PERSONALIZED TODAY'S STATS =====================
df_logs = get_production_logs_df()
today_str = date.today().strftime("%Y-%m-%d")

if not df_logs.empty:
    df_logs["date_str"] = pd.to_datetime(df_logs["date"]).dt.strftime("%Y-%m-%d")
    df_today = df_logs[df_logs["date_str"] == today_str]
else:
    df_today = pd.DataFrame()

if current_role != "manager" and not df_today.empty:
    df_today = df_today[df_today["operator_name"] == current_user]

poured_df = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
packed_df = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

poured_units = int(poured_df["bottles_filled"].sum()) if not poured_df.empty else 0
packed_units = int(packed_df["bottles_filled"].sum()) if not packed_df.empty else 0
scrap_units = int(poured_df["scrap_empty"].sum() + poured_df["scrap_filled"].sum()) if not poured_df.empty else 0

st.markdown(f"### 📊 Today's Performance: {current_user if current_role != 'manager' else 'Plant-Wide'}")

if current_role == "operator":
    c1, c2, c3 = st.columns(3)
    c1.metric("🧪 Units Poured", f"{poured_units:,}")
    c2.metric("🗑️ Scrap Units", f"{scrap_units:,}")
    c3.metric("✅ Quality Yield", f"{(poured_units / (poured_units + scrap_units) * 100):.1f}%" if (poured_units + scrap_units) > 0 else "100.0%")
elif current_role == "packer":
    c1, c2 = st.columns(2)
    c1.metric("📦 Units Packed", f"{packed_units:,}")
    c2.metric("⏳ Shift Status", "On Track")
elif current_role == "manager":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🧪 Plant Units Poured", f"{poured_units:,}")
    c2.metric("📦 Plant Units Packed", f"{packed_units:,}")
    c3.metric("⏳ Floor WIP (Unpacked)", f"{poured_units - packed_units:,}", delta="Pending Pack-Out", delta_color="off")
    c4.metric("✅ Quality Yield", f"{(poured_units / (poured_units + scrap_units) * 100):.1f}%" if (poured_units + scrap_units) > 0 else "100.0%")

st.markdown("---")

# Anything the previous run confirmed - a log submitted, a photo audit filed,
# a checklist cleared. Drawn here, above both the checklist gate and the
# logging tabs, so it is in the same place whichever state the operator is in
# and cannot be missed by somebody who has scrolled. See utils.flash: these
# used to be toasts, which a phone lost entirely.
if st.session_state.pop("_unlock_sweep", False):
    st.markdown(screen_sweep(uid="unlock", seconds="1.5s"), unsafe_allow_html=True)

draw_flashes()

# ===================== THE HARD GATE: DAILY STARTUP CHECKLIST =====================
# This calls st.stop() internally and never returns if the checklist for
# this operator/shift/station is not yet complete - see
# pages/operator_form/checklist.py.
_checklist_ctx = types.SimpleNamespace(
    current_role=current_role,
    current_user=current_user,
    current_shift=current_shift,
    cookie_manager=cookie_manager,
)
checklist.render_checklist_gate(_checklist_ctx)

df_runs = get_assigned_runs_df()

# Does this plant dispatch work orders at all? Off by default - see migration
# 0009. Blanking the frame here rather than testing the setting at each of the
# four places that read it means there is one answer for the whole page: no
# run cards, no "no run matched" notice, and - the part that matters - the lot
# check compares against nothing rather than against a run the operator was
# never shown. A stale run left open in the database cannot reach out and stop
# a pour on a terminal that has no way to display it.
simple_mode = bool(get_plant_settings().get("simple_mode", True))
if simple_mode and not df_runs.empty:
    df_runs = df_runs.iloc[0:0]

active_pumps = get_active_pumps()
dt_reasons = get_downtime_reasons()

# Resin colours for this render. get_all_resin_specs_df is cached, so this
# costs nothing extra, and resolving them in one place means every resin on
# this page - run cards, tank cards, the pouring selection, the packing tab -
# carries the same colour it carries on every other screen.
resin_colour_map = stored_color_map(get_all_resin_specs_df("ALL"))

# --- pours that are an amount rather than a count ----------------------------
# Off unless the plant has switched it on, and when it is off nothing below
# this line runs and the form is byte for byte the form it has always been.
bulk_pour_enabled = bool(get_plant_settings().get("enable_bulk_pour", False))
bulk_densities = (density_map(get_all_resin_specs_df("ALL").to_dict("records"),
                              container_litres)
                  if bulk_pour_enabled else {})

# ===================== MY STATION (multi-pourer support) =====================
# Which station's runs show in Section 1 below. Deliberately independent
# of AssignedRun.assigned_operator: any number of operators can point at
# the same station and all see — and log against — the exact same run,
# with no extra assignment needed from the manager.
#
# No separate "pick your station" widget here anymore — that was a
# redundant second click on top of the Hourly Pouring tab's own "Pump
# Station" selector (key="h_pump") further down. That selector now IS the
# station picker: Streamlit reruns this whole script top-to-bottom on
# every widget interaction and keeps a keyed widget's value in
# st.session_state across reruns, so the moment an operator changes "Pump
# Station" in that tab, the very next rerun sees the new value in
# st.session_state["h_pump"] — and Section 1 above that tab picks it up
# immediately, since Section 1 filters on `my_station` (set here from that
# same session_state key). We only need a sensible default before that
# widget has ever been rendered.
if current_role != "packer":
    station_cookie_name = f"op_station_{current_user.replace(' ', '')}"
    station_options = active_pumps if active_pumps else ["New Pump #1"]

    if "h_pump" not in st.session_state:
        saved_station = cookie_manager.get(station_cookie_name)
        st.session_state["h_pump"] = saved_station if saved_station in station_options else station_options[0]

    my_station = (st.session_state["h_pump"]
                  if st.session_state.get("h_pump") in station_options else station_options[0])

    # Keep the "remember for next time" cookie in sync whenever the
    # Hourly Pouring station selector changes.
    #
    # `cookie_manager.cookies` is empty until the manager component has
    # reported back, which it has not done on the first run of a fresh page
    # load. Writing then would compare against nothing, decide the cookie is
    # wrong, and re-write it - costing every operator the settle wait in
    # set_cookie on a screen they open all shift, for a value that was
    # already correct.
    if cookie_manager.cookies and cookie_manager.get(station_cookie_name) != my_station:
        set_cookie(cookie_manager, station_cookie_name, my_station, expires_at=datetime.now() + timedelta(days=90))
else:
    # Packing only ever has the one shared station — see the Packing tab
    # further down — so there's nothing to pick.
    my_station = "Pack-Out Station"

st.markdown("---")

# ===================== SECTION 1: ACTIVE ASSIGNED RUNS =====================
# ===================== FOCUS MODE =====================
# Four numbers, large enough to read from a few feet away, and nothing else.
#
# During a pour the operator is at the pump, not at the screen. Everything
# they need mid-run is which resin, which lot, how many so far and how far to
# go - and on the full page those four facts are scattered between a card, a
# progress bar and a form, at a size that means walking over and leaning in.
# This is the same data, laid out to be read at a glance and then ignored.
#
# Deliberately a toggle rather than a separate page: it has to be one tap to
# leave, because the moment they need it is the moment they need to log.
#
# Only offered when there is actually something at THIS station to look at.
# It used to be offered in every non-simple-mode plant regardless, which
# meant an operator at a station with nothing running could turn it on and
# land on the exact "nothing running here" empty state below - the control's
# only possible outcome was a message about something not happening, which
# is worse than no control being there at all. Computing the same active-run
# lookup Section 1 below already needs, once, up front, means the toggle
# itself now only appears when it can actually do something.
_my_station_runs = df_runs[
    (df_runs["pump_station"].astype(str).str.strip().str.lower() == str(my_station).strip().lower())
    & (df_runs["status"].isin(["Active", "Pouring"]))
] if not simple_mode and not df_runs.empty else df_runs.iloc[0:0]

_focus = False
if not simple_mode and not _my_station_runs.empty:
    _focus = st.toggle("🔍 Focus mode — big numbers, nothing else", value=False,
                       key="focus_mode",
                       help="For reading from across the station while you pour.")

if _focus:
    # The toggle above only renders when _my_station_runs is already
    # non-empty, so there is nothing to check here - unlike the old version
    # of this block, this one can never land on an empty state.
    for _, _r in _my_station_runs.iterrows():
        _target = int(_r["target_units"] or 0)
        _done = int(_r["current_units"] or 0)
        _left = max(0, _target - _done)
        _pct = min(100.0, (_done / _target * 100.0)) if _target else 0.0
        _bg, _fg, _bd = resin_colors(_r["resin_type"], resin_colour_map.get(str(_r["resin_type"])))
        st.markdown(f"""
<div style="border:2px solid {_bd};border-radius:14px;padding:22px 26px;margin-bottom:14px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px;">
    <div>
      <div style="font-size:0.75rem;letter-spacing:.16em;text-transform:uppercase;opacity:.6;">Resin</div>
      <div style="background-color:{_bg};color:{_fg};border:1px solid {_bd};border-radius:10px;
                  padding:6px 18px;font-size:2.0rem;font-weight:800;display:inline-block;margin-top:4px;">
        {esc(_r['resin_type'])}</div>
    </div>
    <div>
      <div style="font-size:0.75rem;letter-spacing:.16em;text-transform:uppercase;opacity:.6;">Lot</div>
      <div style="font-size:2.0rem;font-weight:800;font-family:monospace;margin-top:6px;">
        {_display_lot(_r.get('lot_number'), _r.get('cartridge_type'))}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.75rem;letter-spacing:.16em;text-transform:uppercase;opacity:.6;">Poured</div>
      <div style="font-size:3.4rem;font-weight:900;line-height:1;margin-top:2px;">{_done:,}</div>
      <div style="font-size:0.95rem;opacity:.7;">of {_target:,}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.75rem;letter-spacing:.16em;text-transform:uppercase;opacity:.6;">Left</div>
      <div style="font-size:3.4rem;font-weight:900;line-height:1;margin-top:2px;">{_left:,}</div>
      <div style="font-size:0.95rem;opacity:.7;">{_pct:.0f}% done</div>
    </div>
  </div>
  <div style="background:rgba(128,128,128,0.25);border-radius:10px;height:22px;margin-top:20px;overflow:hidden;">
    <div style="width:{_pct}%;height:100%;background:{_bd};transition:width .4s ease;"></div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.caption("Turn focus mode off to log, record downtime or run a cleanliness check.")
    st.stop()

# Nothing above the log unless there is something to say. A plant that does
# not dispatch work orders, and a plant that has not dispatched one yet, both
# used to get a heading with a manager's name on it and an empty space under
# it - which reads as a setup step somebody skipped rather than as a screen
# that is finished. The log below is the whole job; this section is a bonus
# when a run exists.
if not df_runs.empty:
    st.subheader("🎯 Active Assigned Production Runs (Assigned by Manager)")

    target_run_type = "Packing" if current_role == "packer" else "Pouring"

    # Gated by station, not by who the manager originally dispatched it
    # to — see the "My Station" picker above. Whoever is logged in and
    # pointed at this station sees (and can log against) the same run.
    active_runs = df_runs[
        (df_runs["status"].isin(["Active", "Pouring", "Queued"])) &
        (df_runs["pump_station"] == my_station) &
        (df_runs.get("run_type", "Pouring") == target_run_type)
    ]

    if not active_runs.empty:
        for _, run in active_runs.iterrows():
            with st.container():
                prog_pct = min(1.0, run["current_units"] / run["target_units"]) if run["target_units"] > 0 else 0.0
                is_active = run["status"] in ["Active", "Pouring"]

                # --- NEW PULSING UI INJECTED HERE ---
                pulse_indicator = "<span class='pulse-green'></span>" if is_active else "🟡"
                status_badge = f"{pulse_indicator} POURING LIVE" if is_active else "🟡 QUEUED / STANDBY"
                status_color = "#10B981" if is_active else "#F59E0B"

                st.markdown(f"""
<div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:14px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<div>
<span style="background:rgba(16, 185, 129, 0.1); color:{status_color}; font-size:0.75rem; font-weight:800; padding:4px 8px; border-radius:4px; border: 1px solid {status_color};">{status_badge}</span>
<span style="margin-left:8px;">{resin_chip(run['resin_type'], resin_colour_map.get(str(run['resin_type'])), size="lg")}</span>
<span style="color:#00D2FF; font-weight:700; font-size:0.85rem; margin-left:6px;">[{esc(run['cartridge_type'])}]</span>
</div>
<div style="color:#94A3B8; font-size:0.85rem;">
🛢️ <b>{esc(run.get('reactor_id', 'Reactor 1'))}</b> ({run.get('reactor_size_l', 5000):,} L) &nbsp;|&nbsp; 🏷️ <b>{esc(run['pump_station'])}</b> &nbsp;|&nbsp; 👤 Dispatched: <b>{esc(run.get('assigned_operator', '—'))}</b>
</div>
</div>
<div style="background-color: #1E2B45; border-radius: 8px; width: 100%; height: 16px; margin-top: 14px; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);">
<div class="animated-progress-bar" style="width: {prog_pct * 100}%; height: 100%; background-color: {status_color}; transition: width 0.4s ease;"></div>
</div>
<div style="font-size: 0.8rem; color: inherit; opacity: 0.72; margin-top: 4px; text-align: right;">
Progress: <b style="color:inherit;">{run['current_units']:,} / {run['target_units']:,}</b> Units ({prog_pct*100:.1f}%) | Lot: {_display_lot(run.get('lot_number'), run.get('cartridge_type'))}
</div>
</div>
""", unsafe_allow_html=True)

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("+50 Units", key=f"p50_{run['id']}"):
                        update_assigned_run_progress(run['id'], 50, operator_name=current_user)
                        st.rerun()
                with col_btn2:
                    if st.button("+100 Units", key=f"p100_{run['id']}"):
                        update_assigned_run_progress(run['id'], 100, operator_name=current_user)
                        st.rerun()
                with col_btn3:
                    if st.button("✓ Mark Done", key=f"done_{run['id']}"):
                        update_run_status(run['id'], "Done")

                        # --- NEW LOTTIE ANIMATION INJECTED HERE ---
                        with st.container():
                            if lottie_success:
                                st_lottie(lottie_success, height=200, key=f"lottie_{run['id']}")

                        st.toast(f"Run {run['id']} completed!", icon="✅")
                        st.rerun()
                st.markdown("---")
    else:
        # Said plainly, without sending anybody to find a manager: the log
        # below works either way, and an operator who reads "check with your
        # Plant Manager" reasonably concludes it does not.
        st.caption(f"Nothing assigned to **{my_station}** right now — logging below works "
                   f"as normal. Pick a different station above if you're working elsewhere "
                   f"this shift.")

st.markdown("---")

# ===================== STATION TOOLS =====================
# Role/shift transfer, tank level calibration, and the resin spec lookup used
# to be three separate expanders sitting between the checklist and "what am I
# working on right now" - so an operator scrolled past three collapsed
# headers of things they touch once a shift (or less) before ever reaching
# the run they are actually pouring against. They are all still here, just
# consolidated into one expander (collapsed by default, same as before) and
# moved below the active-run section, so the common case - "what's running,
# then log it" - is reached without passing through them at all.
#
# Streamlit does not allow nesting an expander inside an expander, so each
# tool's own top-level st.expander(...) became a st.tabs(...) entry inside
# this one instead; nothing about what each tool does or how it is gated
# changed.
# A fragment: typing in the search box below used to rerun the ENTIRE page -
# every reactor card, every KPI, the whole checklist gate above it - on every
# keystroke, purely to redraw a read-only reference table. @st.fragment scopes
# the rerun to just this block, so this box no longer contributes to the
# "wait after every input" the floor was reporting. Nothing in here writes
# to the database, so there is nothing that needs the rest of the page to be
# in step with it. Kept as its own function (called from inside the Station
# Tools tab below) precisely so this fragment scoping survives the move into
# a shared expander/tabs container.
@st.fragment
def _render_resin_lookup():
    st.caption("Target fill weight and tolerance for every formulation - what a pour is checked against.")

    op_specs_df = get_all_resin_specs_df("ALL")
    op_specs_df["Target (kg)"] = (op_specs_df["actual_spec_g"] / 1000.0).round(4)

    op_search = st.text_input("🔍 Search by Resin Name or Container Format...", key="op_resin_search")
    if op_search.strip():
        op_specs_df = op_specs_df[
            op_specs_df["resin_name"].str.contains(op_search, case=False, na=False) |
            op_specs_df["cartridge_type"].str.contains(op_search, case=False, na=False)
        ]

    if op_specs_df.empty:
        st.caption("No formulations match that search.")
    else:
        _op_headers = ["Format", "Resin Formulation", "Target (g)", "Min (g)", "Max (g)", "Target (kg)"]
        _op_rows = []
        for _, _r in op_specs_df.iterrows():
            _bg, _fg, _bd = resin_colors(_r["resin_name"], resin_colour_map.get(str(_r["resin_name"])))
            _op_rows.append(
                "<tr>"
                f'<td style="padding:5px 10px;">{esc(_r["cartridge_type"])}</td>'
                f'<td style="padding:5px 10px;background:{_bg};color:{_fg};'
                f'border-left:3px solid {_bd};font-weight:700;white-space:nowrap;">{esc(_r["resin_name"])}</td>'
                f'<td style="padding:5px 10px;text-align:right;">{esc(_r["actual_spec_g"])}</td>'
                f'<td style="padding:5px 10px;text-align:right;">{esc(_r["min_weight_g"])}</td>'
                f'<td style="padding:5px 10px;text-align:right;">{esc(_r["max_weight_g"])}</td>'
                f'<td style="padding:5px 10px;text-align:right;">{esc(_r["Target (kg)"])}</td>'
                "</tr>"
            )
        _op_head = "".join(
            f'<th style="padding:6px 10px;text-align:left;border-bottom:2px solid rgba(148,163,184,0.5);'
            f'font-size:0.8rem;text-transform:uppercase;letter-spacing:0.04em;">{esc(h)}</th>'
            for h in _op_headers
        )
        st.markdown(
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;font-size:0.88rem;">'
            f"<thead><tr>{_op_head}</tr></thead><tbody>{''.join(_op_rows)}</tbody></table></div>",
            unsafe_allow_html=True,
        )


_station_tool_tabs_spec = []
if current_role in ("operator", "packer"):
    _station_tool_tabs_spec.append("🔄 Role & Shift")
_station_tool_tabs_spec.append("👀 Tank Level")
if can("view_resin_lookup"):
    _station_tool_tabs_spec.append("⚖️ Resin Lookup")

with st.expander("🔧 Station Tools", expanded=False):
    st.caption("Role & shift transfer, tank level calibration, and the resin spec "
               "reference — used occasionally, not on every log.")
    _station_tool_tabs = st.tabs(_station_tool_tabs_spec)
    _tool_tab_idx = 0

    # --- Role & Shift Transfer ---
    # Gated to real operators/packers only. This writes to
    # st.session_state["user_id"] — the REAL logged-in account, never the
    # name picked in the manager/admin "Impersonate Operator" debug selector
    # above — so an admin/manager using this page (including while browsing
    # it in impersonation mode to see what an operator sees) could otherwise
    # silently downgrade their OWN account's role to Operator/Packer with one
    # click, since the dropdown only ever offers those two options. That is
    # exactly what happened once already; this block no longer renders at all
    # for admin/manager sessions. Managers change anyone's role deliberately,
    # from Admin_Panel.py, where the target user is chosen explicitly.
    if current_role in ("operator", "packer"):
        with _station_tool_tabs[_tool_tab_idx]:
            st.caption("Update your assignment if you are pulled to a different station or shift.")

            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                role_opts = ["Operator", "Packer"]
                current_role_cap = current_role.capitalize()
                start_role_idx = role_opts.index(current_role_cap) if current_role_cap in role_opts else 0
                new_role = st.selectbox("New Assigned Role", role_opts, index=start_role_idx)

            with t_col2:
                # Driven by the plant's configured shift count, and always
                # including whatever this person is currently on - so someone
                # still carrying a retired shift can be transferred off it
                # rather than having the dropdown silently pick Shift 1 for them.
                shift_opts = shift_picker_options(get_plant_settings(), current_shift)
                start_shift_idx = shift_opts.index(current_shift) if current_shift in shift_opts else 0
                new_shift = st.selectbox("New Assigned Shift", shift_opts, index=start_shift_idx)

            with t_col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Apply Transfer", use_container_width=True):
                    user_id = st.session_state.get("user_id")
                    if user_id:
                        if update_user_role_and_shift(user_id, new_role, new_shift):
                            # Instantly update the session state so the UI morphs on reload
                            st.session_state["user_role"] = new_role.lower()
                            st.session_state["user_shift"] = new_shift
                            st.toast(f"✅ Successfully transferred to {new_role} on {new_shift}!")
                            st.rerun()
                    else:
                        st.error("Error: Could not locate User ID.")
        _tool_tab_idx += 1

    # --- Visual Tank Reconciliation ---
    with _station_tool_tabs[_tool_tab_idx]:
        st.caption(
            "If physical tank sight-glasses do not match live telemetry (e.g., at "
            "shift start), perform a visual level check to force-recalibrate the "
            "reactor gauge."
        )

        df_reactors_op = get_all_reactors_df()
        if not df_reactors_op.empty:
            active_tanks = df_reactors_op[
                df_reactors_op["current_resin"].notnull()
                & (df_reactors_op["current_resin"] != "None")
            ]

            if not active_tanks.empty:
                v_col1, v_col2, v_col3 = st.columns([1.5, 1.5, 1])

                with v_col1:
                    selected_tank = st.selectbox(
                        "Select Vessel", active_tanks["reactor_name"].tolist()
                    )
                    tank_info = active_tanks[
                        active_tanks["reactor_name"] == selected_tank
                    ].iloc[0]
                    st.markdown(
                        "Resin: &nbsp;"
                        + resin_chip(tank_info["current_resin"],
                                     resin_colour_map.get(str(tank_info["current_resin"])))
                        + f"&nbsp; | &nbsp; Max Cap: <b>{tank_info['max_capacity_l']:,} L</b>",
                        unsafe_allow_html=True,
                    )

                with v_col2:
                    estimated_l = st.number_input(
                        label="Actual Remaining Volume (Liters)",
                        min_value=0.0,
                        max_value=float(tank_info["max_capacity_l"]),
                        value=float(tank_info["max_capacity_l"]),
                        step=1.0,
                        help="Input the exact volume read on the tank gauge."
                    )

                    # Reverse calculate the percentage for the UI display
                    visual_pct = (estimated_l / float(tank_info["max_capacity_l"])) * 100.0
                    st.caption(f"Calculated Fill Level: ~**{visual_pct:.2f}%**")

                with v_col3:
                    recon_notes = st.text_input(
                        label="Check Reason", placeholder="e.g. Exact volume calibration"
                    )
                    st.markdown(body="<br>", unsafe_allow_html=True)
                    if st.button(
                        label="⚖️ Sync Tank Level", type="primary", use_container_width=True
                    ):
                        # Calling the NEW function with the exact liters!
                        success = reconcile_reactor_liters(
                            reactor_name=selected_tank,
                            actual_liters=estimated_l,
                            operator_name=current_user,
                            notes=recon_notes,
                        )

                        if success:
                            st.toast(
                                f"✅ {selected_tank} recalibrated to exactly {estimated_l}L!"
                            )
                            st.rerun()
            else:
                empty_state(
                    "No tanks have a resin assigned",
                    "Reactor levels are reconciled against what has been poured from them, "
                    "so a tank needs a resin on it before there is anything to reconcile.",
                    action="A manager sets this under Live Reactors.",
                    icon="\U0001F6E2️")
        else:
            st.info("No reactor tanks registered in database.")
    _tool_tab_idx += 1

    # --- Resin Lookup Reference ---
    # Finding 11 (security posture doc, Section 8): this used to be open to any
    # signed-in account with no ability check, showed the WHOLE master table
    # including SKUs and internal codes for formulations not released yet, and
    # st.dataframe's own toolbar let anyone export it in one click. Now gated
    # behind "view_resin_lookup" (granted to every floor role by default - this
    # is what a pour is checked against, so taking it away would break the
    # actual job), shows only the fields a pour needs (no SKU, no internal
    # code), and is a plain table rather than st.dataframe so there is no
    # built-in export button. The full table with SKUs stays where it already
    # was - the manager-only Resin Canvas page, behind manage_resins.
    if can("view_resin_lookup"):
        with _station_tool_tabs[_tool_tab_idx]:
            _render_resin_lookup()
        _tool_tab_idx += 1

# ===================== SECTION 2: DIGITAL LOGGING TRAVELER =====================

# --- NEW: AUTO-SCROLL DOWN TO LOGS ON LOGIN ---
st.markdown("<div id='log_action_area' style='padding-top: 20px;'></div>", unsafe_allow_html=True)

if not st.session_state.get("auto_scrolled_to_logs", False):
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function () {
            // A single fixed-delay setTimeout used to be enough, but as more
            // sections (top nav, KPI cards, checklist gate, expanders) got
            // added above the log area, rendering above it can still be
            // shifting layout well past a flat 800ms — the scroll fired
            // before the page finished settling, landing in the wrong spot
            // or appearing to do nothing. This instead polls for the target
            // and waits for its position to stop moving before scrolling.
            function getDoc() {
                try {
                    if (window.parent && window.parent.document) return window.parent.document;
                } catch (e) { /* sandboxed iframe — fall back below */ }
                return document;
            }

            var doc = getDoc();
            var attempts = 0;
            var maxAttempts = 60;   // ~6s at 100ms between checks
            var lastTop = null;
            var stableCount = 0;

            var poll = setInterval(function () {
                attempts++;
                var target = doc.getElementById('log_action_area');
                if (target) {
                    var top = target.getBoundingClientRect().top;
                    stableCount = (lastTop !== null && Math.abs(top - lastTop) < 2) ? stableCount + 1 : 0;
                    lastTop = top;
                    if (stableCount >= 2 || attempts >= maxAttempts) {
                        clearInterval(poll);
                        try {
                            target.scrollIntoView({behavior: 'smooth', block: 'start'});
                        } catch (e) { /* give up quietly */ }
                    }
                } else if (attempts >= maxAttempts) {
                    clearInterval(poll);
                }
            }, 100);
        })();
        </script>
        """,
        height=0, width=0
    )
    # Lock it so it doesn't jump around while they are typing!
    st.session_state["auto_scrolled_to_logs"] = True
# -----------------------------------------------------

plant_config = get_plant_settings()
packing_enabled = plant_config.get("enable_packing", True)

# --- The pump form, reachable without leaving this page ---------------------
# There is a QR sticker on the pump that opens a form somebody outside this
# application owns. Scanning it is a one-way trip: the phone navigates away
# from the MES and the way back is the browser's back button, which on a
# Streamlit app means a fresh session and a sign-in.
#
# This opens the same form in a new tab instead. The MES tab is never
# navigated away from, so closing the form puts the operator back exactly
# where they were, mid-log, with nothing retyped. It also beats the sticker
# on distance - they are already holding the phone.
#
# Above the tab strip on purpose, so it is reachable whichever tab they are
# standing in, and absent entirely when no address is configured.
_pump_url, _pump_problem = external_links.normalise(plant_config.get("pump_form_url", ""))
if _pump_url:
    st.link_button(
        "🔗 " + external_links.label_or_default(plant_config.get("pump_form_label", "")),
        _pump_url,
        use_container_width=True,
        help="Opens in a new tab. This page stays open behind it, so nothing "
             "you have already typed is lost.",
    )
elif _pump_problem and current_role in ("manager", "admin"):
    # Shown to the people who can fix it, and to nobody else - an operator
    # cannot act on a malformed setting and a warning they cannot clear is
    # just noise on the screen they work from.
    st.caption(f"⚠️ The pump form address in plant settings is not usable: {_pump_problem}")

# Short tab labels, deliberately. At 390px the four full titles needed 642px
# of strip and only two of them were fully visible; the rest sat off the right
# edge behind a horizontal scroll that nobody finds, so half this form was
# effectively unreachable on the device the operators actually hold. Each tab's
# own heading still carries the full wording - the label is a handle, not the
# sentence.
# "My Shift" is a personal, opt-in summary of this operator's own day - it
# has no plant-wide meaning, so it's only offered to the two roles who are
# actually working a shift at a station (never manager/admin, whose "Today's
# Performance" above is already plant-wide, not personal).
if current_role == "packer":
    if packing_enabled:
        tab_pack, tab_summary, tab_chat = st.tabs(["📦 Packing", "📊 My Shift", "📋 Notes"])
        tab1 = tab2 = tab3 = None
    else:
        st.error("Packing module is disabled by management.")
        st.stop()
elif current_role == "operator":
    tab1, tab2, tab3, tab_summary, tab_chat = st.tabs((
        "⚡ Pouring",
        "⚠️ Downtime",
        "📸 Audit",
        "📊 My Shift",
        "📋 Notes"
    ))
    tab_pack = None
else:
    tab_summary = None
    if packing_enabled:
        tab1, tab_pack, tab2, tab3, tab_chat = st.tabs((
            "⚡ Pouring",
            "📦 Packing",
            "⚠️ Downtime",
            "📸 Audit",
            "📋 Notes"
        ))
    else:
        tab1, tab2, tab3, tab_chat = st.tabs((
            "⚡ Pouring",
            "⚠️ Downtime",
            "📸 Audit",
            "📋 Notes"
        ))
        tab_pack = None

# Shared, request-scoped values every tab module needs - built once here
# rather than each tab re-deriving its own copy of "who is logged in" or
# re-querying the active pumps list.
_tab_ctx = types.SimpleNamespace(
    current_user=current_user,
    current_role=current_role,
    current_shift=current_shift,
    active_pumps=active_pumps,
    dt_reasons=dt_reasons,
    resin_colour_map=resin_colour_map,
    bulk_pour_enabled=bulk_pour_enabled,
    bulk_densities=bulk_densities,
    df_runs=df_runs,
    simple_mode=simple_mode,
    my_station=my_station,
)

# --- TAB 1: HOURLY POURING COUNT ---
if tab1 is not None:
    with tab1:
        pouring_tab.render(_tab_ctx)

# --- PACKING TAB ---
if tab_pack is not None:
    with tab_pack:
        packing_tab.render(_tab_ctx)

# --- TAB 2: DOWNTIME ---
if tab2 is not None:
    with tab2:
        downtime_tab.render(_tab_ctx)

# --- TAB 3: CLEANLINESS & SPILL PHOTO AUDIT ---
if tab3 is not None:
    with tab3:
        audit_tab.render(_tab_ctx)

# --- MY SHIFT: OPT-IN PERSONAL STATS SUMMARY ---
if tab_summary is not None:
    with tab_summary:
        summary_tab.render(_tab_ctx)

# --- TAB 4: MANAGER COMMS ---
if tab_chat is not None:
    with tab_chat:
        notes_tab.render(_tab_ctx)
