


import base64
import time
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from dotenv import load_dotenv

from crud import delete_session, create_session, get_user_by_session_token, last_log_at
from shift_clock import PLANT_TZ, compute_shift_status
from print_build import laser_sweep
from utils import run_scheduled_backup
from record_health import record_state
from app_logger import logger

load_dotenv()
from database import (
    authenticate_user,
    container_litres,
    log_litres,
    create_user,
    get_all_resin_specs_df,
    get_all_users_df,
    get_assigned_runs_df,
    get_downtime_logs_df,
    get_plant_settings,
    role_can_administer,
    set_cookie,
    flash,
    draw_flashes,
    get_production_logs_df,
    init_db,
    seed_initial_data,
    backfill_foreign_keys,
    update_user_theme,
    add_suggestion,
    do_logout,
)
from database import esc
from resin_palette import resin_chip, stored_color_map, style_resin_column

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
printer_b64 = get_base64_image("assets/form_printer.png")

# --- INITIALIZE SESSION STATE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = None
    st.session_state["user_name"] = None
    st.session_state["user_id"] = None
    st.session_state["preferred_theme"] = "Default Dark"

# We add a lock so we ONLY check the browser cookie once!
if "theme_loaded_from_cookie" not in st.session_state:
    st.session_state["theme_loaded_from_cookie"] = False

# --- PERSISTENT COOKIE MANAGER MUST LOAD FIRST ---
cookie_manager = stx.CookieManager(key="home_cookies")

# --- BULLETPROOF THEME ENGINE ---
cached_theme = cookie_manager.get(cookie="formlabs_mes_theme")

# ONLY apply the cookie if we haven't loaded it yet this session
if cached_theme and cached_theme in THEMES and not st.session_state["theme_loaded_from_cookie"]:
    st.session_state["preferred_theme"] = cached_theme
    st.session_state["theme_loaded_from_cookie"] = True

# Always trust the fast internal memory from here on out
active_theme = st.session_state.get("preferred_theme", "Default Dark")

# Change this variable to easily update the version across the app!
APP_VERSION = "PT-V3.31"

_signed_in = bool(st.session_state.get("authenticated", False))

st.set_page_config(
    page_title="Pouring Log | Formlabs",
    page_icon="static/app-icon.png",
    layout="wide",
    # "auto", not "expanded". Expanded is a fixed instruction that ignores the
    # screen it lands on: on a phone the sidebar is an overlay about 320px
    # wide, so forcing it open on a 390px screen covers four fifths of the
    # page and the operator's first action every time is to close something
    # they did not open. "auto" is expanded on a desktop or the wall display
    # and collapsed on a phone - which is where the operators actually are.
    initial_sidebar_state="auto",
)

# Nothing is written to the sidebar until after sign-in, so on the login screen
# it renders as an empty panel taking a third of the width. Streamlit has no
# server-side "no sidebar on this render" switch - initial_sidebar_state only
# applies on the first page load, so collapsing it here would leave it collapsed
# after login too. Hiding it while signed out is scoped to exactly that state
# and reverts the moment the operator is authenticated.
if not _signed_in:
    st.markdown("""
    <style>
      [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      [data-testid="stAppViewContainer"] > section:first-of-type { display: none !important; }
    </style>
    """, unsafe_allow_html=True)


st.logo("assets/formlabs_logo.png")

# ===================== DYNAMIC THEME INJECTION =====================
# If we just manually clicked a theme, grab it straight from session memory
if st.session_state.get("theme_just_changed") and st.session_state.get("preferred_theme") in THEMES:
    current_css_theme = st.session_state["preferred_theme"]
else:
    current_css_theme = active_theme

st.markdown(THEMES[current_css_theme], unsafe_allow_html=True)
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
# ===================================================================

init_db()
seed_initial_data()


@st.cache_resource
def _announce_database_once():
    """Advertises this machine's database on the local network via mDNS so
    a Device Gateway on another floor PC can find it automatically instead
    of a manually-typed DB_URL - see service_announcer.py. Wrapped in
    st.cache_resource the same way as the FK backfill just below, so it
    only actually runs once per server process despite Streamlit
    re-executing this script on every rerun."""
    from service_announcer import start_announcing
    start_announcing()


_announce_database_once()


