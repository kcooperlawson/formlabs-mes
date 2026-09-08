
import os
import sys
import base64
from datetime import datetime, date, timedelta

import streamlit as st
import extra_streamlit_components as stx

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from database import (
    get_all_resin_specs_df,
    reactor_draw_litres,
    container_litres,
    add_hourly_log,
    get_plant_settings,
    get_all_reactors_df,
    add_reactor,
    update_reactor_identity,
    delete_reactor,
    update_reactor_config,
    get_active_pumps,
    add_suggestion,
    do_logout,
    check_authentication,
    role_can_administer,
)
from database import esc
from resin_palette import resin_chip, stored_color_map, resin_color
from bulk_pour import (DEFAULT_DENSITY_KG_L, UNITS, density_map, resin_density,
                       pour_litres, check_pour, describe_pour)
from reactor_vessel import (vessel_svg, resolve_vessel_type,
                            VESSEL_TYPES, VESSEL_LABELS, VESSEL_HELP)


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = get_base64_image("assets/formlabs_logo.png")

st.set_page_config(page_title="Live Reactor Fleet SCADA | Formlabs MES", page_icon="🛢️", layout="wide")
st.logo("assets/formlabs_logo.png")


# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
# ===================================================================

@st.fragment(run_every="10s")
def auto_refresh_reactors():
    pass

auto_refresh_reactors()

cookie_manager = stx.CookieManager(key="reactors_cookies")
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")


# 1. Initialize User & Role FIRST
current_user = st.session_state.get("user_name") or "Keagan C."

# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
# ===================================================================
# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

st.markdown("<br>", unsafe_allow_html=True)
if role_can_administer(current_role):
    # God Mode (Now 6 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5:
        st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6:
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    # Manager Suite (Now 5 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5:
        st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    # Operator View (Stays 3 Columns)
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")

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

    # --- CUSTOM ROUTER (NEW) ---
    st.markdown("#### 🗺️ Navigation")
    st.page_link("Home.py", label="Live SCADA", icon="⚡")
    st.page_link("pages/Operator_Form.py", label="Operator Form", icon="📝")
    st.page_link("pages/Manager_Cockpit.py", label="Manager Cockpit", icon="📊")
    st.page_link("pages/Live_Reactors.py", label="Live Reactors", icon="🛢️")
    st.page_link("pages/Analytics_Hub.py", label="Analytics Hub", icon="🌌")

    # In execution mode this is administrators only. In logging mode there is
    # no separate IT role and a manager reaches it too - see
    # crud.can_administer.
    if role_can_administer(st.session_state.get("user_role")):
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️")

    st.markdown("---")
    # ---------------------------

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
            current_t = st.session_state.get("preferred_theme", "Default Dark")
            chosen_t = st.selectbox("System Theme", list(THEMES.keys()),
                                    index=list(THEMES.keys()).index(current_t) if current_t in THEMES else 0)

            if chosen_t != current_t:
                from database import update_user_theme

                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
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
            st.markdown("#### Universal Feedback Box")
            with st.form("settings_sug_form", clear_on_submit=True):
                s_cat = st.selectbox("Category", ("Feature Request", "App Bug / Error", "Plant Floor Issue"))
                s_txt = st.text_area("Observation / Description")
                if st.form_submit_button("🚀 Submit Feedback", type="primary", use_container_width=True):
                    if s_txt.strip():
                        from database import add_suggestion

                        add_suggestion(st.session_state.get("user_name"), st.session_state.get("user_role"), s_cat,
                                       s_txt)
                        st.success("✅ Submitted to IT Admin!")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LAUNCH TV MODE ---
    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        # switch_page raises to navigate, so an st.rerun() after it never ran.
        st.switch_page("Home.py")




st.markdown(f"""
<div class="brand-header">
    <div style="display:flex; align-items:center;">
        <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain;">
        <div style="font-size:1.4rem; font-weight:900; color:inherit; margin-left:15px;">🛢️ REAL-TIME REACTOR FLEET</div>
    </div>
    <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; border-radius: 20px; padding: 4px 12px; font-weight: 800;">● LIVE SENSOR SYNC</span>
</div>
""", unsafe_allow_html=True)

