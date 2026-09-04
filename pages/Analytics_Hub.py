

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
    get_plant_settings, do_logout, check_authentication, role_can_administer,
    get_all_users_df, get_all_resin_specs_df,
)
from resin_palette import resin_color_map, stored_color_map
import fill_weight


cookie_manager = stx.CookieManager(key="analytics_cookies")
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

# --- SETUP & LOGO ---
st.set_page_config(
    page_title="Analytics Engine | Formlabs MES",
    page_icon="🌌",
    layout="wide",
    # "auto" like the entry point - see Home.py. Every other page already
    # leaves this at the default; this one and Home were the two forcing the
    # sidebar open on a phone.
    initial_sidebar_state="auto"
)

st.logo("assets/formlabs_logo.png")


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
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
# ===================================================================
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
        do_logout(cookie_manager)
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
if role_can_administer(current_role):
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

# --- OPERATOR IDENTITY CONSOLIDATION ---
# Group by operator_id (the FK) instead of the raw operator_name string
# wherever possible, so a renamed operator's history stays consolidated
# under their current display name instead of splitting into two rows.
# Falls back to the logged string name for rows with no matching operator_id
# (e.g. "System Auto-Reconciliation" adjustment entries).
if not pour_df.empty:
    _users_df = get_all_users_df()
    _id_to_name = dict(zip(_users_df["id"], _users_df["full_name"])) if not _users_df.empty else {}
    pour_df["display_operator"] = pour_df.apply(
        lambda r: _id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1
    )
else:
    pour_df["display_operator"] = pour_df.get("operator_name")

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
        <div style="font-size: 1.5rem; font-weight: 900; color: inherit;">{expected_right_now:,.0f} L</div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 0.7rem; font-weight: 800; color: #A855F7; letter-spacing: 0.15em;">SELF-ADJUSTING DAILY PROJECTION</div>
        <div style="font-size: 1.5rem; font-weight: 900; color: inherit;">{projected_daily:,.0f} L</div>
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
        # Same colours as everywhere else the resin is named, so a segment can
        # be matched to a cartridge without reading the legend.
        _donut_colours = resin_color_map(resin_grp["resin_type"].tolist(),
                                         stored_color_map(get_all_resin_specs_df("ALL")))
        fig_donut = px.pie(resin_grp, names="resin_type", values="bottles_filled", hole=0.7,
                           color="resin_type", color_discrete_map=_donut_colours)
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
        op_matrix = pour_df.groupby(["display_operator", "date_str"])["bottles_filled"].sum().reset_index()
        top_ops = op_matrix.groupby("display_operator")["bottles_filled"].sum().nlargest(5).index
        op_matrix = op_matrix[op_matrix["display_operator"].isin(top_ops)]

        fig_heat = go.Figure(data=go.Heatmap(
            z=op_matrix['bottles_filled'],
            x=op_matrix['date_str'],
            y=op_matrix['display_operator'],
            colorscale='Tealgrn',
            hoverongaps=False,
            xgap=3, ygap=3
        ))
        fig_heat.update_layout(**chart_layout)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Insufficient data for matrix.")




# ==================== FILL WEIGHT ====================
# The tolerance window is lopsided - a typical spec allows 10 g under target
# and only 5 g over - so a pump set to stay safely clear of the low limit
# sits high in the window on every cartridge and gives resin away on every
# cartridge, entirely inside spec and entirely invisible. This section exists
# to make that number sayable.
st.markdown("---")
st.markdown("<h4 style='color:#E2E8F0;'>⚖️ Fill weight</h4>", unsafe_allow_html=True)

_w = pour_df[pour_df["check_weight_g"].notna()].copy() if "check_weight_g" in pour_df.columns else pd.DataFrame()

if _w.empty:
    # An honest empty state rather than a broken chart. Readings are optional,
    # so "nobody has weighed anything yet" is a normal condition, not a fault -
    # and saying what to do about it is more use than an empty axis.
    st.info(
        "No check weights recorded yet. The pouring form has an optional "
        "**Check weight (g)** box — one reading an hour from any pump is enough "
        "to show where that pump is sitting in its tolerance window, and how "
        "much resin is being given away above target."
    )
