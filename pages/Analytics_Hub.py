import os
import sys
import base64
from datetime import datetime, date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import extra_streamlit_components as stx

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from database import (
    get_production_logs_df,
    get_downtime_logs_df,
    get_plant_settings
)


cookie_manager = stx.CookieManager(key="analytics_cookies")
# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---




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

            st.rerun()
    else:
        # THE DOUBLE-TAKE: Give the browser 0.2 seconds to send the cookie!
        if not st.session_state["auth_check_passed"]:
            st.session_state["auth_check_passed"] = True
            st.rerun()
        else:
            # If it checked twice and STILL no cookie, they are truly logged out.
            st.warning("🔒 Session Expired. Please log in.")
            st.switch_page("Home.py")
            st.stop()

# --- SETUP & LOGO ---
st.set_page_config(
    page_title="Analytics Engine | Formlabs MES",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.logo("assets/formlabs_logo.png")

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

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""


logo_b64 = get_base64_image("assets/formlabs_logo.png")

# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {
        "Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
# ===================================================================
# ===================== SIDEBAR: PROFILE & SETTINGS =====================
with st.sidebar:
    st.markdown("---")
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
                cookie_manager.set("formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar

                    update_user_avatar(st.session_state["user_id"], new_avatar)
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
    current_role = st.session_state.get("user_role", "operator")
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
        st.rerun()


# ===================== THEME-ADAPTIVE CSS INJECTION =====================
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }

    /* Glassmorphic KPI Cards (Adapts to Active Theme) */
    .glass-kpi {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .glass-kpi:hover {
        transform: translateY(-4px);
        border-color: currentColor;
    }

    .kpi-title {
        font-size: 0.8rem;
        font-weight: 800;
        opacity: 0.75;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 2.8rem;
        font-weight: 900;
        line-height: 1.1;
        margin-bottom: 10px;
    }
    .kpi-value-alt { color: #F59E0B; }
    .kpi-value-success { color: #10B981; }
    .kpi-value-purple { color: #A855F7; }

    .trend-tag {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 800;
    }
    .trend-up { background: rgba(16, 185, 129, 0.2); color: #10B981; }
    .trend-down { background: rgba(239, 68, 68, 0.2); color: #EF4444; }
    .trend-neutral { background: rgba(255, 255, 255, 0.1); }
</style>
""", unsafe_allow_html=True)
# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

st.markdown("<br>", unsafe_allow_html=True)
if current_role == "admin":
    # God Mode (Now 6 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6: st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    # Manager Suite (Now 5 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    # Operator View (Stays 3 Columns)
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")
# ===================== DATA ACQUISITION & PROCESSING =====================
from datetime import date, timedelta

today = date.today()
sevendays_ago = today - timedelta(days=7)
prev_sevendays_ago = sevendays_ago - timedelta(days=7)

# Fetch 14 days of data so we can calculate the week-over-week delta
df_logs = get_production_logs_df(start_date=prev_sevendays_ago, end_date=today)
df_dt = get_downtime_logs_df()
settings = get_plant_settings()

if not df_logs.empty:
    df_logs['date_obj'] = pd.to_datetime(df_logs['date']).dt.date
    df_logs['date_str'] = df_logs['date_obj'].astype(str)
else:
    df_logs = pd.DataFrame(columns=['date_obj', 'date_str', 'log_type', 'bottles_filled', 'scrap_empty', 'scrap_filled', 'resin_type'])

# Re-establish pour_df and pack_df for the rest of the script
pour_df = df_logs[df_logs["log_type"] == "Hourly Bottle Count"].copy()
pack_df = df_logs[df_logs["log_type"] == "Packing Count"].copy()

# Slice out the current 7 days
pour_7d = pour_df[pour_df['date_obj'] >= sevendays_ago]
dt_7d = df_dt[pd.to_datetime(df_dt['date']).dt.date >= sevendays_ago] if not df_dt.empty else pd.DataFrame()

# Math
total_poured_7d = pour_7d['bottles_filled'].sum() if not pour_7d.empty else 0
total_scrap_7d = (pour_7d['scrap_empty'].sum() + pour_7d['scrap_filled'].sum()) if not pour_7d.empty else 0
yield_7d = (total_poured_7d / (total_poured_7d + total_scrap_7d) * 100) if (total_poured_7d + total_scrap_7d) > 0 else 100.0
total_dt_mins = dt_7d['duration_min'].sum() if not dt_7d.empty else 0

# Previous 7 Days for Delta comparison
pour_prev7d = pour_df[(pour_df['date_obj'] >= prev_sevendays_ago) & (pour_df['date_obj'] < sevendays_ago)]
prev_poured = pour_prev7d['bottles_filled'].sum() if not pour_prev7d.empty else 0
pour_delta = total_poured_7d - prev_poured
pour_delta_pct = (pour_delta / prev_poured * 100) if prev_poured > 0 else 0

# --- LIVE SHIFT TICKER BAR ---
time_now = datetime.now()
s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
shift_1_start = time_now.replace(hour=s1_h, minute=s1_m, second=0)

# Calculate rapid live shift metrics
if time_now < shift_1_start:
    elapsed_hrs = (time_now - (shift_1_start - timedelta(days=1))).total_seconds() / 3600.0
else:
    elapsed_hrs = (time_now - shift_1_start).total_seconds() / 3600.0

total_shift_length = float(settings["shift_1_hours"]) + float(settings["shift_2_hours"])
elapsed_hrs = min(total_shift_length, max(0.1, elapsed_hrs))
remaining_hrs = max(0.0, total_shift_length - elapsed_hrs)

live_target_lph = float(settings.get("target_lph", 400.0))
live_today_poured = pour_df[pour_df['date_obj'] == today]['bottles_filled'].sum() if not pour_df.empty else 0

expected_right_now = live_target_lph * elapsed_hrs
live_rate = live_today_poured / elapsed_hrs
projected_daily = live_today_poured + ((live_rate if elapsed_hrs > 0.5 else live_target_lph) * remaining_hrs)

st.markdown(f"""
<div style="background: rgba(0, 210, 255, 0.05); border: 1px solid rgba(0, 210, 255, 0.2); border-radius: 12px; padding: 12px 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
    <div>
        <div style="font-size: 0.7rem; font-weight: 800; color: #00D2FF; letter-spacing: 0.15em;">LIVE DAILY EXPECTATION (TICKING)</div>
        <div style="font-size: 1.5rem; font-weight: 900; color: #FFFFFF;">{expected_right_now:,.0f} L</div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 0.7rem; font-weight: 800; color: #A855F7; letter-spacing: 0.15em;">SELF-ADJUSTING DAILY PROJECTION</div>
        <div style="font-size: 1.5rem; font-weight: 900; color: #FFFFFF;">{projected_daily:,.0f} L</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ===================== UI LAYOUT =====================
st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 30px;">
    <div style="display:flex; align-items:center; gap: 15px;">
        <img src="data:image/png;base64,{logo_b64}" style="height: 50px; object-fit: contain; filter: drop-shadow(0px 0px 8px rgba(0, 210, 255, 0.4));">
        <h1 style="margin:0; padding:0; font-size: 2.2rem; font-weight: 900; background: linear-gradient(to right, #FFFFFF, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">NEXUS ANALYTICS</h1>
    </div>
    <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.3); padding: 8px 16px; border-radius: 8px; color: #A78BFA; font-weight: bold; letter-spacing: 0.1em; font-size: 0.8rem;">
        ROLLING 7-DAY INTELLIGENCE
    </div>
</div>
""", unsafe_allow_html=True)

# --- KPI ROW ---
k1, k2, k3, k4 = st.columns(4)

with k1:
    trend_class = "trend-up" if pour_delta_pct >= 0 else "trend-down"
    arrow = "▲" if pour_delta_pct >= 0 else "▼"
    st.markdown(f"""
    <div class="glass-kpi">
        <div class="kpi-title">Total Units Poured</div>
        <div class="kpi-value">{total_poured_7d:,.0f}</div>
        <div class="trend-tag {trend_class}">{arrow} {abs(pour_delta_pct):.1f}% vs Prev Week</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="glass-kpi">
        <div class="kpi-title">Quality Yield (FPY)</div>
        <div class="kpi-value kpi-value-success">{yield_7d:.2f}%</div>
        <div class="trend-tag trend-neutral">Target: {settings.get('yield_target_pct', 99.0)}%</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="glass-kpi">
        <div class="kpi-title">Total Scrap Volume</div>
        <div class="kpi-value kpi-value-alt">{total_scrap_7d:,.0f}</div>
        <div class="trend-tag trend-down">Lost Units</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    dt_hours = total_dt_mins / 60
    st.markdown(f"""
    <div class="glass-kpi">
        <div class="kpi-title">Accumulated Downtime</div>
        <div class="kpi-value kpi-value-purple">{dt_hours:.1f}h</div>
        <div class="trend-tag trend-neutral">{total_dt_mins} Minutes Logged</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- CHARTS ROW 1 ---
c1, c2 = st.columns((2, 1))

# Chart Theming configuration to make Plotly blend into the Glassmorphism CSS
chart_layout = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#94A3B8', family="sans-serif"),
    margin=dict(t=40, b=20, l=20, r=20),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False)
)

with c1:
    st.markdown("<h4 style='color:#E2E8F0;'>📈 Production Velocity Stream</h4>", unsafe_allow_html=True)
    if not pour_7d.empty:
        trend_df = pour_7d.groupby("date_str")["bottles_filled"].sum().reset_index()
        fig_line = px.area(trend_df, x="date_str", y="bottles_filled", markers=True)
        # Apply intense gradient styling
        fig_line.update_traces(
            line=dict(color='#00D2FF', width=4),
            marker=dict(size=8, color='#FFFFFF', line=dict(width=2, color='#00D2FF')),
            fillcolor='rgba(0, 210, 255, 0.1)'
        )
        fig_line.update_layout(**chart_layout)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No pouring data available for the last 7 days.")

with c2:
    st.markdown("<h4 style='color:#E2E8F0;'>🧪 Formulation Output</h4>", unsafe_allow_html=True)
    if not pour_7d.empty:
        resin_grp = pour_7d.groupby("resin_type")["bottles_filled"].sum().reset_index()
        fig_donut = px.pie(resin_grp, names="resin_type", values="bottles_filled", hole=0.7)
        fig_donut.update_traces(
            hoverinfo='label+percent',
            textinfo='none',
            marker=dict(line=dict(color='#02040A', width=2))
        )
        fig_donut.update_layout(
            **chart_layout,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        # Add total center text
        fig_donut.add_annotation(text=f"<b>{total_poured_7d:,.0f}</b><br>Total", x=0.5, y=0.5, font_size=20,
                                 showarrow=False, font_color="#FFFFFF")
        st.plotly_chart(fig_donut, use_container_width=True)

st.markdown("---")

# --- CHARTS ROW 2 ---
d1, d2 = st.columns((1, 2))

with d1:
    st.markdown("<h4 style='color:#E2E8F0;'>⚠️ Downtime Pareto</h4>", unsafe_allow_html=True)
    if not dt_7d.empty:
        dt_grp = dt_7d.groupby("reason")["duration_min"].sum().reset_index().sort_values("duration_min", ascending=True)
        fig_bar = px.bar(dt_grp, x="duration_min", y="reason", orientation='h')
        fig_bar.update_traces(marker_color='#A855F7', marker_line_color='#D8B4FE', marker_line_width=1.5, opacity=0.8)
        fig_bar.update_layout(**chart_layout)
        fig_bar.update_yaxes(title="")
        fig_bar.update_xaxes(title="Minutes")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.success("No downtime events logged in the last 7 days! 🎉")

with d2:
    st.markdown("<h4 style='color:#E2E8F0;'>👥 Operator Contribution Matrix</h4>", unsafe_allow_html=True)
    if not pour_df.empty:
        # Get the top 5 operators over the whole dataset for a wider matrix
        op_matrix = pour_df.groupby(["operator_name", "date_str"])["bottles_filled"].sum().reset_index()
        top_ops = op_matrix.groupby("operator_name")["bottles_filled"].sum().nlargest(5).index
        op_matrix = op_matrix[op_matrix["operator_name"].isin(top_ops)]

        fig_heat = go.Figure(data=go.Heatmap(
            z=op_matrix['bottles_filled'],
            x=op_matrix['date_str'],
            y=op_matrix['operator_name'],
            colorscale='Tealgrn',
            hoverongaps=False,
            xgap=3, ygap=3
        ))
        fig_heat.update_layout(**chart_layout)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Insufficient data for matrix.")