df_reactors = get_all_reactors_df()
specs_df = get_all_resin_specs_df("ALL")

# How heavy a litre of each resin is.
#
# The tank is measured in litres - that is what a tank holds - and the second
# number on the card is the same quantity in kilograms, because that is the
# unit the resin is bought and reported in. Going between them needs a density
# and nothing else: a spec of 1,110 g in a 1 L cartridge and one of 5,550 g in
# a 5 L jug are the same 1.11 kg per litre, so it does not matter which format
# the spec happens to be written against. That is the whole reason this is a
# density map and not the old container lookup - the tank no longer knows, or
# needs to know, which format is being poured out of it right now.
# The derivation itself now lives in bulk_pour, because the bulk-pour panel
# below needs the same numbers to turn kilograms into litres and two copies of
# a conversion is how a tank and a form come to disagree about the same pour.
density_by_resin = density_map(
    (specs_df.to_dict("records") if not specs_df.empty else []), container_litres)

_bulk_enabled = bool(get_plant_settings().get("enable_bulk_pour", False))
_resin_colours = stored_color_map(specs_df)
all_resins = ["None"] + sorted(specs_df["resin_name"].unique().tolist()) if not specs_df.empty else ["None"]
all_pumps = ["None"] + get_active_pumps()

if st.session_state.get("user_role") in ["manager", "admin"]:
    with st.expander("⚙️ Manage Permanent Reactor Fleet", expanded=False):
        c1, c2 = st.columns([1.5, 2.5])
        with c1:
            st.markdown("**➕ Add New Permanent Reactor**")
            with st.form("add_reactor_form", clear_on_submit=True):
                new_name = st.text_input("Reactor Name (e.g. Tank C-5000)")
                new_cap = st.number_input("Max Capacity (Liters)", value=5000, step=500)
                new_kind = st.selectbox(
                    "Vessel Type", VESSEL_TYPES, index=0,
                    format_func=lambda k: VESSEL_LABELS[k],
                    help="What the vessel physically is. This is what the fleet "
                         "wall draws, and capacity cannot tell these apart.")
                st.caption(VESSEL_HELP[new_kind])
                nt1, nt2 = st.columns(2)
                new_tag = nt1.text_input("Asset Tag", placeholder="M-205")
                new_bay = nt2.text_input("Bay Marker", placeholder="F3", max_chars=3)
                if st.form_submit_button("Add Permanent Reactor", type="primary", use_container_width=True):
                    if new_name.strip():
                        add_reactor(new_name, int(new_cap), vessel_type=new_kind,
                                    asset_tag=new_tag, bay_marker=new_bay)
                        st.rerun()
        with c2:
            st.markdown("**🏭 Permanent Fleet Registration**")
            # The tags are not decoration. Every vessel out there is stencilled
            # with an asset tag and stands beside a bollard carrying an orange
            # bay marker, and those are what people say to each other on the
            # floor. A tank called "Reactor 2" on screen and "M-205" in the
            # aisle is one translation step at the exact moment somebody is
            # trying to check whether the screen is telling the truth.
            st.caption("Permanent physical vessels. The type decides how each one is drawn on "
                       "the wall; the tag and bay marker are what it is called on the floor.")
            _fleet_specs = get_all_resin_specs_df("ALL")
            _fleet_resin_names = (sorted(_fleet_specs["resin_name"].dropna()
                                         .astype(str).unique().tolist())
                                  if not _fleet_specs.empty else [])
            if not df_reactors.empty:
                for _, r in df_reactors.iterrows():
                    r_id = r['id']
                    col_r1, col_r2 = st.columns([4, 1])
                    col_r1.markdown(
                        f"<div style='margin-top:8px;'><b>🛢️ {esc(r['reactor_name'])}</b> "
                        f"<span style='color:#94A3B8; font-size:0.9rem;'>"
                        f"({r['max_capacity_l']:,} L)</span></div>",
                        unsafe_allow_html=True)
                    if col_r2.button("🗑️ Remove", key=f"del_{r_id}"):
                        delete_reactor(r_id)
                        st.rerun()

                    kind_now = resolve_vessel_type(r.get("vessel_type"), r["max_capacity_l"])
                    with st.form(f"vessel_form_{r_id}"):
                        f1, f2, f3, f4 = st.columns([2.2, 1, 1, 1])
                        kind = f1.selectbox(
                            "Vessel type", VESSEL_TYPES,
                            index=VESSEL_TYPES.index(kind_now),
                            format_func=lambda k: VESSEL_LABELS[k],
                            key=f"vk_{r_id}", label_visibility="collapsed")
                        tag = f2.text_input("Asset tag", value=r.get("asset_tag") or "",
                                            placeholder="M-205", key=f"vt_{r_id}",
                                            label_visibility="collapsed")
                        bay = f3.text_input("Bay", value=r.get("bay_marker") or "",
                                            placeholder="F3", max_chars=3, key=f"vb_{r_id}",
                                            label_visibility="collapsed")
                        # The two fields that decide whether this tank counts
                        # for anything. A vessel's level is worked out from the
                        # logs that match its pump and its resin, and until now
                        # the only code that ever set them was work-order
                        # dispatch - so on a plant running with work orders off
                        # there was no way to link a tank at all, and every one
                        # of them read full for ever while the floor emptied
                        # them. update_reactor_config already existed and was
                        # imported into this page. Nothing ever called it.
                        g1, g2 = st.columns(2)
                        _pump_opts = ["— not set —"] + [str(x) for x in get_active_pumps()]
                        _pump_now = str(r.get("assigned_pump") or "").strip()
                        _resin_opts = ["— not set —"] + _fleet_resin_names
                        _resin_now = str(r.get("current_resin") or "").strip()
                        pump_pick = g1.selectbox(
                            "Feeds pump station", _pump_opts,
                            index=_pump_opts.index(_pump_now) if _pump_now in _pump_opts else 0,
                            key=f"vp_{r_id}")
                        resin_pick = g2.selectbox(
                            "Resin in it now", _resin_opts,
                            index=_resin_opts.index(_resin_now) if _resin_now in _resin_opts else 0,
                            key=f"vr_{r_id}")
                        if not _pump_now or not _resin_now:
                            st.caption("⚠️ Not linked yet, so this tank's level will not move. "
                                       "Set the pump and the resin and it starts counting from "
                                       "the pours already logged against them.")
                        if f4.form_submit_button("💾 Save", use_container_width=True):
                            update_reactor_identity(int(r_id), vessel_type=kind,
                                                    asset_tag=tag, bay_marker=bay)
                            update_reactor_config(
                                int(r_id),
                                "" if resin_pick.startswith("—") else resin_pick,
                                "" if pump_pick.startswith("—") else pump_pick)
                            st.rerun()
                    st.markdown("<hr style='margin: 5px 0; border-color: #1E2B45;'>", unsafe_allow_html=True)
            else:
                st.caption("No permanent reactors added yet.")

