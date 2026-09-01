
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
    get_assigned_runs_df,
    get_all_resin_specs_df,
    calculate_logged_units_for_resin,
    get_all_reactors_df,
    add_reactor,
    delete_reactor,
    update_reactor_config,
    get_active_pumps,
    add_suggestion,
    do_logout,
    check_authentication,
)
from database import esc
from resin_palette import resin_chip, stored_color_map


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
if current_role == "admin":
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

    # Only show IT Admin to actual admins
    if st.session_state.get("user_role") == "admin":
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
        st.switch_page("Home.py")
        st.rerun()




st.markdown(f"""
<div class="brand-header">
    <div style="display:flex; align-items:center;">
        <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain;">
        <div style="font-size:1.4rem; font-weight:900; color:#FFFFFF; margin-left:15px;">🛢️ REAL-TIME REACTOR FLEET</div>
    </div>
    <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; border-radius: 20px; padding: 4px 12px; font-weight: 800;">● LIVE SENSOR SYNC</span>
</div>
""", unsafe_allow_html=True)

df_reactors = get_all_reactors_df()
df_runs = get_assigned_runs_df()
specs_df = get_all_resin_specs_df("ALL")

spec_dict = {}
if not specs_df.empty:
    for _, r in specs_df.iterrows():
        spec_dict[f"{str(r['cartridge_type']).strip().lower()}_{str(r['resin_name']).strip().lower()}"] = float(r["actual_spec_g"])

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
                if st.form_submit_button("Add Permanent Reactor", type="primary", use_container_width=True):
                    if new_name.strip():
                        add_reactor(new_name, int(new_cap))
                        st.rerun()
        with c2:
            st.markdown("**🏭 Permanent Fleet Registration**")
            st.caption("Reactors are permanent physical tanks. They will automatically fill and empty as you dispatch or complete Work Orders.")
            if not df_reactors.empty:
                for _, r in df_reactors.iterrows():
                    r_id = r['id']
                    col_r1, col_r2 = st.columns([4, 1])
                    
                    col_r1.markdown(f"<div style='margin-top:8px;'><b>🛢️ {esc(r['reactor_name'])}</b> <span style='color:#94A3B8; font-size:0.9rem;'>({r['max_capacity_l']:,} L Capacity)</span></div>", unsafe_allow_html=True)
                    
                    if col_r2.button("🗑️ Remove", key=f"del_{r_id}"):
                        delete_reactor(r_id)
                        st.rerun()
                    st.markdown("<hr style='margin: 5px 0; border-color: #1E2B45;'>", unsafe_allow_html=True)
            else:
                st.caption("No permanent reactors added yet.")

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

            # Check if there happens to be a formal active run mapping to this tank
            active_run = None
            if not df_runs.empty:
                matches = df_runs[(df_runs["reactor_id"] == r_name) & (df_runs["status"].isin(["Active", "Pouring"]))]
                if not matches.empty:
                    active_run = matches.iloc[0]

            if r_resin and r_resin != "None":
                target_pump = r_pump if (r_pump and r_pump != "None") else ""
                
                # Pull active run lot if present to ensure exact batch matching
                target_lot = str(active_run.get("lot_number", "")) if active_run is not None else ""

                # Calculate fill level dynamically from database logs
                current_poured_units = float(calculate_logged_units_for_resin(
                    resin_name=r_resin, 
                    pump_station=target_pump,
                    lot_number=target_lot
                ))

                # If an active run exists, pull exact metadata from it. Otherwise assume V2 default format.
                if active_run is not None:
                    c_type = str(active_run.get("cartridge_type", "V2")).strip()
                    op = str(active_run.get("assigned_operator", "Active Run")).strip()
                else:
                    c_type = "V2"
                    op = "Manual Floor WIP"

                vol_mult = 5.0 if "RPS" in c_type.upper() else (0.124 if "PIGMENT" in c_type.upper() else 1.0)
                poured_l = current_poured_units * vol_mult
                remaining_l = max(0.0, capacity_l - poured_l)
                fill_pct = min(100.0, (remaining_l / capacity_l) * 100.0) if capacity_l > 0 else 100.0
                
                lookup_key = f"{str(c_type).lower()}_{str(r_resin).lower()}"
                unit_g = spec_dict.get(lookup_key, 5500.0 if "RPS" in c_type.upper() else 1110.0)
                unit_kg = unit_g / 1000.0

                total_capacity_kg = (capacity_l / vol_mult) * unit_kg if vol_mult > 0 else 0.0
                poured_kg = current_poured_units * unit_kg
                remaining_kg = max(0.0, total_capacity_kg - poured_kg)

                tank_color = "linear-gradient(0deg, #EF4444 0%, #F87171 100%)" if fill_pct < 10 else "linear-gradient(0deg, #3B82F6 0%, #00D2FF 100%)"
                # The tank's resin as a coloured chip rather than cyan text.
                # This wall of tanks is read from across the room, and colour
                # is the only thing legible at that distance.
                status_html = (
                    resin_chip(r_resin, _resin_colours.get(str(r_resin)))
                    + f"<br><span style='color:#64748B; font-size:0.7rem;'>"
                      f"Station: {esc(target_pump) if target_pump else 'Any'} | Op: {esc(op)}</span>"
                )
                rem_display = f"{remaining_l:,.0f} L"
            else:
                fill_pct = 0.0
                tank_color = "transparent"
                status_html = f"<span style='color:#64748B; font-weight:800;'>IDLE / EMPTY</span><br><span style='color:#334155; font-size:0.7rem;'>Available for Setup</span>"
                rem_display = "0 L"
                remaining_kg = 0

            # --- DYNAMIC VISUAL STYLING BASED ON TANK CAPACITY ---
            if capacity_l >= 5000:
                # Tall 30ft cone-bottom on heavy metal stand
                tank_style = "width: 140px; height: 320px; margin: 0 auto; border: 3px solid #94A3B8; border-radius: 10px 10px 50% 50% / 10px 10px 15% 15%;"
                # Stand sits slightly behind and overlaps the cone bottom
                stand_html = '<div style="width: 144px; height: 60px; margin: -20px auto 0 auto; border: 6px solid #475569; border-top: none; position: relative; z-index: 1;"></div><div style="width: 156px; height: 8px; margin: 0 auto; background: #475569; border-radius: 3px;"></div>'
            elif capacity_l >= 3000:
                # Medium 15ft cone-bottom on standard metal stand
                tank_style = "width: 180px; height: 220px; margin: 0 auto; border: 3px solid #94A3B8; border-radius: 10px 10px 50% 50% / 10px 10px 22% 22%;"
                stand_html = '<div style="width: 184px; height: 50px; margin: -20px auto 0 auto; border: 5px solid #475569; border-top: none; position: relative; z-index: 1;"></div><div style="width: 196px; height: 8px; margin: 0 auto; background: #475569; border-radius: 3px;"></div>'
            else:
                # 1000L IBC Tote with Blue Plastic Frame and Pallet Base
                tank_style = "width: 220px; height: 180px; margin: 0 auto; border: 10px solid #2563EB; border-radius: 12px;"
                stand_html = '<div style="width: 220px; height: 16px; margin: 4px auto 0 auto; background: #1E3A8A; border-radius: 4px;"></div>'

            html_card = (
                f'<div style="width:100%; margin-bottom:24px;">'
                f'<div style="text-align:center; color:#FFFFFF; font-weight:800; margin-bottom:12px; font-size:1.1rem;">{r_name}</div>'
                f'<div style="{tank_style} background:#060B14; position:relative; overflow:hidden; box-shadow:inset 0 5px 15px rgba(0,0,0,0.8); z-index: 2;">'
                f'<div style="position:absolute; bottom:0; width:100%; height:{fill_pct}%; background:{tank_color}; transition:height 1s ease-in-out; opacity:0.85; border-top:2px solid rgba(255,255,255,0.8);"></div>'
                f'<div style="position:absolute; top:40%; width:100%; text-align:center; font-size:1.5rem; font-weight:900; color:#FFFFFF; text-shadow:2px 2px 6px #000; z-index: 3;">{fill_pct:.1f}%</div>'
                f'</div>'
                f'{stand_html}'
                f'<div style="text-align:center; background:linear-gradient(180deg, #0D1627 0%, #080D1A 100%); border:1px solid #00D2FF; border-radius:8px; padding:8px; margin-top:16px;">'
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