else:
    _w["weight_deviation_g"] = pd.to_numeric(_w["weight_deviation_g"], errors="coerce")
    _w = _w[_w["weight_deviation_g"].notna()]

    # Each reading stands for the units logged alongside it: one weight an
    # hour is a sample of that hour's output, not a single cartridge on its
    # own. Weighting by units is what turns "4 g heavy" into kilograms.
    _summary = fill_weight.giveaway(
        zip(_w["weight_deviation_g"], _w["bottles_filled"].fillna(0))
    )
    _in_band = int((_w["weight_status"] == "in").sum())
    _judged = int(_w["weight_status"].isin(["in", "over", "under"]).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Readings taken", f"{_summary['samples']:,}")
    # fill_weight.band_percent, not a format string: 349 of 350 rounds to
    # "100%" beside a scatter that visibly contains an out-of-band point, and
    # the reader who spots that stops trusting the rest of the panel.
    m2.metric("In band", fill_weight.band_percent(_in_band, _judged),
              help="Share of readings inside the resin's own tolerance window. "
                   "Only a clean sweep reads 100%.")
    m3.metric("Mean deviation", f"{_summary['mean_deviation']:+.1f} g",
              help="Average distance from target. Positive means running heavy.")
    m4.metric("Resin above target", f"{_summary['kg']:+,.1f} kg",
              help="Mean deviation applied to the units those readings represent. "
                   "Positive is resin given away.")

    g1, g2 = st.columns((2, 1))
    with g1:
        # Deviation rather than absolute grams, because each resin has its own
        # target - plotting raw weight would stack unrelated products on one
        # axis and show nothing. Zero is target. Points are coloured by the
        # status judged at capture against that resin's own window, which is
        # why no band lines are drawn: the limits differ per resin and a
        # single pair of lines would be wrong for most of the points.
        _plot = _w.sort_values("timestamp")
        fig_w = px.scatter(
            _plot, x="timestamp", y="weight_deviation_g", color="pump_station",
            labels={"weight_deviation_g": "Grams from target", "timestamp": "",
                    "pump_station": ""},
            hover_data=["resin_type", "check_weight_g", "operator_name", "weight_status"],
        )
        fig_w.update_traces(marker=dict(size=8, line=dict(width=0)), opacity=0.75)

        # Out-of-band readings ride on top as their own trace rather than as a
        # third colour in the main series. At this density a status colour is
        # lost among hundreds of in-band points, and the exceptions are the
        # entire reason a manager opens this chart.
        _out = _plot[_plot["weight_status"].isin(["over", "under"])]
        if not _out.empty:
            fig_w.add_scatter(
                x=_out["timestamp"], y=_out["weight_deviation_g"], mode="markers",
                name="outside band",
                marker=dict(size=15, symbol="diamond-open", color="#F87171",
                            line=dict(width=2.5)),
                hovertext=_out["pump_station"], hoverinfo="text+y",
            )

        fig_w.add_hline(y=0, line_dash="dash", line_color="#64748B",
                        annotation_text="target", annotation_font_color="#94A3B8")
        fig_w.update_layout(**chart_layout, legend_title_text="",
                            legend=dict(orientation="h", yanchor="bottom",
                                        y=1.02, xanchor="left", x=0))
        st.plotly_chart(fig_w, use_container_width=True)

    with g2:
        # The actionable cut: which pump runs heavy. A station consistently
        # above zero is a setting, not noise, and it is fixable in minutes.
        _by_pump = (_w.groupby("pump_station")["weight_deviation_g"]
                    .agg(["mean", "count"]).reset_index()
                    .sort_values("mean", ascending=False))
        _by_pump["mean"] = _by_pump["mean"].round(2)
        # Above target costs money, below target does not - so the two
        # directions get different colours rather than one bar colour that
        # makes "runs light" look like the same problem as "runs heavy".
        _by_pump["tone"] = _by_pump["mean"].apply(lambda m: "over" if m > 0 else "under")
        fig_p = px.bar(_by_pump, x="mean", y="pump_station", orientation="h",
                       labels={"mean": "Mean grams from target", "pump_station": ""},
                       text="mean", color="tone",
                       color_discrete_map={"over": "#EA580C", "under": "#38BDF8"})
        # 'auto' rather than 'outside': a negative bar puts an outside label
        # on the left, straight through the station names.
        #
        # But 'auto' means a short bar's label lands OUTSIDE it, on the chart
        # background - and a single white text colour then makes that one label
        # invisible on every light theme. It was: the pump averaging +0.35 g
        # had no readable number at all. Inside and outside get their own
        # colours: white on the saturated bar, and the same slate the rest of
        # the chart chrome uses out on the background, which reads either way.
        fig_p.update_traces(textposition="auto", cliponaxis=False,
                            insidetextfont=dict(color="#FFFFFF", size=12),
                            outsidetextfont=dict(color="#94A3B8", size=12))
        fig_p.add_vline(x=0, line_color="#64748B")
        fig_p.update_layout(**chart_layout, showlegend=False)
        st.plotly_chart(fig_p, use_container_width=True)

        if len(_by_pump):
            _worst = _by_pump.iloc[0]
            if _worst["mean"] > 0.5:
                st.caption(
                    f"**{_worst['pump_station']}** is averaging "
                    f"{_worst['mean']:+.1f} g against target across "
                    f"{int(_worst['count'])} readings. Every gram above target is "
                    f"resin out of the door on every cartridge that pump fills."
                )
