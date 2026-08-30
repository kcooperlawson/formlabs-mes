

import os
import sys
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_production_logs_df, do_logout, get_all_users_df

st.set_page_config(page_title="Historical Analytics | Formlabs MES", page_icon="📈", layout="wide")

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

try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"), THEMES["Default Dark"]), unsafe_allow_html=True)

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
import extra_streamlit_components as stx

# Initialize cookie manager for the logout function
cookie_manager = stx.CookieManager(key=f"ghost_cookie_{st.session_state.get('user_id', '0')}")
current_role = st.session_state.get("user_role", "operator")

# --- TOP NAVIGATION BAR ---
st.markdown("<br>", unsafe_allow_html=True)
if current_role == "admin":
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6: st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")

# --- SIDEBAR: PROFILE & SETTINGS ---
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
                cookie_manager.set("formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
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
        st.switch_page("Home.py")
        st.rerun()

st.markdown("### 📈 Historical Plant Analytics & Production Trends")

df_logs = get_production_logs_df()

# Build operator dropdown from resolved identities: prefer each operator_id's
# CURRENT full_name so a mid-history rename shows one entry, not two. Any
# operator_name with no resolved operator_id (a deleted account, or a legacy
# name that never matched a real user) still gets its own entry so that data
# isn't silently hidden from the filter.
_users_df = get_all_users_df()
_id_to_name = dict(zip(_users_df["id"], _users_df["full_name"])) if not _users_df.empty else {}
_name_to_id = {v: k for k, v in _id_to_name.items()}

if not df_logs.empty:
    resolved_ids = df_logs["operator_id"].dropna().unique().tolist()
    resolved_names = sorted({_id_to_name[i] for i in resolved_ids if i in _id_to_name})
    unresolved_names = sorted(
        df_logs[df_logs["operator_id"].isna()]["operator_name"].dropna().unique().tolist()
    )
    operator_options = ["All Operators"] + resolved_names + unresolved_names
else:
    operator_options = ["All Operators"]

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    date_range = st.selectbox("📅 Time Horizon", ["Past 7 Days", "Past 30 Days", "Year to Date", "All Time"])
with col_f2:
    selected_resin = st.selectbox("🧪 Resin Filter", ["All Resins"] + sorted(df_logs["resin_type"].dropna().unique().tolist()) if not df_logs.empty else ["All Resins"])
with col_f3:
    selected_op = st.selectbox("👤 Operator Filter", operator_options)

today_d = date.today()
start_date_filter = None
if date_range == "Past 7 Days": start_date_filter = today_d - timedelta(days=7)
elif date_range == "Past 30 Days": start_date_filter = today_d - timedelta(days=30)
elif date_range == "Year to Date": start_date_filter = date(today_d.year, 1, 1)

# A selected name that resolves to a current user filters by operator_id (FK) —
# this pulls in every row tied to that person, even ones logged under an older
# name. A name with no resolution (deleted/legacy) falls back to an exact
# operator_name match, same as before.
selected_operator_id = _name_to_id.get(selected_op) if selected_op != "All Operators" else None
selected_operator_name = selected_op if (selected_op != "All Operators" and selected_operator_id is None) else None

hist_df = get_production_logs_df(
    start_date=start_date_filter, end_date=today_d, resin=selected_resin,
    operator=selected_operator_name, operator_id=selected_operator_id
)

if not hist_df.empty:
    hist_df['date_str'] = pd.to_datetime(hist_df['date']).dt.strftime('%Y-%m-%d')

pour_df = hist_df[hist_df["log_type"] == "Hourly Bottle Count"] if not hist_df.empty else pd.DataFrame()
pack_df = hist_df[hist_df["log_type"] == "Packing Count"] if not hist_df.empty else pd.DataFrame()
total_poured = pour_df["bottles_filled"].sum() if not pour_df.empty else 0
total_packed = pack_df["bottles_filled"].sum() if not pack_df.empty else 0
total_scrap = (pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0
yield_pct = (total_poured / (total_poured + total_scrap) * 100) if (total_poured + total_scrap) > 0 else 100.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Units Poured", f"{total_poured:,}")
k2.metric("Total Units Packed", f"{total_packed:,}")
k3.metric("Total Scrap Units", f"{total_scrap:,}")
k4.metric("Average Yield", f"{yield_pct:.1f}%")
st.markdown("---")

if not pour_df.empty:
    c1, c2 = st.columns(2)
    with c1:
        trend_df = pour_df.groupby("date_str")["bottles_filled"].sum().reset_index()
        fig_trend = px.line(trend_df, x="date_str", y="bottles_filled", markers=True, title="Units Poured Over Time")
        fig_trend.update_layout(height=320, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94A3B8'))
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        _op_display = pour_df.copy()
        _op_display["display_operator"] = _op_display.apply(
            lambda r: _id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1
        )
        op_df = _op_display.groupby("display_operator")["bottles_filled"].sum().reset_index().sort_values("bottles_filled", ascending=False)
        fig_op = px.bar(op_df, x="display_operator", y="bottles_filled", color="display_operator", title="Total Output by Operator")
        fig_op.update_layout(height=320, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94A3B8'))
        st.plotly_chart(fig_op, use_container_width=True)


