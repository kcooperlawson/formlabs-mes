import base64
import time
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from dotenv import load_dotenv
load_dotenv()
from database import (
    authenticate_user,
    create_user,
    get_all_resin_specs_df,
    get_all_users_df,
    get_assigned_runs_df,
    get_downtime_logs_df,
    get_plant_settings,
    get_production_logs_df,
    init_db,
    seed_initial_data,
    update_user_theme,
    add_suggestion,
)

# Pull our external theme dictionary
try:
    from themes import THEMES
except ImportError:
    THEMES = {
        "Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}


@st.fragment(run_every="10s")
def auto_refresh():
    pass


auto_refresh()


@st.cache_resource
def print_terminal_logo():
    """Prints a custom ASCII logo to the terminal only once on server boot."""
    cyan = "\033[38;5;45m"
    white = "\033[97m"
    gray = "\033[38;5;240m"
    reset = "\033[0m"

    logo = f"""
{cyan}   __                     _       _{reset}
{cyan}  / _| ___  _ __ _ __ ___| | __ _| |__  ___{reset}
{cyan} | |_ / _ \\| '__| '_ ` _ \\ |/ _` | '_ \\/ __|{reset}
{cyan} |  _| (_) | |  | | | | | | | (_| | |_) \\__ \\{reset}
{cyan} |_|  \\___/|_|  |_| |_| |_|_|\\__,_|_.__/|___/{reset}
{gray} ═════════════════════════════════════════════{reset}
{white}         MES SCADA TELEMETRY TERMINAL{reset}
{cyan}         Initializing Plant Sensors...{reset}
    """
    print(logo)


print_terminal_logo()


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""


logo_b64 = get_base64_image("assets/formlabs_logo.png")

# Change this variable to easily update the version across the app!
APP_VERSION = "PT-V3.5.2"

st.set_page_config(
    page_title="Formlabs MES Live Dashboard",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.logo("assets/formlabs_logo.png")

init_db()
seed_initial_data()

# --- INITIALIZE COOKIE MANAGER ---
cookie_manager = stx.CookieManager(key="scada_cookies")

# --- INITIALIZE SESSION STATE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = None
    st.session_state["user_name"] = None
    st.session_state["user_id"] = None
    st.session_state["preferred_theme"] = "Default Dark"

# --- PERSISTENT AUTO-LOGIN ENGINE ---
cached_token = cookie_manager.get(cookie="formlabs_mes_token")

if not st.session_state["authenticated"] and cached_token is not None:
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
        st.rerun()

# ===================== DYNAMIC THEME INJECTION =====================
active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
# ===================================================================

if not st.session_state["authenticated"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.2, 1])
    with auth_col2:
        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom:30px;">
                <div style="display:flex; justify-content:center; align-items:center; margin-bottom:15px;">
                    <img src="data:image/png;base64,{logo_b64}" style="height: 85px; object-fit: contain; filter: drop-shadow(0px 0px 10px rgba(0, 210, 255, 0.5));">
                </div>
                <h1 style="color:#FFFFFF; font-weight:900; margin-top: 15px; font-size: 2.8rem; letter-spacing: 0.02em;">SCADA <span style="color:#00D2FF; font-weight:300;">TERMINAL</span></h1>
                <p style="color:#00D2FF; font-family: monospace; letter-spacing: 0.15em; font-size: 0.85rem; text-transform: uppercase; border-top: 1px solid #1E293B; border-bottom: 1px solid #1E293B; padding: 8px 0; display: inline-block;">Manufacturing Execution System</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            log_tab, reg_tab = st.tabs(["🔐 SECURE SIGN IN", "📝 REGISTER ACCESS"])

            with log_tab:
                with st.form("login_form"):
                    log_user = st.text_input(
                        "OPERATOR ID / USERNAME", placeholder="e.g. jsmith", autocomplete="username"
                    )
                    log_pin = st.text_input(
                        "SECURITY PIN",
                        type="password",
                        autocomplete="current-password",
                    )

                    # --- NEW CHECKBOX ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    remember_device = st.checkbox("💾 Remember this device", value=False,
                                                  help="Checking this keeps you logged in for 30 days. Do not use on shared tablets.")
                    st.markdown("<br>", unsafe_allow_html=True)

                    if st.form_submit_button(
                            "INITIALIZE SESSION", type="primary", use_container_width=True
                    ):
                        user = authenticate_user(log_user, log_pin)
                        if user:
                            # ONLY SET COOKIE IF CHECKBOX IS TICKED
                            if remember_device:
                                cookie_manager.set("formlabs_mes_token", user["username"],
                                                   expires_at=datetime.now() + timedelta(days=30))
                                time.sleep(1.2)  # Give browser time to save the cookie

                            st.session_state["authenticated"] = True
                            st.session_state["user_id"] = user["id"]
                            st.session_state["user_role"] = user["role"]
                            st.session_state["user_name"] = user["full_name"]
                            st.session_state["user_shift"] = user.get("shift", "Shift 1")
                            st.session_state["preferred_theme"] = user.get("preferred_theme", "Default Dark")

                            st.rerun()
                        else:
                            st.error("❌ Authorization Denied: Invalid Credentials.")

            with reg_tab:
                with st.form("register_form", clear_on_submit=True):
                    reg_name = st.text_input("FULL NAME")
                    reg_email = st.text_input("WORK EMAIL", placeholder="e.g. user@company.com")
                    reg_user = st.text_input("DESIRED OPERATOR ID")
                    reg_pin = st.text_input("CREATE SECURITY PIN", type="password")
                    reg_col1, reg_col2 = st.columns(2)
                    with reg_col1:
                        reg_role = st.selectbox("ASSIGNED ROLE", ("Operator", "Packer"))
                    with reg_col2:
                        reg_shift = st.selectbox(
                            "ASSIGNED SHIFT", ("Shift 1", "Shift 2", "Floater")
                        )

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button(
                            "REGISTER & AUTHENTICATE", type="primary", use_container_width=True
                    ):
                        if "@" not in reg_email or "." not in reg_email:
                            st.error("⚠️ Invalid email address format.")
                        elif (
                                reg_name.strip()
                                and reg_user.strip()
                                and reg_pin.strip()
                                and reg_email.strip()
                        ):
                            success = create_user(
                                username=reg_user,
                                email=reg_email,
                                pin=reg_pin,
                                full_name=reg_name,
                                role=reg_role.lower(),
                                target_lph=400.0,
                                shift=reg_shift,
                                theme="Default Dark"
                            )
                            if success:
                                st.success("✅ Credentials logged! You may now sign in.")
                            else:
                                st.error("❌ Operator ID or email is already registered.")
                        else:
                            st.warning("⚠️ All clearance fields are required.")
    st.stop()

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

                                add_suggestion(st.session_state.get("user_name"), st.session_state.get("user_role"),
                                               s_cat, s_txt)
                                st.success("✅ Submitted to IT Admin!")

                    st.markdown("---")
                    st.markdown("#### 📜 Release Notes")
                    try:
                        with open("CHANGELOG.md", "r", encoding="utf-8") as f:
                            changelog_contents = f.read()
                        with st.expander("🔍 View Version History", expanded=False):
                            st.markdown(changelog_contents)
                    except FileNotFoundError:
                        st.caption("⚠️ `CHANGELOG.md` file not found in root directory.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LAUNCH TV MODE ---
    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        # 1. Catch missing cookie errors gracefully
        try:
            cookie_manager.delete("formlabs_mes_token")
        except Exception:
            pass

        # 2. Clear authentication and session state
        st.session_state["authenticated"] = False
        st.session_state.clear()

        # 3. Force immediate redirect to the Home login page
        st.switch_page("Home.py")
        time.sleep(0.5)
        st.rerun()



df_logs = get_production_logs_df()
df_dt = get_downtime_logs_df()
df_runs = get_assigned_runs_df()
specs_df = get_all_resin_specs_df("ALL")

spec_dict = {}
if not specs_df.empty:
    for _, r in specs_df.iterrows():
        spec_dict[(
            f"{str(r['cartridge_type']).strip().lower()}_{str(r['resin_name']).strip().lower()}"
        )] = float(r["actual_spec_g"])

if not df_logs.empty:
    df_logs["date_obj"] = pd.to_datetime(df_logs["date"]).dt.date
    df_logs["date_str"] = df_logs["date_obj"].astype(str)

    df_logs["timestamp"] = pd.to_datetime(df_logs["timestamp"]).dt.tz_localize("UTC").dt.tz_convert(
        "America/New_York").dt.strftime("%Y-%m-%d %H:%M:%S")

    all_dates = sorted(df_logs["date_str"].unique().tolist(), reverse=True)
else:
    df_logs["date_obj"] = []
    df_logs["date_str"] = []
    all_dates = []

st.markdown(
    f"""
<div class="brand-header" style="flex-wrap: wrap; gap: 15px;">
    <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 10px;">
        <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain;">
        <div class="system-badge" style="margin-left: 0px;">{APP_VERSION}</div>
    </div>
    <div style="margin-top: 2px;">
        <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; border-radius: 20px; padding: 6px 12px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.08em; white-space: nowrap; display: inline-block;">
            ● PLANT FLOOR LIVE SYNC
        </span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="filter-section-card"><div style="display:flex;'
    ' justify-content:space-between; align-items:center;'
    ' margin-bottom:8px;"><b style="font-size:0.95rem; color:#FFFFFF;">🔍 TIME'
    ' HORIZON & PRODUCTION FILTERS</b><span style="font-size:0.75rem;'
    ' color:#94A3B8;">All top statistics and tables calculate based on these'
    " filters.</span></div></div>",
    unsafe_allow_html=True,
)

f1_col1, f1_col2 = st.columns((2, 3))
with f1_col1:
    time_horizon = st.selectbox(
        "⏱️ Select Time Horizon Mode:",
        (
            "⚡ Live Today (Active Shift)",
            "📅 Specific Single Day",
            "📆 Past 7 Days (Week)",
            "📊 Past 30 Days (Month)",
            "🌐 All Time History",
        ),
    )

with f1_col2:
    if time_horizon == "📅 Specific Single Day":
        selected_specific_date = st.selectbox(
            "Choose Exact Production Date:", all_dates, index=0 if all_dates else 0
        )
    elif time_horizon == "⚡ Live Today (Active Shift)":
        st.info(
            "Showing live production logged for today"
            f" ({date.today().strftime('%Y-%m-%d')})."
        )
    elif time_horizon == "📆 Past 7 Days (Week)":
        st.caption("Aggregating all runs over the rolling 7-day window.")
    elif time_horizon == "📊 Past 30 Days (Month)":
        st.caption("Aggregating all runs over the rolling 30-day window.")
    else:
        st.caption("Aggregating full plant lifetime history.")

d1, d2, d3, d4 = st.columns(4)
with d1:
    selected_pump = st.selectbox(
        "Pump Station",
        ["All Pumps"] + sorted(df_logs["pump_station"].dropna().unique().tolist())
        if not df_logs.empty
        else ["All Pumps"],
    )
with d2:
    selected_resin = st.selectbox(
        "Resin Formula",
        ["All Resins"] + sorted(df_logs["resin_type"].dropna().unique().tolist())
        if not df_logs.empty
        else ["All Resins"],
    )
with d3:
    selected_operator = st.selectbox(
        "Operator",
        ["All Operators"]
        + sorted(df_logs["operator_name"].dropna().unique().tolist())
        if not df_logs.empty
        else ["All Operators"],
    )
with d4:
    selected_shift = st.selectbox(
        "Shift",
        ["All Shifts"] + sorted(df_logs["shift"].dropna().unique().tolist())
        if not df_logs.empty
        else ["All Shifts"],
    )

filtered_df = df_logs.copy() if not df_logs.empty else pd.DataFrame()
today_d = date.today()

if not filtered_df.empty:
    if time_horizon == "⚡ Live Today (Active Shift)":
        settings = get_plant_settings()
        time_now = datetime.now()
        s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
        s2_h, s2_m = map(int, settings["shift_2_start"].split(":"))

        s1_start = time_now.replace(hour=s1_h, minute=s1_m, second=0)
        s2_start = time_now.replace(hour=s2_h, minute=s2_m, second=0)

        if s1_start <= time_now < s2_start:
            active_shift = "Shift 1"
        else:
            active_shift = "Shift 2"

        filtered_df = filtered_df[
            (filtered_df["date_obj"] == today_d) &
            (filtered_df["shift"] == active_shift)
            ]
    elif time_horizon == "📅 Specific Single Day":
        filtered_df = filtered_df[filtered_df["date_str"] == selected_specific_date]
    elif time_horizon == "📆 Past 7 Days (Week)":
        filtered_df = filtered_df[
            filtered_df["date_obj"] >= (today_d - timedelta(days=7))
            ]
    elif time_horizon == "📊 Past 30 Days (Month)":
        filtered_df = filtered_df[
            filtered_df["date_obj"] >= (today_d - timedelta(days=30))
            ]

    if selected_pump != "All Pumps":
        filtered_df = filtered_df[filtered_df["pump_station"] == selected_pump]
    if selected_resin != "All Resins":
        filtered_df = filtered_df[filtered_df["resin_type"] == selected_resin]
    if selected_operator != "All Operators":
        filtered_df = filtered_df[
            filtered_df["operator_name"] == selected_operator
            ]
    if selected_shift != "All Shifts":
        filtered_df = filtered_df[filtered_df["shift"] == selected_shift]

pour_df = (
    filtered_df[filtered_df["log_type"] == "Hourly Bottle Count"]
    if not filtered_df.empty
    else pd.DataFrame()
)
pack_df = (
    filtered_df[filtered_df["log_type"] == "Packing Count"]
    if not filtered_df.empty
    else pd.DataFrame()
)

# --- POURING MATH ---
total_poured = int(pour_df["bottles_filled"].sum()) if not pour_df.empty else 0
total_scrap = (
    int(pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum())
    if not pour_df.empty
    else 0
)
liters_output = 0.0
resin_mass_kg = 0.0
v2_cart_count = 0
rps_jug_count = 0

if not pour_df.empty:
    for _, r in pour_df.iterrows():
        b_count = float(r.get("bottles_filled", 0) or 0)
        c_type = str(r.get("cartridge_type", "V2")).strip()
        r_name = str(r.get("resin_type", "")).strip()
        if "RPS" in c_type.upper():
            vol_mult = 5.0
            rps_jug_count += int(b_count)
        elif "PIGMENT" in c_type.upper():
            vol_mult = 0.124
        else:
            vol_mult = 1.0
            v2_cart_count += int(b_count)

        liters_output += b_count * vol_mult
        lookup_key = f"{c_type.lower()}_{r_name.lower()}"
        unit_g = spec_dict.get(
            lookup_key, 5500.0 if "RPS" in c_type.upper() else 1110.0
        )
        resin_mass_kg += b_count * (unit_g / 1000.0)

# --- PACKING MATH ---
total_packed = (
    int(pack_df["bottles_filled"].sum()) if not pack_df.empty else 0
)
unpacked_wip = total_poured - total_packed
total_skids_est = 0.0

if not pack_df.empty:
    for _, r in pack_df.iterrows():
        b_count = float(r.get("bottles_filled", 0) or 0)
        skid_size = 500
        if not specs_df.empty:
            match = specs_df[specs_df["resin_name"] == r["resin_type"]]
            if not match.empty:
                skid_size = float(match.iloc[0].get("units_per_skid", 500))
        if skid_size > 0:
            total_skids_est += b_count / skid_size

# --- SHIFT ACTIVITY & LIVE PACE VARIANCE ENGINE ---
settings = get_plant_settings()
target_rate_lh = float(settings.get("target_lph", 400.0))

time_now = datetime.now()
s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
s2_h, s2_m = map(int, settings["shift_2_start"].split(":"))

s1_gross = float(settings["shift_1_hours"])
s2_gross = float(settings["shift_2_hours"])

s1_break = float(settings.get("shift_1_break_mins", 60.0)) / 60.0
s2_break = float(settings.get("shift_2_break_mins", 60.0)) / 60.0

s1_net = max(0.1, s1_gross - s1_break)
s2_net = max(0.1, s2_gross - s2_break)

s1_start_time = time_now.replace(hour=s1_h, minute=s1_m, second=0)
s2_start_time = time_now.replace(hour=s2_h, minute=s2_m, second=0)
s1_end_time = s1_start_time + timedelta(hours=s1_gross)
s2_end_time = s2_start_time + timedelta(hours=s2_gross)

# 1. Determine if a shift is currently active
is_shift_active = False
active_shift_name = "Off-Shift"
elapsed_gross = 0.0
active_shift_net = s1_net

if s1_start_time <= time_now < s1_end_time:
    is_shift_active = True
    active_shift_name = "Shift 1"
    active_shift_net = s1_net
    elapsed_gross = (time_now - s1_start_time).total_seconds() / 3600.0
    elapsed_net = elapsed_gross * (s1_net / s1_gross)
elif s2_start_time <= time_now < s2_end_time:
    is_shift_active = True
    active_shift_name = "Shift 2"
    active_shift_net = s2_net
    elapsed_gross = (time_now - s2_start_time).total_seconds() / 3600.0
    elapsed_net = elapsed_gross * (s2_net / s2_gross)
else:
    is_shift_active = False
    elapsed_net = 0.0

operating_hours = elapsed_net if (time_horizon == "⚡ Live Today (Active Shift)" and is_shift_active) else active_shift_net

run_velocity_lh = (liters_output / operating_hours) if operating_hours > 0 else 0.0
pack_velocity_uh = (total_packed / operating_hours) if operating_hours > 0 else 0.0
oee_pct = (run_velocity_lh / target_rate_lh) * 100.0 if target_rate_lh > 0 else 0.0
yield_pct = (total_poured / (total_poured + total_scrap) * 100.0) if (total_poured + total_scrap) > 0 else 100.0

# 2. Dynamic Pace Variance Display Logic
if is_shift_active and time_horizon == "⚡ Live Today (Active Shift)":
    expected_now = target_rate_lh * max(0.1, operating_hours)
    pace_variance_l = liters_output - expected_now
    expected_display = f"{expected_now:,.0f} L"
    variance_display = f"{pace_variance_l:+,.0f} L"
    status_badge = f"🟢 {active_shift_name} Active"
else:
    pace_variance_l = 0.0
    expected_display = "⏸️ Shift Standby"
    variance_display = "⏸️ Idle / Off-Hours"
    status_badge = "🔴 No Active Shift"

remaining_hours = max(0.0, active_shift_net - operating_hours)
blended_rate = run_velocity_lh if operating_hours > 0.5 else target_rate_lh
projected_total = liters_output + (blended_rate * remaining_hours)

# ===================== ROLE-BASED VIEW TOGGLE =====================
current_role = st.session_state.get("user_role", "operator")
# --- EMERGENCY RESET BUTTON (TEMPORARY) ---
if st.button("🚨 EMERGENCY LOGOUT & RESET APP", type="primary", use_container_width=True):
    cookie_manager.delete("formlabs_mes_token")
    st.session_state.clear()
    import time
    time.sleep(1)
    st.rerun()
# ------------------------------------------
settings = get_plant_settings()
packing_enabled = settings.get("enable_packing", True)

st.markdown("<br>", unsafe_allow_html=True)

if not packing_enabled:
    # If Packing is disabled globally in Plant Settings, force Pouring view only
    view_mode = "💧 Pouring Operations"
    st.markdown(
        "<h4 style='color:#00D2FF;'>💧 POURING OPERATIONS DASHBOARD</h4>",
        unsafe_allow_html=True,
    )
else:
    # Normal role-based view selection when packing IS enabled
    if current_role == "manager":
        view_mode = st.radio(
            "📊 SELECT DASHBOARD VIEW:",
            ["💧 Pouring Operations", "📦 Packing Operations", "🌐 Master Combined View"],
            horizontal=True,
        )
    elif current_role == "packer":
        view_mode = "📦 Packing Operations"
        st.markdown(
            "<h4 style='color:#A855F7;'>📦 PACKING OPERATIONS DASHBOARD</h4>",
            unsafe_allow_html=True,
        )
    else:
        view_mode = "💧 Pouring Operations"
        st.markdown(
            "<h4 style='color:#00D2FF;'>💧 POURING OPERATIONS DASHBOARD</h4>",
            unsafe_allow_html=True,
        )

show_pouring = view_mode in [
    "🌐 Master Combined View",
    "💧 Pouring Operations",
]
show_packing = view_mode in [
    "🌐 Master Combined View",
    "📦 Packing Operations",
]

show_pouring = view_mode in [
    "🌐 Master Combined View",
    "💧 Pouring Operations",
]
show_packing = view_mode in [
    "🌐 Master Combined View",
    "📦 Packing Operations",
]

# ===================== 💧 POURING UI =====================
if show_pouring:
    if current_role == "manager" or view_mode == "🌐 Master Combined View":
        st.markdown(
            "<h4 style='color:#00D2FF; margin-top:10px;'>💧 POURING TELEMETRY</h4>",
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f"""<div class="telemetry-grid-card"><div class="telemetry-label">VOLUME OUTPUT</div>
            <div class="telemetry-val-large">{liters_output:,.0f} <span style="font-size:0.9rem; color:#94A3B8;">L</span></div>
            <div class="telemetry-subtext">{v2_cart_count} V2 | {rps_jug_count} RPS</div></div>""",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"""<div class="telemetry-grid-card"><div class="telemetry-label">RESIN MASS POURED</div>
            <div class="telemetry-val-large">{resin_mass_kg:,.1f} <span style="font-size:0.9rem; color:#94A3B8;">kg</span></div>
            <div class="telemetry-subtext">Calculated from Specs</div></div>""",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"""<div class="telemetry-grid-card"><div class="telemetry-label">RUN VELOCITY</div>
            <div class="telemetry-val-large" style="color:#00D2FF;">{run_velocity_lh:.1f} <span style="font-size:0.9rem; color:#94A3B8;">L/h</span></div>
            <div class="telemetry-subtext">Target: <b>{target_rate_lh:.0f} L/h</b></div></div>""",
        unsafe_allow_html=True,
    )
    c4.markdown(
        f"""<div class="telemetry-grid-card"><div class="telemetry-label">POURING YIELD</div>
            <div class="telemetry-val-large" style="color:#10B981;">{yield_pct:.1f}%</div>
            <div class="telemetry-subtext"><span class="telemetry-subtext-green">{total_scrap} scrap units</span></div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    row2_col1, row2_col2 = st.columns((2, 1.3))
    with row2_col1:
        st.markdown(
            f"""
            <div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="color:#10B981; font-size:1.1rem;">⏱️ LIVE SHIFT TRAJECTORY</b>
                    <span style="font-size:0.8rem; font-weight:800; color:#94A3B8;">{status_badge}</span>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-top:12px;">
                    <div><span class="telemetry-label" style="color:#00D2FF;">Expected Right Now</span><br><b style="font-size:1.4rem; color:#00D2FF;">{expected_display}</b></div>
                    <div><span class="telemetry-label" style="color:#A855F7;">Projected Shift End</span><br><b style="font-size:1.4rem; color:#A855F7;">{projected_total:,.0f} L</b></div>
                    <div style="margin-top:8px;"><span class="telemetry-label">Pace Variance</span><br><b style="font-size:1.2rem; color:{'#10B981' if is_shift_active and pace_variance_l >= 0 else ('#EF4444' if is_shift_active else '#94A3B8')};">{variance_display}</b></div>
                    <div style="margin-top:8px;"><span class="telemetry-label">OEE Performance</span><br><b style="font-size:1.2rem; color:#FFFFFF;">{oee_pct:.1f}%</b></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with row2_col2:
        st.markdown(
            "<div class='operator-card'><div class='telemetry-label'"
            " style='margin-bottom:12px;'>🔥 POURING LEADERBOARD</div>",
            unsafe_allow_html=True,
        )
        if not pour_df.empty:
            op_stats = []
            for op in pour_df["operator_name"].unique():
                op_data = pour_df[pour_df["operator_name"] == op]

                op_liters = 0.0
                for _, r in op_data.iterrows():
                    b_count = float(r.get("bottles_filled", 0) or 0)
                    c_type = str(r.get("cartridge_type", "V2")).upper()
                    vol_mult = 5.0 if "RPS" in c_type else (0.124 if "PIGMENT" in c_type else 1.0)
                    op_liters += (b_count * vol_mult)

                timestamps = pd.to_datetime(op_data["timestamp"])
                time_span_hours = (timestamps.max() - timestamps.min()).total_seconds() / 3600.0

                op_hours = min(operating_hours, max(1.0, time_span_hours + 1.0))

                op_vel = op_liters / op_hours if op_hours > 0 else 0
                op_stats.append((op, op_vel))

            op_stats.sort(key=lambda x: x[1], reverse=True)

            for rank, (op, vel) in enumerate(op_stats[:3]):
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between;"
                    " border-bottom:1px solid #1E2B45; padding-bottom:6px;"
                    f" margin-bottom:6px;'><span>#{rank + 1} <b>{op}</b></span> <span"
                    " style='color:#00D2FF;"
                    f" font-weight:bold;'>{vel:,.0f} L/h</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No pouring logged.")
        st.markdown("</div>", unsafe_allow_html=True)

# ===================== 📦 PACKING UI =====================
if show_packing:
    if current_role == "manager" or view_mode == "🌐 Master Combined View":
        st.markdown(
            "<br><h4 style='color:#A855F7; margin-top:10px;'>📦 PACKING"
            " TELEMETRY</h4>",
            unsafe_allow_html=True,
        )

    p1, p2, p3, p4 = st.columns(4)
    p1.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#A855F7;"><div class="telemetry-label">TOTAL UNITS PACKED</div>
            <div class="telemetry-val-large" style="color:#A855F7;">{total_packed:,} <span style="font-size:0.9rem; color:#94A3B8;">units</span></div></div>""",
        unsafe_allow_html=True,
    )
    p2.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#A855F7;"><div class="telemetry-label">ESTIMATED SKIDS BUILT</div>
            <div class="telemetry-val-large" style="color:#FFFFFF;">{total_skids_est:,.1f} <span style="font-size:0.9rem; color:#94A3B8;">skids</span></div></div>""",
        unsafe_allow_html=True,
    )
    p3.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#A855F7;"><div class="telemetry-label">PACKING VELOCITY</div>
            <div class="telemetry-val-large" style="color:#A855F7;">{pack_velocity_uh:,.0f} <span style="font-size:0.9rem; color:#94A3B8;">Units/h</span></div></div>""",
        unsafe_allow_html=True,
    )
    p4.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#F59E0B;"><div class="telemetry-label">UNPACKED FLOOR W.I.P.</div>
            <div class="telemetry-val-large" style="color:#F59E0B;">{unpacked_wip:,} <span style="font-size:0.9rem; color:#94A3B8;">pending</span></div></div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        "<div class='operator-card'><div class='telemetry-label'"
        " style='margin-bottom:12px; color:#A855F7;'>📦 PACKED BY RESIN &"
        " LOT</div>",
        unsafe_allow_html=True,
    )
    if not pack_df.empty:
        pack_grp = (
            pack_df.groupby(["resin_type", "lot_number"])["bottles_filled"]
            .sum()
            .reset_index()
        )
        for _, row in pack_grp.iterrows():
            skid_size = 500
            if not specs_df.empty:
                match = specs_df[specs_df["resin_name"] == row["resin_type"]]
                if not match.empty:
                    skid_size = float(match.iloc[0].get("units_per_skid", 500))
            skids = row["bottles_filled"] / skid_size if skid_size > 0 else 0
            st.markdown(
                f"<div style='display:flex; justify-content:space-between;"
                " border-bottom:1px solid #1E2B45; padding-bottom:6px;"
                " margin-bottom:6px;'><span><b"
                f" style='color:#FFFFFF;'>{row['resin_type']}</b> <span"
                f" style='color:#94A3B8; font-size:0.8rem;'>({row['lot_number']})</span></span>"
                f" <span><b style='color:#A855F7;'>{row['bottles_filled']:,}"
                f" Units</b> <span style='color:#64748B;'>({skids:.1f}"
                " Skids)</span></span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No packing logged for this filter.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# ===================== ROLE-BASED LOG STREAM FILTERING =====================
if current_role == "operator":
    stream_title = "📋 Filtered Pouring Log Stream"
    filtered_df = filtered_df[filtered_df["log_type"] == "Hourly Bottle Count"]
elif current_role == "packer":
    stream_title = "📋 Filtered Packing Log Stream"
    filtered_df = filtered_df[filtered_df["log_type"] == "Packing Count"]
else:
    stream_title = "📋 Filtered Master Production Stream"

t_head1, t_head2 = st.columns((3, 1))
with t_head1:
    st.subheader(stream_title)
    st.caption(f"Showing **{len(filtered_df)}** matching records.")
with t_head2:
    sort_choice = st.selectbox(
        "Sort Table By:",
        (
            "Newest First",
            "Oldest First",
            "Highest Bottle Count",
            "Resin Name",
        ),
    )

sorted_df = filtered_df.copy()
if not sorted_df.empty:
    if sort_choice == "Newest First":
        sorted_df = sorted_df.sort_values(by="timestamp", ascending=False)
    elif sort_choice == "Oldest First":
        sorted_df = sorted_df.sort_values(by="timestamp", ascending=True)
    elif sort_choice == "Highest Bottle Count":
        sorted_df = sorted_df.sort_values(by="bottles_filled", ascending=False)
    elif sort_choice == "Resin Name":
        sorted_df = sorted_df.sort_values(by="resin_type", ascending=True)

    display_df = sorted_df[[
        "timestamp",
        "date_str",
        "log_type",
        "operator_name",
        "pump_station",
        "cartridge_type",
        "resin_type",
        "bottles_filled",
        "scrap_empty",
        "scrap_filled",
        "notes",
    ]]

    st.markdown(
        '<div style="overflow-x:'
        f' auto;">{display_df.to_html(index=False)}</div>',
        unsafe_allow_html=True,
    )
else:
    st.info("No records match the current filter selection.")


def add_reactor(reactor_name: str, max_capacity_l: float) -> bool:
    session = ScopedSession()
    try:
        # Assuming your SQLAlchemy model is named Reactor
        session.add(Reactor(reactor_name=reactor_name.strip(), max_capacity_l=max_capacity_l))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()

def delete_reactor(reactor_id: int) -> bool:
    session = ScopedSession()
    try:
        r = session.query(Reactor).filter(Reactor.id == reactor_id).first()
        if r:
            session.delete(r)
            session.commit()
            return True
        return False
    finally:
        session.close()