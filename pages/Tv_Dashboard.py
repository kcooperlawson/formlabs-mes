import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from database import (
    get_production_logs_df,
    get_assigned_runs_df,
    get_all_resin_specs_df,
    get_plant_settings,
    add_suggestion,
)
import base64

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = get_base64_image("assets/formlabs_logo.png")

st.set_page_config(page_title="Factory Live TV | Formlabs SCADA", page_icon="📺", layout="wide")

st.markdown("""
<style>
    /* Aggressively hide native multi-page navigation to minimize load flash */
    [data-testid="stSidebarNav"], 
    [data-testid="stSidebarNav"] > ul {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

import extra_streamlit_components as stx
cookie_manager = stx.CookieManager(key="tv_cookies")
# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
import extra_streamlit_components as stx

# Initialize our double-take flag
if "auth_check_passed" not in st.session_state:
    st.session_state["auth_check_passed"] = False

if not st.session_state.get("authenticated", False):
    cached_token = cookie_manager.get(cookie="formlabs_mes_token")

    if cached_token is not None:
        from database import get_all_users_df

        df_users = get_all_users_df()
        user_match = df_users[df_users["username"] == cached_token]

        if not user_match.empty:
            user_data = user_match.iloc[0]
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = int(user_data["id"])
            st.session_state["user_role"] = user_data["role"]
            st.session_state["user_name"] = user_data["full_name"]
            st.session_state["user_shift"] = user_data.get("shift", "Shift 1")
            st.session_state["preferred_theme"] = user_data.get("preferred_theme", "Default Dark")
            time.sleep(0.2)
            st.rerun()
    else:
        # THE DOUBLE-TAKE: Give the browser 0.2 seconds to send the cookie!
        if not st.session_state["auth_check_passed"]:
            st.session_state["auth_check_passed"] = True
            time.sleep(0.2)
            st.rerun()
        else:
            # If it checked twice and STILL no cookie, they are truly logged out.
            st.warning("🔒 Session Expired. Please log in.")
            st.switch_page("Home.py")
            st.stop()

# 1. Initialize User & Role FIRST
current_user = st.session_state.get("user_name") or "Keagan C."

# --- Check Manager Role Security Gate ---
user_role = st.session_state.get("user_role") or "guest"
if user_role not in ["manager", "admin"]: # <-- Change to this
    st.error("🔒 Access Denied: The TV Dashboard is restricted to Plant Management.")
    st.stop()

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
    st.markdown(f"### 👤 {st.session_state.get('user_name', 'Operator')}")
    st.caption(
        f"Role: `{str(st.session_state.get('user_role', 'unknown')).upper()}` | Shift: `{st.session_state.get('user_shift', 'Unknown')}`")

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
                        st.success(f"✅ {msg}")
                        time.sleep(1)
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
                cookie_manager.set("formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar

                    update_user_avatar(st.session_state["user_id"], new_avatar)
                    st.success("✅ Avatar updated!")
                    time.sleep(1)
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
        # 1. Save the current theme before wiping the session
        saved_theme = st.session_state.get("preferred_theme", "Default Dark")

        try:
            # 2. Forcing an expired date is much more reliable than just .delete()
            cookie_manager.set("formlabs_mes_token", "", expires_at=datetime.now() - timedelta(days=1))
            cookie_manager.delete("formlabs_mes_token")
        except Exception:
            pass

        # 3. Clear memory
        st.session_state.clear()

        # 4. Restore the theme and set a Hard Lockout flag!
        st.session_state["preferred_theme"] = saved_theme
        st.session_state["explicitly_logged_out"] = True

        st.switch_page("Home.py")
        time.sleep(0.5)
        st.rerun()



st.markdown("""
<style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 98% !important; }
    .stApp { background-color: #050914; color: #E2E8F0; }
    
    .tv-card { background: linear-gradient(180deg, #0D1627 0%, #080D1A 100%); border: 1px solid #1E2B45; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.5); height: 100%; }
    .tv-value { font-size: 3.5rem; font-weight: 900; color: #FFFFFF; line-height: 1.1; margin-top: 10px; }
    .tv-label { font-size: 1rem; font-weight: 700; color: #94A3B8; letter-spacing: 0.1em; text-transform: uppercase; }
    .tv-header { font-size: 2.2rem; font-weight: 900; color: #FFFFFF; border-bottom: 2px solid #1E2B45; padding-bottom: 10px; margin-bottom: 20px; display:flex; justify-content:space-between; align-items:center; }
    .stat-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #1E2B45; font-size: 1.15rem; }
</style>
""", unsafe_allow_html=True)


df_logs = get_production_logs_df()
today_str = date.today().strftime("%Y-%m-%d")

if not df_logs.empty:
    df_logs["date_str"] = pd.to_datetime(df_logs["date"]).dt.strftime("%Y-%m-%d")
    df_today = df_logs[df_logs["date_str"] == today_str]
else:
    df_today = pd.DataFrame()

df_today_pour = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
df_today_pack = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

def calculate_liters(df_subset):
    total_l = 0.0
    for _, r in df_subset.iterrows():
        b_count = float(r.get("bottles_filled", 0) or 0)
        c_type = str(r.get("cartridge_type", "V2")).upper()
        vol_mult = 5.0 if "RPS" in c_type else (0.124 if "PIGMENT" in c_type else 1.0)
        total_l += (b_count * vol_mult)
    return total_l

df_s1 = df_today_pour[df_today_pour["shift"] == "Shift 1"] if not df_today_pour.empty else pd.DataFrame()
df_s2 = df_today_pour[df_today_pour["shift"] == "Shift 2"] if not df_today_pour.empty else pd.DataFrame()

s1_liters = calculate_liters(df_s1)
s2_liters = calculate_liters(df_s2)

# Calculate total for the whole day
total_liters_today = calculate_liters(df_today_pour)

# Add the interactive toggle to the top of the TV Dashboard
display_mode = st.radio(
    "📺 SELECT TV DISPLAY MODE:", 
    ["🟢 Auto-Detect Active Shift", "🏭 Full Plant Daily Total"], 
    horizontal=True
)

total_poured = int(df_today_pour["bottles_filled"].sum()) if not df_today_pour.empty else 0
total_packed = int(df_today_pack["bottles_filled"].sum()) if not df_today_pack.empty else 0
scrap_units = int(df_today_pour["scrap_empty"].sum() + df_today_pour["scrap_filled"].sum()) if not df_today_pour.empty else 0
yield_pct = (total_poured / (total_poured + scrap_units) * 100) if (total_poured + scrap_units) > 0 else 100.0

settings = get_plant_settings()
target_lph = float(settings.get("target_lph", 400.0))
target_yield = float(settings.get("yield_target_pct", 99.0))
packing_enabled = settings.get("enable_packing", True)

time_now = datetime.now()
s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
s2_h, s2_m = map(int, settings["shift_2_start"].split(":"))

shift_1_start = time_now.replace(hour=s1_h, minute=s1_m, second=0)
shift_2_start = time_now.replace(hour=s2_h, minute=s2_m, second=0)

# --- TOGGLE LOGIC ---
if display_mode == "🟢 Auto-Detect Active Shift":
    if time_now < shift_1_start:
        shift_2_start = shift_2_start - timedelta(days=1)
        active_shift = "Shift 2"
        shift_start = shift_2_start
        shift_length_hrs = float(settings["shift_2_hours"])
        current_output = s2_liters
    elif shift_1_start <= time_now < shift_2_start:
        active_shift = "Shift 1"
        shift_start = shift_1_start
        shift_length_hrs = float(settings["shift_1_hours"])
        current_output = s1_liters
    else:
        active_shift = "Shift 2"
        shift_start = shift_2_start
        shift_length_hrs = float(settings["shift_2_hours"])
        current_output = s2_liters

    elapsed_hours = min(shift_length_hrs, max(0.25, (time_now - shift_start).total_seconds() / 3600.0))

else:
    # Full Daily Total Logic
    active_shift = "ALL SHIFTS (DAILY TOTAL)"
    current_output = total_liters_today
    total_shift_length = float(settings["shift_1_hours"]) + float(settings["shift_2_hours"])

    if time_now < shift_1_start:
        total_elapsed = (time_now - (shift_1_start - timedelta(days=1))).total_seconds() / 3600.0
    else:
        total_elapsed = (time_now - shift_1_start).total_seconds() / 3600.0

    elapsed_hours = min(total_shift_length, max(0.25, total_elapsed))

current_run_rate = current_output / elapsed_hours

# --- NEW LIVE TICKING MATH ---
if active_shift == "ALL SHIFTS (DAILY TOTAL)":
    remaining_hrs = max(0.0, total_shift_length - elapsed_hours)
else:
    remaining_hrs = max(0.0, shift_length_hrs - elapsed_hours)

blended_rate = current_run_rate if elapsed_hours > 0.5 else target_lph
projected_total = current_output + (blended_rate * remaining_hrs)
expected_now = target_lph * elapsed_hours

st.markdown(f"""
<div class='tv-header'>
    <div style='display:flex; align-items:center; gap:20px;'>
        <img src="data:image/png;base64,{logo_b64}" style="height: 50px; object-fit: contain;">
        <span>LIVE PLANT COMMAND</span>
    </div>
    <span style='color:#10B981; font-size:1.5rem;'>● {active_shift.upper()} ACTIVE &nbsp;|&nbsp; {time_now.strftime('%H:%M:%S')}</span>
</div>
""", unsafe_allow_html=True)

# ===================== DYNAMIC KPI ROW =====================
if packing_enabled:
    col1, col2, col3, col4 = st.columns(4)
else:
    col1, col2 = st.columns(2)

with col1:
    fig_rate = go.Figure(go.Indicator(
        mode="gauge+number", value=current_run_rate,
        number={'suffix': " L/h", 'font': {'size': 48, 'color': '#FFFFFF'}},
        gauge={
            'axis': {'range': [None, 600], 'tickwidth': 1, 'tickcolor': "#94A3B8"},
            'bar': {'color': "#00D2FF"}, 'bgcolor': "#1E2B45",
            'steps': [{'range': [0, 300], 'color': "rgba(239, 68, 68, 0.3)"},
                      {'range': [300, 400], 'color': "rgba(245, 158, 11, 0.3)"},
                      {'range': [400, 600], 'color': "rgba(16, 185, 129, 0.3)"}],
            'threshold': {'line': {'color': "#FFFFFF", 'width': 4}, 'thickness': 0.75, 'value': target_lph}
        }
    ))
    fig_rate.update_layout(margin=dict(l=15, r=15, t=15, b=15), height=230, paper_bgcolor="rgba(0,0,0,0)",
                           font={'color': "#94A3B8"})

    st.markdown("<div class='tv-card'><div class='tv-label'>💧 LIVE RUN VELOCITY</div>", unsafe_allow_html=True)
    st.plotly_chart(fig_rate, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="tv-card" style="padding: 15px;">
            <div class="tv-label">💧 TOTAL VOLUME POURED</div>
            <div class="tv-value" style="font-size: 3rem;">{current_output:,.0f} <span style="font-size:1.2rem; color:#94A3B8;">Liters</span></div>
            <div style="display:flex; justify-content: space-between; border-top: 1px solid #1E2B45; margin-top: 12px; padding-top: 12px;">
                <div style="text-align: left;">
                    <div style="font-size:0.7rem; color:#94A3B8; font-weight:bold; letter-spacing:0.1em;">EXPECTED NOW</div>
                    <div style="color:#00D2FF; font-size:1.2rem; font-weight:bold;">{expected_now:,.0f} L</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size:0.7rem; color:#94A3B8; font-weight:bold; letter-spacing:0.1em;">PROJECTED TOTAL</div>
                    <div style="color:#A855F7; font-size:1.2rem; font-weight:bold;">{projected_total:,.0f} L</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

if packing_enabled:
    with col3:
        st.markdown(f"""<div class="tv-card" style="border-color:#A855F7;"><div class="tv-label" style="color:#A855F7;">📦 TOTAL UNITS PACKED</div>
            <div class="tv-value" style="color:#A855F7;">{total_packed:,.0f} <span style="font-size:1.5rem; color:#94A3B8;">Units</span></div>
            <div style="color:#A855F7; font-size:1.2rem; font-weight:bold; margin-top:20px;">Est. Skids Built: {(total_packed / 500):,.1f}</div></div>""",
                    unsafe_allow_html=True)

    with col4:
        st.markdown(f"""<div class="tv-card" style="border-color:#F59E0B;"><div class="tv-label" style="color:#F59E0B;">⚠️ UNPACKED FLOOR W.I.P.</div>
            <div class="tv-value" style="color:#F59E0B;">{total_poured - total_packed:,} <span style="font-size:1.5rem; color:#94A3B8;">Pending</span></div>
            <div style="color:#94A3B8; font-size:1.2rem; font-weight:bold; margin-top:20px;">Units awaiting pack-out</div></div>""",
                    unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ===================== DYNAMIC BREAKDOWN ROW =====================
if packing_enabled:
    b1, b2, b3 = st.columns((1.1, 1.5, 1.5))
else:
    b1, b3 = st.columns(2)

with b1:
    st.markdown("<div class='tv-card'><div class='tv-label' style='margin-bottom:15px;'>💧 TOP POURERS (L/h)</div>", unsafe_allow_html=True)
    if not df_today_pour.empty:
        op_stats = []
        for op in df_today_pour["operator_name"].unique():
            op_data = df_today_pour[df_today_pour["operator_name"] == op]

            # 1. Calculate liters
            op_liters = 0.0
            for _, r in op_data.iterrows():
                b_count = float(r.get("bottles_filled", 0) or 0)
                c_type = str(r.get("cartridge_type", "V2")).upper()
                vol_mult = 5.0 if "RPS" in c_type else (0.124 if "PIGMENT" in c_type else 1.0)
                op_liters += (b_count * vol_mult)

            # 2. Isolate the operator's specific worked hours
            timestamps = pd.to_datetime(op_data["timestamp"])
            time_span_hours = (timestamps.max() - timestamps.min()).total_seconds() / 3600.0
            op_hours = min(elapsed_hours, max(1.0, time_span_hours + 1.0))

            # 3. Calculate true rate
            vel = op_liters / op_hours if op_hours > 0 else 0
            op_stats.append((op, vel))

        # Sort by velocity descending
        op_stats.sort(key=lambda x: x[1], reverse=True)

        for rank, (op, vel) in enumerate(op_stats[:5]):
            st.markdown(f"<div class='stat-row'><span>👤 {op}</span><span style='color:#00D2FF; font-weight:bold;'>{vel:,.0f} L/h</span></div>", unsafe_allow_html=True)
    else:
        st.caption("No pouring data logged yet today.")
    st.markdown("</div>", unsafe_allow_html=True)

if packing_enabled:
    with b2:
        st.markdown(
            "<div class='tv-card' style='border-color:#A855F7;'><div class='tv-label' style='margin-bottom:15px; color:#A855F7;'>📦 PACKING BREAKDOWN</div>",
            unsafe_allow_html=True)
        if not df_today_pack.empty:
            specs_df = get_all_resin_specs_df("ALL")
            pack_grp = df_today_pack.groupby(["resin_type", "lot_number"])["bottles_filled"].sum().reset_index()

            for _, row in pack_grp.iterrows():
                res = row['resin_type']
                lot = row['lot_number']
                qty = row['bottles_filled']

                skid_size = 500
                if not specs_df.empty:
                    match = specs_df[specs_df["resin_name"] == res]
                    if not match.empty:
                        skid_size = float(match.iloc[0].get("units_per_skid", 500))

                skids = qty / skid_size if skid_size > 0 else 0
                st.markdown(
                    f"<div style='text-align:left; margin-bottom: 8px; border-bottom:1px solid #1E2B45; padding-bottom:6px;'><b style='color:white; font-size:1.1rem;'>{res}</b> &nbsp;<span style='color:#94A3B8; font-size:0.8rem;'>({lot})</span><div style='float:right;'><span style='color:#A855F7; font-weight:bold; font-size:1.1rem;'>{qty:,} Units</span> <span style='color:#64748B; font-size:0.9rem;'>({skids:.1f} Skids)</span></div></div>",
                    unsafe_allow_html=True)
        else:
            st.caption("No packing data logged yet today.")
        st.markdown("</div>", unsafe_allow_html=True)

with b3:
    st.markdown(
        "<div class='tv-card'><div class='tv-label' style='margin-bottom:15px;'>⚙️ ACTIVE REACTOR WORK ORDERS</div>",
        unsafe_allow_html=True)
    df_runs = get_assigned_runs_df()
    if not df_runs.empty:
        active_runs = df_runs[df_runs["status"].isin(["Active", "Pouring"])]
        if not active_runs.empty:
            for _, run in active_runs.iterrows():
                prog_pct = min(1.0, run["current_units"] / run["target_units"]) if run["target_units"] > 0 else 0.0
                st.markdown(
                    f"<div style='text-align:left; margin-bottom: 4px; margin-top:8px;'><b style='color:white; font-size:1.1rem;'>{run['resin_type']}</b> &nbsp;|&nbsp; <span style='color:#94A3B8;'>{run['pump_station']}</span><span style='float:right; color:#00D2FF; font-weight:bold;'>{run['current_units']:,} / {run['target_units']:,}</span></div>",
                    unsafe_allow_html=True)
                st.progress(prog_pct)
        else:
            st.info("No active Work Orders in progress.")
    else:
        st.info("No Work Orders configured.")
    st.markdown("</div>", unsafe_allow_html=True)

import time

# Wait 10 seconds, then force the entire script to run again from top to bottom
time.sleep(10)
st.rerun()