@st.cache_resource
def _run_fk_backfill_once():
    """Guarded with cache_resource so this only runs once per server process —
    it's safe to call repeatedly (it only touches rows still missing an FK),
    but there's no reason to re-query it on every 10s auto-refresh rerun."""
    backfill_foreign_keys()
    return True


_run_fk_backfill_once()


@st.cache_data(ttl=3600, show_spinner=False)
def _daily_backup_check(_hour_bucket):
    """Take a backup if the newest one is a day old.

    There is no scheduler on a plant PC, and adding one is a second thing to
    install, configure and forget - so the check rides on the application
    being opened, which on a working day it is. The hour bucket is the cache
    key rather than a value anybody uses: it makes this run at most once an
    hour per server process instead of on every rerun of a page that
    refreshes itself every ten seconds.

    backup_policy decides whether one is actually due; almost every call
    here does nothing but read a directory listing.
    """
    return run_scheduled_backup()


_daily_backup_check(datetime.now().strftime("%Y%m%d%H"))

# --- BLOCK ZOMBIE COOKIES & HANDLE LOGOUT ---
if st.query_params.get("logged_out") == "true":
    st.session_state["explicitly_logged_out"] = True
    st.query_params.clear()

if st.session_state.get("explicitly_logged_out", False):
    cached_token = None
    try:
        cookie_manager.delete("formlabs_mes_token")
    except:
        pass
else:
    cached_token = cookie_manager.get(cookie="formlabs_mes_token")

# --- PERSISTENT AUTO-LOGIN ENGINE ---
if not st.session_state["authenticated"] and cached_token is not None:
    # noinspection bad-argument-type
    user_data = get_user_by_session_token(cached_token)

    if user_data:
        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user_data["id"]
        st.session_state["user_role"] = user_data["role"]
        st.session_state["user_name"] = user_data["full_name"]
        st.session_state["user_shift"] = user_data.get("shift", "Shift 1")
        st.session_state["preferred_theme"] = user_data.get("preferred_theme", "Default Dark")
        st.session_state["avatar_filename"] = user_data.get("avatar_filename")
        if user_data["role"] in ["operator", "packer"]:
            st.switch_page("pages/Operator_Form.py")
        else:
            st.rerun()


