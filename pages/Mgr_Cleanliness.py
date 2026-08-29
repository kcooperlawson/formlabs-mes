import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from database import get_cleanliness_audits_df, delete_cleanliness_audit, UPLOAD_DIR

st.set_page_config(page_title="Cleanliness Gallery | Formlabs MES", page_icon="📸", layout="wide")

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
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar
                    update_user_avatar(st.session_state["user_id"], new_avatar)
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

st.subheader("📸 Cleanliness & Station Photo Gallery")

df_audits = get_cleanliness_audits_df()

k1, k2, k3, k4, k5 = st.columns(5)
total_audits = len(df_audits) if not df_audits.empty else 0
start_checks = len(df_audits[df_audits["audit_type"].str.contains("Start", na=False)]) if not df_audits.empty else 0
end_checks = len(df_audits[df_audits["audit_type"].str.contains("End", na=False)]) if not df_audits.empty else 0
transfers = len(df_audits[df_audits["audit_type"].str.contains("Transfer", na=False)]) if not df_audits.empty else 0
spills = len(df_audits[df_audits["is_spill"] == "Yes"]) if not df_audits.empty else 0
with k1: st.metric("All Photo Audits", f"{total_audits} records")
with k2: st.metric("Start Shift Checks", f"{start_checks} verified")
with k3: st.metric("End Shift Checks", f"{end_checks} shutdowns")
with k4: st.metric("Pump Transfers", f"{transfers} line changes")
with k5: st.metric("Spills / Issues", f"{spills} flags", delta="Attention Needed" if spills > 0 else "Clear", delta_color="inverse")
st.markdown("---")

if not df_audits.empty:
    ac1, ac2, ac3 = st.columns(3)
    for idx, row in df_audits.iterrows():
        target_col = ac1 if (idx % 3 == 0) else (ac2 if idx % 3 == 1 else ac3)
        with target_col:
            with st.container():
                badge_color = "#EF4444" if row["is_spill"] == "Yes" else "#38BDF8"
                st.markdown(
                    f"<div style='border:1px solid #334155; border-radius:8px; padding:12px; background-color:#0F172A; margin-bottom:8px;'>"
                    f"<b style='color:{badge_color}; font-size:0.85rem;'>● {row['audit_type']}</b>"
                    f"<span style='float:right; font-size:0.8rem; color:#94A3B8;'>{row['pump_station']}</span><br>",
                    unsafe_allow_html=True)
                if row["image_filename"]:
                    img_path = os.path.join(UPLOAD_DIR, str(row["image_filename"]))
                    if os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                    else:
                        st.caption("🖼️ Image file not found on disk.")
                else:
                    st.caption("📝 Log entry without image attachment.")
                st.caption(f"📅 **Time:** `{row['timestamp']}` | 👤 **Operator:** {row['operator_name']}")
                st.markdown(f"*{row['notes'] if row['notes'] else 'No additional operator notes logged.'}*")
                st.markdown("</div>", unsafe_allow_html=True)
                if st.button(f"🗑️ Delete Photo Audit #{row['id']}", key=f"del_gal_aud_{row['id']}", use_container_width=True):
                    delete_cleanliness_audit(row["id"])
                    st.success(f"Deleted Audit #{row['id']}")
                    st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)