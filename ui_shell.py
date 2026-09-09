"""The shared page shell: top navigation, sidebar router, account popover.

This was 131 lines copy-pasted into eleven manager pages. That duplication was
not just bulk - it was a defect source. The theme-change crash fixed earlier
today existed in eight pages at once because the block had been pasted eight
times and half the copies were missing an import. One copy means one fix.

render_shell() is deliberately a straight lift of that block, not a rewrite:
same widgets, same keys, same cookie manager key, same order. The only
parameter exists so Mgr_Log_Management keeps rendering exactly what it
rendered before - it never had the account popover. Drop the argument there
whenever you want that page to match the others.
"""

import streamlit as st
import extra_streamlit_components as stx
from datetime import datetime, timedelta

from database import (do_logout, get_avatar_path, role_can_administer,
                      role_can_view_scada, can, get_plant_settings,
                      set_cookie, flash, draw_flashes)

try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; }</style>"}


# What a phone needs to save this to a home screen and have it look like an
# application rather than a bookmark: an icon at the size iOS asks for, and a
# manifest so Android uses the same one and the right name underneath it. Both
# are served out of static/ (see .streamlit/config.toml). Operators meet this
# every shift before they have opened anything, which is why it is worth the
# five files it costs.
_HEAD_LINKS = """
<link rel="apple-touch-icon" sizes="180x180" href="./app/static/apple-touch-icon.png">
<link rel="icon" type="image/png" href="./app/static/favicon.png">
<link rel="manifest" href="./app/static/manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Pouring Log">
<meta name="theme-color" content="#0B1220">
"""


def inject_app_icons():
    """Once per page render. Cheap, and idempotent if it happens twice."""
    st.markdown(_HEAD_LINKS, unsafe_allow_html=True)


def handbook_link():
    """The operations handbook, as a grey line rather than a button.

    One definition, called from every sidebar. It was written inline the first
    time and only reached two of the six sidebars in the app - Manager
    Cockpit, Analytics, Live Reactors and IT Admin all build their own, so a
    manager spent their whole day on pages that did not have it. That is what
    a copied snippet does; this is why it is a function.

    Discreet on purpose: it is something you go and find once, not something
    you need in front of you. Discreet is not invisible though, so it sits at
    0.7 rather than the 0.55 it started at.
    """
    st.markdown(
        '<div style="margin-top:8px; font-size:0.8rem; opacity:0.7;">'
        '<a href="./app/static/Formlabs_MES_Handbook.pdf" target="_blank" '
        'style="color:inherit; text-decoration:none;">'
        '📘 Operations handbook (PDF)</a></div>',
        unsafe_allow_html=True)


def _install_crash_reporting():
    """Attach the crash reporter, once per process.

    Here rather than in each page because Streamlit routes every uncaught page
    exception through one function, so one patch covers all eighteen pages
    including the seven that predate this shell, and no page has to remember
    to wrap itself in anything.

    Everything is inside the try. This runs on the way into every render, and
    a crash reporter that crashes is strictly worse than no crash reporter.
    """
    try:
        import error_report
        import crud

        def record(payload):
            return crud.record_error_report(
                payload,
                user_name=st.session_state.get("user_name"),
                user_role=st.session_state.get("user_role"),
                app_version=st.session_state.get("app_version"),
            )

        def where():
            try:
                return st.context.url.rsplit("/", 1)[-1] or "Home"
            except Exception:
                return st.session_state.get("current_page") or ""

        error_report.install(recorder=record, page_name=where)
    except Exception:
        pass


def apply_display_preferences(cookie_manager=None):
    """Inject glove mode and night dimming for this render, if active.

    Public because seven pages predate the shared shell and build their own
    cookie manager - they call this directly with it. Reading the cookie here
    rather than relying on session state matters: an operator who lands
    straight on the workstation page has no session state from anywhere else,
    and glove mode is exactly the setting that must survive that.

    The home-screen icons ride along here for the same reason: this is the one
    function every page in the app reaches, including the seven that predate
    the shell.
    """
    inject_app_icons()
    _install_crash_reporting()
    try:
        if cookie_manager is not None:
            try:
                if "glove_mode" not in st.session_state:
                    st.session_state["glove_mode"] = cookie_manager.get("formlabs_mes_glove") == "1"
                if "night_dim" not in st.session_state:
                    _c = cookie_manager.get("formlabs_mes_dim")
                    st.session_state["night_dim"] = True if _c is None else _c == "1"
            except Exception:
                pass
    except Exception:
        pass
    try:
        from display_modes import display_css
        from shifts import is_outside_day_shift
        night = False
        if st.session_state.get("night_dim", True):
            try:
                from database import get_plant_settings
                night = is_outside_day_shift(get_plant_settings())
            except Exception:
                night = False
        css = display_css(glove=st.session_state.get("glove_mode", False), night=night)
        if css:
            st.markdown(css, unsafe_allow_html=True)
    except Exception:
        pass