if not st.session_state["authenticated"]:
    # The front door says which system this is. A plant running this as a
    # record was greeting its operators - and anyone being shown it for the
    # first time - with SCADA TERMINAL over MANUFACTURING EXECUTION SYSTEM,
    # which is the largest claim the application makes and, in that
    # configuration, not a true one. Set the mode to an execution system and
    # the original wording comes back, because then it is.
    #
    # Read before authentication on purpose: this is the one screen that has
    # to describe the plant to somebody who has not signed in yet.
    try:
        _login_simple = bool(get_plant_settings().get("simple_mode", True))
    except Exception:
        _login_simple = True
    if _login_simple:
        _title_lead, _title_tail = "POURING", "LOG"
        _title_sub = "Resin Pouring &middot; Production Record"
    else:
        _title_lead, _title_tail = "SCADA", "TERMINAL"
        _title_sub = "Manufacturing Execution System"

    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.2, 1])
    with auth_col2:
        # The machine this plant's resin goes into, with a laser passing over
        # it once as the screen arrives. It is the front door of a printing
        # company's software and it should look like one - but it plays once
        # and stops, because a login screen that never settles is a login
        # screen people learn to look away from.
        if printer_b64:
            # The stroke is asked for on the first two renders and no more.
            # Render one is the page arriving; render two is the cookie
            # component coming back with what it found, which re-runs the
            # script. The laser's own delay means render one's is still
            # waiting when render two replaces it, so exactly one stroke is
            # ever seen moving. From render three on - typing a PIN, ticking
            # the box - the machine is drawn without it, and the screen
            # settles instead of glitching every time somebody touches it.
            _sweeps = st.session_state.get("_signin_renders", 0) + 1
            st.session_state["_signin_renders"] = _sweeps
            st.markdown(laser_sweep(printer_b64, height_px=132, uid="signin",
                                    play=_sweeps <= 2),
                        unsafe_allow_html=True)

        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom:22px;">
                <div style="display:flex; justify-content:center; align-items:center; margin-bottom:10px;">
                    <img src="data:image/png;base64,{logo_b64}" style="height: 66px; object-fit: contain; filter: drop-shadow(0px 0px 10px rgba(0, 210, 255, 0.5));">
                </div>
                <h1 style="color:#FFFFFF; font-weight:800; margin-top: 15px; font-size: clamp(1.5rem, 6vw, 2.8rem); letter-spacing: 0.02em;">{_title_lead} <span style="color:#00D2FF; font-weight:300;">{_title_tail}</span></h1>
                <p style="color:#00D2FF; font-family: monospace; letter-spacing: 0.15em; font-size: 0.85rem; text-transform: uppercase; border-top: 1px solid #1E293B; border-bottom: 1px solid #1E293B; padding: 8px 0; display: inline-block;">{_title_sub}</p>
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
                                                  help="Keeps you signed in on this phone for 30 days. Do not tick it on a shared device.")
                    st.markdown("<br>", unsafe_allow_html=True)

                    if st.form_submit_button("INITIALIZE SESSION", type="primary", use_container_width=True):
                        user, auth_error = authenticate_user(log_user, log_pin)
                        if user:
                            # Capture theme from user profile and set theme cookie
                            user_theme = user.get("preferred_theme", "Default Dark")
                            set_cookie(cookie_manager, "formlabs_mes_theme", user_theme,
                                               expires_at=datetime.now() + timedelta(days=30), key="set_theme_cookie")

                            # ONLY SET COOKIE IF CHECKBOX IS TICKED
                            if remember_device:
                                session_token = create_session(user["id"])
                                set_cookie(cookie_manager, "formlabs_mes_token", session_token,
                                                   expires_at=datetime.now() + timedelta(days=30),
                                                   key="set_token_cookie")

                            st.session_state["authenticated"] = True
                            st.session_state["user_id"] = user["id"]
                            st.session_state["user_role"] = user["role"]
                            st.session_state["user_name"] = user["full_name"]
                            st.session_state["user_shift"] = user.get("shift", "Shift 1")
                            st.session_state["preferred_theme"] = user_theme
                            st.session_state["avatar_filename"] = user.get("avatar_filename")

                            # --- NEW REDIRECT LOGIC ---
                            if user["role"] in ["operator", "packer"]:
                                st.switch_page("pages/Operator_Form.py")
                            else:
                                st.rerun()
                        else:
                            st.error(f"❌ {auth_error or 'Authorization Denied: Invalid Credentials.'}")

            # Look how reg_tab is now properly aligned with log_tab!
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
                    if st.form_submit_button("REGISTER & AUTHENTICATE", type="primary", use_container_width=True):
                        if "@" not in reg_email or "." not in reg_email:
                            st.error("⚠️ Invalid email address format.")
                        elif reg_name.strip() and reg_user.strip() and reg_pin.strip() and reg_email.strip():
                            success = create_user(
                                username=reg_user, email=reg_email, pin=reg_pin, full_name=reg_name,
                                role="operator",  # self-registration can never grant anything above operator
                                target_lph=400.0, shift=reg_shift, theme="Default Dark"
                            )
                            if success:
                                st.success("✅ Credentials logged! You may now sign in.")
                            else:
                                st.error("❌ Operator ID or email is already registered.")
                        else:
                            st.warning("⚠️ All clearance fields are required.")

        # --- OUT OF SIGHT THEME SELECTOR ---
        # Look how it's completely outside the forms and tabs now!
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🎨 Login Screen Appearance", expanded=False):

            def update_unauth_theme():
                new_theme = st.session_state.unauth_theme_selector
                set_cookie(cookie_manager, "formlabs_mes_theme", new_theme,
                                   expires_at=datetime.now() + timedelta(days=365),
                                   key="set_theme_unauth")
                st.session_state["preferred_theme"] = new_theme
                st.session_state["theme_just_changed"] = True

            st.selectbox(
                "Select Theme",
                list(THEMES.keys()),
                index=list(THEMES.keys()).index(active_theme) if active_theme in THEMES else 0,
                label_visibility="collapsed",
                key="unauth_theme_selector",
                on_change=update_unauth_theme
            )

        # --- CRITICAL FIX: STOP THE PAGE FROM RENDERING ---
        st.stop()

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