# --- a pour that is an amount, not a count ----------------------------------
# Most of what leaves these tanks goes into a cartridge and is counted. Some of
# it is decanted: a specific amount into a drum, a tote, a pail. There was no
# way to write that down, so it went in as a wrong number of cartridges or it
# did not go in at all, and either way the tank above was wrong from that
# moment on.
#
# It sits on this page rather than a settings screen because a bulk pour's
# whole effect is the tank level, and this is where you can see it land. The
# operator's form carries the same thing behind the same switch, for the times
# nobody with a manager login is on the floor.
if _bulk_enabled and st.session_state.get("user_role") in ["manager", "admin"]:
    with st.expander("🛢️ Log a bulk pour (drum, tote, pail)", expanded=False):
        _live = df_reactors[df_reactors["current_resin"].notna()] if not df_reactors.empty else df_reactors
        _live = _live[_live["current_resin"] != "None"] if not _live.empty else _live

        if _live.empty:
            st.info("No reactor has a resin assigned yet. Set one above and this will "
                    "know which tank the pour came out of.")
        else:
            _labels = {}
            for _, _r in _live.iterrows():
                _tag = str(_r.get("asset_tag") or "").strip()
                _labels[f"{_tag + ' — ' if _tag else ''}{_r['reactor_name']} · {_r['current_resin']}"] = _r

            _pick = st.selectbox("Which vessel did it come out of?", list(_labels.keys()),
                                 key="bp_vessel")
            _r = _labels[_pick]
            _cap = float(_r["max_capacity_l"])
            _resin = str(_r["current_resin"])
            _pump = _r.get("assigned_pump") if _r.get("assigned_pump") not in (None, "None") else ""
            _drawn, _lot = reactor_draw_litres(_resin, _pump)
            _left = max(0.0, _cap - _drawn)
            _dens = resin_density(_resin, density_by_resin)

            st.caption(f"Record says **{_left:,.0f} L** left of {_cap:,.0f} L"
                       + (f" · lot {esc(_lot)}" if _lot else "")
                       + f" · {_dens:.3f} kg per litre")

            bp1, bp2, bp3 = st.columns([1, 1.4, 1])
            with bp1:
                _count = st.number_input("Containers", min_value=1, max_value=99, value=1,
                                         step=1, key="bp_count")
            with bp2:
                _each = st.number_input("Amount in each", min_value=0.0, value=0.0,
                                        step=1.0, format="%.2f", key="bp_each")
            with bp3:
                _unit = st.radio("Unit", UNITS, horizontal=True, key="bp_unit")

            _what = st.text_input("Poured into", placeholder="55 gal drum, blue tote, pail",
                                  max_chars=60, key="bp_what")
            _litres = pour_litres(_count, _each, _unit, _dens)
            _verdict = check_pour(_litres, capacity_l=_cap, remaining_l=_left)

            # The conversion is stated before the submit, not after. An
            # operator knows they poured 200 kg; whether that is 180 litres is
            # the application's claim, and it should have to make it out loud.
            if _litres > 0:
                st.markdown(f"**{describe_pour(_count, _each, _unit, _dens, _what)}**")
            if _verdict["message"]:
                (st.error if _verdict["blocked"] else st.warning)(_verdict["message"])

            if st.button("💾 Record this pour", type="primary", disabled=_verdict["blocked"],
                         use_container_width=True, key="bp_save"):
                add_hourly_log(
                    operator_name=st.session_state.get("user_name", "Manager"),
                    pump_station=_pump or str(_r["reactor_name"]),
                    shift=st.session_state.get("user_shift", "Shift 1"),
                    cartridge_type="Bulk", resin_type=_resin,
                    lot_number=_lot or "", bottles=int(_count),
                    scrap_empty=0, scrap_filled=0,
                    notes=f"Bulk pour logged from the reactor page.",
                    litres_poured=_litres, pour_note=_what,
                )
                st.success(f"Recorded {_litres:,.1f} L off {_r['reactor_name']}.")
                st.rerun()