# ------------------------------------------------------------ the one menu --
#
# Every page used to write its own navigation out by hand: six bars, six
# copies of the same list, and the rule about who gets which page kept in a
# seventh place. The result was exactly what you would expect. A bar went on
# offering the plant dashboard for a day after the dashboard stopped accepting
# operators, and two bars on the same screen disagreed with each other.
#
# So the list lives here, once, and it is built by asking what this person can
# do rather than what they are called. A link that is drawn is a page that
# opens, because the door on that page asks the same question.
def nav_links():
    """(target, label, short label, icon) for every page this person reaches."""
    out = []
    if can("view_scada"):
        out.append(("Home.py", "Live SCADA", "Live SCADA", "⚡"))
    out.append(("pages/Operator_Form.py", "Operator Form", "Workstation", "📝"))
    if can("view_manager_cockpit"):
        out.append(("pages/Manager_Cockpit.py", "Manager Cockpit", "Manager", "📊"))
    out.append(("pages/Live_Reactors.py", "Live Reactors", "Reactors", "🛢️"))
    if can("view_analytics"):
        out.append(("pages/Analytics_Hub.py", "Analytics Hub", "Analytics", "🌌"))
    if role_can_administer(st.session_state.get("user_role")):
        out.append(("pages/Admin_Panel.py", "IT Admin", "IT Admin", "🛡️"))
    return out


def nav_bar():
    """The row of buttons across the top of a page. Sized to what is in it."""
    links = nav_links()
    if not links:
        return
    st.markdown("<br>", unsafe_allow_html=True)
    for col, (target, _long, short, icon) in zip(
            st.columns(len(links), gap="small"), links):
        with col:
            st.page_link(target, label=short, icon=icon, use_container_width=True)
    st.markdown("---")


def nav_menu():
    """The list down the sidebar. Same links, longer labels, no columns."""
    st.markdown("#### 🗺️ Navigation")
    for target, long_label, _short, icon in nav_links():
        st.page_link(target, label=long_label, icon=icon)
    if bool(get_plant_settings().get("enable_device_gateway", 0)) and \
            role_can_administer(st.session_state.get("user_role")):
        st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")


def render_shell(show_settings: bool = True):
    """Draw the nav bar and sidebar. Returns the page's cookie manager."""
    cookie_manager = stx.CookieManager(key=f"ghost_cookie_{st.session_state.get('user_id', '0')}")

    # Display adjustments ride on top of whichever of the 34 themes is
    # selected, so they compose with all of them instead of being a 35th.
    # Read from the cookie because both are properties of this terminal.
    try:
        if "glove_mode" not in st.session_state:
            st.session_state["glove_mode"] = cookie_manager.get("formlabs_mes_glove") == "1"
        if "night_dim" not in st.session_state:
            _c = cookie_manager.get("formlabs_mes_dim")
            st.session_state["night_dim"] = True if _c is None else _c == "1"
    except Exception:
        # A cookie manager that is not ready yet must never stop a page
        # rendering - the operator terminal is the one screen that has to
        # come up no matter what.
        st.session_state.setdefault("glove_mode", False)
        st.session_state.setdefault("night_dim", True)

    apply_display_preferences()
    current_role = st.session_state.get("user_role", "operator")

    nav_bar()

    # --- SIDEBAR: PROFILE & SETTINGS ---
    with st.sidebar:
        st.markdown("---")
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

        nav_menu()

        # The handbook, for the people who run this. Deliberately a small grey
        # line at the bottom of the menu rather than a button: it is a thing
        # you go and find once, not a thing you need in front of you.
        if can("view_manager_cockpit"):
            handbook_link()

        st.markdown("---")
        # ---------------------------

        # UNIFIED SETTINGS POPOVER
        if show_settings:
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
                    st.markdown("#### Display")
                    # Stored on the DEVICE, not the account. Glove mode is a
                    # property of where you are standing, not of who you are:
                    # a shared floor terminal wants big targets for whoever
                    # signs in next, and the same person at a desk with a
                    # mouse wants the density back. Tying it to the login
                    # would get it wrong for both.
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

            # spacing that belongs to the popover above, not to pages without it
            st.markdown("<br>", unsafe_allow_html=True)

        if current_role in ["admin", "manager"]:
            st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
            do_logout(cookie_manager)
            # switch_page raises to navigate, so an st.rerun() after it never ran.
            st.switch_page("Home.py")

    return cookie_manager