#- SIDEBAR: PROFILE & SETTINGS ---
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

    # --- CUSTOM ROUTER MENU ---
    st.markdown("#### 🗺️ Navigation")
    st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    st.page_link("pages/Live_Reactors.py", label="Live Reactors", icon="🛢️", use_container_width=True)

    # Only show Manager and Analytics to Managers/Admins
    if st.session_state.get("user_role") in ["manager", "admin"]:
        st.page_link("pages/Manager_Cockpit.py", label="Manager Cockpit", icon="📊", use_container_width=True)
        st.page_link("pages/Analytics_Hub.py", label="Analytics Hub", icon="🌌", use_container_width=True)

    # In execution mode this is administrators only. In logging mode there is
    # no separate IT role and a manager reaches it too - see
    # crud.can_administer.
    if role_can_administer(st.session_state.get("user_role")):
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)

    st.markdown("---")
    # --------------------------

    # UNIFIED SETTINGS POPOVER
    with st.popover("⚙️ Account & Preferences", use_container_width=True):
        set_tab1, set_tab2, set_tab3 = st.tabs(["🔑 Security", "🎨 Theme & Avatar", "💡 Feedback"])

        with set_tab1:
            st.markdown("#### Update Account Credentials")
            with st.form("user_cred_form"):
                acc_name = st.text_input("Full Display Name", value=st.session_state.get("user_name", ""))
                acc_user = st.text_input("Username / ID", value=st.session_state.get("username", ""))
                acc_pin = st.text_input("New PIN / Password", type="password", placeholder="Leave blank to keep current PIN")

                if st.form_submit_button("💾 Save Credentials", type="primary", use_container_width=True):
                    from database import update_user_credentials
                    success, msg = update_user_credentials(st.session_state["user_id"], acc_user, acc_pin, acc_name)
                    if success:
                        st.session_state["user_name"] = acc_name.strip()
                        st.session_state["username"] = acc_user.lower().strip()
                        st.toast(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with set_tab2:
            st.markdown("#### Interface Preferences")
            current_t = st.session_state.get("preferred_theme", "Default Dark")
            chosen_t = st.selectbox("System Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(current_t) if current_t in THEMES else 0)

            if chosen_t != current_t:
                from database import update_user_theme
                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
                set_cookie(cookie_manager, "formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
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

        with set_tab3:
            st.markdown("#### Universal Feedback Box")
            with st.form("settings_sug_form", clear_on_submit=True):
                s_cat = st.selectbox("Category", ("Feature Request", "App Bug / Error", "Plant Floor Issue"))
                s_txt = st.text_area("Observation / Description")
                if st.form_submit_button("🚀 Submit Feedback", type="primary", use_container_width=True):
                    if s_txt.strip():
                        from database import add_suggestion
                        add_suggestion(st.session_state.get("user_name"), st.session_state.get("user_role"), s_cat, s_txt)
                        st.success("✅ Submitted to IT Admin!")

    st.markdown("<br>", unsafe_allow_html=True)

    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        # No switch_page here: this IS Home. And no st.rerun() after one
        # anywhere, because switch_page raises to navigate and anything
        # following it never runs. do_logout has already cleared the session,
        # so a plain rerun draws the sign-in screen.
        st.rerun()



df_logs = get_production_logs_df()
df_dt = get_downtime_logs_df()
df_runs = get_assigned_runs_df()
specs_df = get_all_resin_specs_df("ALL")
_resin_colours = stored_color_map(specs_df)

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

# --- is the record still being fed? ---------------------------------------
# Above the header, before the filters, before every figure on the page -
# because every one of those figures is computed from the log and every one
# of them looks entirely normal when the log has stopped arriving. Yesterday's
# numbers under today's date is the most convincing wrong answer this
# application can give, and this line is the only thing on the screen that
# can tell a quiet plant from a system nobody is reaching. See record_health
# for why silence off-shift is deliberately not a fault.
_shift_now = compute_shift_status(get_plant_settings())
_health = record_state(last_log_at(), _shift_now["is_active"],
                       shift_started_at=_shift_now.get("started_at"))
if _health["is_alarm"]:
    st.error(f"🔴 **The record has stopped.** {_health['message']}")
elif _health["state"] == "quiet":
    st.warning(f"🟠 {_health['message']}")

st.markdown(
    f"""
<div class="brand-header" style="flex-wrap: wrap; gap: 15px;">
    <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 10px;">
        <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain;">
        <div class="system-badge" style="margin-left: 0px;">{APP_VERSION}</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# No hardcoded colours here. This header used to be #FFFFFF on a card, which
# is fine on the twenty-four dark themes and invisible on the six light ones -
# white text on a cream card, on the landing screen, in the first thing anyone
# sees. The point of a palette is that a component takes its colour from the
# theme instead of assuming one, so this inherits and the caption is dimmed by
# opacity, which works in both directions.
st.markdown(
    '<div class="filter-section-card"><div style="display:flex;'
    ' justify-content:space-between; align-items:center;'
    ' margin-bottom:8px;"><b style="font-size:0.95rem; color:inherit;">🔍 TIME'
    ' HORIZON &amp; PRODUCTION FILTERS</b><span style="font-size:0.75rem;'
    ' color:inherit; opacity:0.72;">All top statistics and tables calculate'
    " based on these filters.</span></div></div>",
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
        st.markdown(
            f"""<div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding-top:6px;">
                <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; border-radius: 20px; padding: 6px 12px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.08em; white-space: nowrap;">
                    ● PLANT FLOOR LIVE SYNC
                </span>
                <span style="color:#94A3B8; font-size:0.85rem;">Showing live production for today ({date.today().strftime('%Y-%m-%d')}).</span>
            </div>""",
            unsafe_allow_html=True,
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
        _live_shift_status = compute_shift_status(settings)
        if _live_shift_status["is_active"]:
            filtered_df = filtered_df[
                (filtered_df["date_obj"] == today_d) &
                (filtered_df["shift"] == _live_shift_status["shift_name"])
                ]
        else:
            # No shift is actually running right now — "Live Today" should
            # show nothing rather than leaking into whichever shift the
            # old logic defaulted to.
            filtered_df = filtered_df.iloc[0:0]
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
            rps_jug_count += int(b_count)
        elif "PIGMENT" not in c_type.upper():
            v2_cart_count += int(b_count)

        # One definition of how much a row is worth, in crud.log_litres, so the
        # tanks and the totals can never disagree about it - including on a
        # bulk pour, where the volume is measured rather than counted.
        liters_output += log_litres(b_count, c_type, r.get("litres_poured"))
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

shift_status = compute_shift_status(settings)
is_shift_active = shift_status["is_active"]
active_shift_name = shift_status["shift_name"]
elapsed_net = shift_status["elapsed_net"]
active_shift_net = shift_status["shift_net_hours"]
shift_pct = shift_status["shift_pct"]

operating_hours = elapsed_net if (time_horizon == "⚡ Live Today (Active Shift)" and is_shift_active) else active_shift_net

run_velocity_lh = (liters_output / operating_hours) if operating_hours > 0 else 0.0
pack_velocity_uh = (total_packed / operating_hours) if operating_hours > 0 else 0.0
oee_pct = (run_velocity_lh / target_rate_lh) * 100.0 if target_rate_lh > 0 else 0.0
yield_pct = (total_poured / (total_poured + total_scrap) * 100.0) if (total_poured + total_scrap) > 0 else 100.0

# 2. Dynamic Pace Variance Display Logic — only meaningful in Live Today
# mode. The trajectory card itself is now hidden outside that mode (see
# row2_col1 below) instead of showing stale placeholder text.
if is_shift_active and time_horizon == "⚡ Live Today (Active Shift)":
    expected_now = target_rate_lh * max(0.1, operating_hours)
    pace_variance_l = liters_output - expected_now
    expected_display = f"{expected_now:,.0f} L"
    variance_display = f"{pace_variance_l:+,.0f} L"
    status_badge = f"🟢 {active_shift_name} Active"
else:
    pace_variance_l = 0.0
    expected_display = "—"
    variance_display = "—"
    status_badge = "⏸️ Floor Idle"

remaining_hours = shift_status["remaining_hours"]
blended_rate = run_velocity_lh if operating_hours > 0.5 else target_rate_lh
projected_total = liters_output + (blended_rate * remaining_hours)

# ===================== ROLE-BASED VIEW TOGGLE =====================
current_role = st.session_state.get("user_role", "operator")

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
        if time_horizon == "⚡ Live Today (Active Shift)" and is_shift_active:
            variance_color = "#10B981" if pace_variance_l >= 0 else "#EF4444"
            st.markdown(
                f"""
                <div class="telemetry-grid-card" style="border-color:#10B981;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="telemetry-label" style="color:#10B981;">⏱️ LIVE SHIFT TRAJECTORY</span>
                        <span style="font-size:0.75rem; font-weight:800; color:#10B981;">{status_badge}</span>
                    </div>
                    <div style="font-size:1.15rem; font-weight:800; color:inherit; margin-top:4px;">{active_shift_name}</div>
                    <div style="margin:14px 0 6px;">
                        <div style="display:flex; justify-content:space-between; font-size:0.7rem; color:inherit; opacity:0.72; margin-bottom:4px;">
                            <span>{elapsed_net:.1f}h elapsed</span><span>{remaining_hours:.1f}h remaining</span>
                        </div>
                        <div style="background:#1E2B45; border-radius:6px; height:8px; overflow:hidden;">
                            <div style="background:linear-gradient(90deg,#10B981,#00D2FF); width:{shift_pct:.1f}%; height:100%; transition: width 0.4s ease;"></div>
                        </div>
                    </div>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:14px;">
                        <div><span class="telemetry-label" style="color:#00D2FF;">Expected Right Now</span><br><b style="font-size:1.3rem; color:#00D2FF;">{expected_display}</b></div>
                        <div><span class="telemetry-label" style="color:#A855F7;">Projected Shift End</span><br><b style="font-size:1.3rem; color:#A855F7;">{projected_total:,.0f} L</b></div>
                        <div><span class="telemetry-label">Pace Variance</span><br><b style="font-size:1.1rem; color:{variance_color};">{variance_display}</b></div>
                        <div><span class="telemetry-label">OEE Performance</span><br><b style="font-size:1.1rem; color:inherit;">{oee_pct:.1f}%</b></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif time_horizon == "⚡ Live Today (Active Shift)":
            next_line = (
                f"Next up: <b style='color:inherit; opacity:0.8;'>{shift_status['next_shift_label']}</b>"
                if shift_status.get("next_shift_label")
                else "Check Plant Settings for the shift schedule."
            )
            st.markdown(
                f"""
                <div class="telemetry-grid-card" style="border-color:#334155;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="telemetry-label">⏱️ LIVE SHIFT TRAJECTORY</span>
                        <span style="font-size:0.75rem; font-weight:800; color:#64748B;">⏸️ FLOOR IDLE</span>
                    </div>
                    <div style="text-align:center; padding:26px 0 10px;">
                        <div style="font-size:1rem; color:inherit; opacity:0.72;">No shift is currently running.</div>
                        <div style="font-size:0.8rem; color:inherit; opacity:0.55; margin-top:6px;">{next_line}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="telemetry-grid-card" style="border-color:#1E2B45;">
                    <div class="telemetry-label">📊 VIEWING HISTORICAL DATA</div>
                    <div style="font-size:0.95rem; color:inherit; opacity:0.72; margin-top:10px;">Live shift trajectory only applies in <b style="color:inherit;">⚡ Live Today (Active Shift)</b> mode.</div>
                    <div style="font-size:0.8rem; color:inherit; opacity:0.55; margin-top:8px;">Switch the Time Horizon filter above to see real-time shift pace.</div>
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
                    c_type = str(r.get("cartridge_type", "V2"))
                    op_liters += log_litres(b_count, c_type, r.get("litres_poured"))

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
            <div class="telemetry-val-large" style="color:#A855F7;">{total_packed:,} <span style="font-size:0.9rem; color:inherit; opacity:0.72;">units</span></div></div>""",
        unsafe_allow_html=True,
    )
    p2.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#A855F7;"><div class="telemetry-label">ESTIMATED SKIDS BUILT</div>
            <div class="telemetry-val-large" style="color:inherit;">{total_skids_est:,.1f} <span style="font-size:0.9rem; color:inherit; opacity:0.72;">skids</span></div></div>""",
        unsafe_allow_html=True,
    )
    p3.markdown(
        f"""<div class="telemetry-grid-card" style="border-color:#A855F7;"><div class="telemetry-label">PACKING VELOCITY</div>
            <div class="telemetry-val-large" style="color:#A855F7;">{pack_velocity_uh:,.0f} <span style="font-size:0.9rem; color:inherit; opacity:0.72;">Units/h</span></div></div>""",
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
                f">{resin_chip(row['resin_type'], _resin_colours.get(str(row['resin_type'])))}</b> <span"
                f" style='color:#94A3B8; font-size:0.8rem;'>({esc(row['lot_number'])})</span></span>"
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

    st.dataframe(
        style_resin_column(display_df, "resin_type", _resin_colours),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No records match the current filter selection.")