st.markdown("---")

if not df_reactors.empty:
    cols_per_row = 4
    for i in range(0, len(df_reactors), cols_per_row):
        row_reactors = df_reactors.iloc[i:i+cols_per_row]
        tank_cols = st.columns(cols_per_row)

        for j, (_, reactor) in enumerate(row_reactors.iterrows()):
            capacity_l = float(reactor["max_capacity_l"])
            r_name = reactor["reactor_name"]
            r_resin = reactor.get("current_resin")
            r_pump = reactor.get("assigned_pump")

            if r_resin and r_resin != "None":
                target_pump = r_pump if (r_pump and r_pump != "None") else ""

                # What has come out of this tank since it was last filled.
                #
                # This used to be read off the work order assigned to the tank:
                # the order's lot said which pours to count, and the order's
                # container format said how big each pour was. Neither of those
                # is a reactor fact, and with work orders switched off there was
                # no order to read - so every tank summed every log ever taken
                # at that station, drained to empty on the first day and stayed
                # there, and sized every pour as a 1 L cartridge whatever had
                # actually gone out.
                #
                # Both answers are already in the log itself. The operator reads
                # the lot off the container each hour, so a new lot at the
                # station is the tank being refilled; and each log carries the
                # format it was poured in, so the litres are summed per log
                # rather than assumed for the batch. The tank now reads the same
                # whether or not anybody is dispatching runs, which is the point.
                poured_l, batch_lot = reactor_draw_litres(r_resin, target_pump)
                remaining_l = max(0.0, capacity_l - poured_l)
                fill_pct = min(100.0, (remaining_l / capacity_l) * 100.0) if capacity_l > 0 else 100.0

                density = density_by_resin.get(str(r_resin).strip().lower(), DEFAULT_DENSITY_KG_L)
                remaining_kg = remaining_l * density

                # The tank's resin as a coloured chip rather than cyan text.
                # This wall of tanks is read from across the room, and colour
                # is the only thing legible at that distance.
                #
                # The second line is the lot, not the operator: the lot is what
                # says which fill this reading belongs to, and it is the thing
                # somebody standing at the tank can check against the container
                # in front of them.
                status_html = (
                    resin_chip(r_resin, _resin_colours.get(str(r_resin)))
                    + f"<br><span style='color:#64748B; font-size:0.7rem;'>"
                      f"Station: {esc(target_pump) if target_pump else 'Any'} | "
                      f"Lot: {esc(batch_lot) if batch_lot else '—'}</span>"
                )
                rem_display = f"{remaining_l:,.0f} L"
            else:
                fill_pct = 0.0
                tank_color = "transparent"
                status_html = f"<span style='color:#64748B; font-weight:800;'>IDLE / EMPTY</span><br><span style='color:#334155; font-size:0.7rem;'>Available for Setup</span>"
                rem_display = "0 L"
                remaining_kg = 0

            # The vessel is drawn as the kind of thing it physically is - a
            # bulk vertical, a cone-bottom mixer or a caged tote - from what
            # a manager recorded against it, because capacity cannot tell
            # those apart. See reactor_vessel.
            vessel_kind = resolve_vessel_type(reactor.get("vessel_type"), capacity_l)
            vessel = vessel_svg(
                vessel_kind, fill_pct, capacity_l,
                resin_colour=resin_color(r_resin, _resin_colours.get(str(r_resin))),
                asset_tag=reactor.get("asset_tag") or "",
                bay_marker=reactor.get("bay_marker") or "",
                idle=not (r_resin and r_resin != "None"),
                key=f"{reactor.get('id', i)}_{j}")

            html_card = (
                f'<div style="width:100%; margin-bottom:24px;">'
                f'<div style="text-align:center; color:#FFFFFF; font-weight:800; margin-bottom:10px; font-size:1.1rem;">{r_name}</div>'
                f'{vessel}'
                f'<div style="text-align:center; background:linear-gradient(180deg, #0D1627 0%, #080D1A 100%); border:1px solid #00D2FF; border-radius:8px; padding:8px; margin-top:14px;">'
                f'<div style="font-size:0.6rem; font-weight:800; color:#94A3B8; letter-spacing:0.1em;">REMAINING IN TANK</div>'
                f'<div style="font-size:1.05rem; font-weight:900; color:#FFFFFF; margin-top:2px;">{rem_display} <span style="font-size:0.7rem; color:#64748B;">({remaining_kg:,.0f} kg)</span></div>'
                f'</div>'
                f'<div style="text-align:center; background-color:#0F172A; border:1px solid #1E2B45; border-radius:6px; padding:6px; margin-top:6px;">'
                f'{status_html}'
                f'</div>'
                f'</div>'
            )

            with tank_cols[j]:
                st.markdown(html_card, unsafe_allow_html=True)
else:
    st.info("No active physical reactors allocated by management. Add them in the settings menu above.")
