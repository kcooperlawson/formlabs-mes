
import os
import sys


import pandas as pd
import streamlit as st

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_all_resin_specs_df, add_resin_spec, bulk_update_resin_specs, delete_resin_spec, do_logout

st.set_page_config(page_title="Resin Specifications | Formlabs MES", page_icon="⚖️", layout="wide")

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

st.subheader("⚖️ Formlabs Master Resin Specification Lookup Table")

with (st.expander("➕ Add New Proprietary Resin Formulation", expanded=False)):
    with st.form("add_new_resin_form", clear_on_submit=True):
        a_c1, a_c2, a_c3 = st.columns(3)
        with a_c1:
            new_cart_type = st.selectbox("Container Format", ["V2", "V1", "V1/V2", "RPS", "Pigment", "Amazon"])
            new_sku = st.text_input("SKU Code", placeholder="e.g. RS-F2-CUST-01")
        with a_c2:
            new_resin_name = st.text_input("Formulation Name", placeholder="e.g. High-Temp Clear V3")
            new_code = st.text_input("Internal Resin Code", placeholder="e.g. FLCUST01")
        with a_c3:
            new_target_g = st.number_input("Target Fill Weight (g)", min_value=1.0, value=1110.0, step=10.0)
            new_min_g = st.number_input("Min Weight Tolerance (g)", min_value=1.0, value=1100.0, step=10.0)
            new_max_g = st.number_input("Max Weight Tolerance (g)", min_value=1.0, value=1125.0, step=10.0)

        if st.form_submit_button("💾 Save New Resin to Database", type="primary", use_container_width=True):
            if new_resin_name.strip():
                if add_resin_spec(new_cart_type, new_sku, new_code, new_resin_name, new_target_g, new_min_g, new_max_g):
                    st.toast(f"✅ Successfully registered '{new_resin_name}'!")
                    st.rerun()
                else:
                    st.error("❌ Failed to add resin. Check for duplicate names.")
            else:
                st.warning("⚠️ Formulation name is required.")

c_all, c_v1, c_v12, c_v2, c_rps, c_pig, c_amz = st.columns(7)
with c_all: fmt_all = st.button("🌐 ALL", use_container_width=True)
with c_v1: fmt_v1 = st.button("🔵 V1 (1L)", use_container_width=True)
with c_v12: fmt_v12 = st.button("🟢 V1/V2 Dual", use_container_width=True)
with c_v2: fmt_v2 = st.button("🟠 V2 (1L)", use_container_width=True)
with c_rps: fmt_rps = st.button("🍏 RPS (5L Jugs)", use_container_width=True)
with c_pig: fmt_pig = st.button("🔴 Pigments", use_container_width=True)
with c_amz: fmt_amz = st.button("🟡 Amazon Formulations", use_container_width=True)

if "spec_filter" not in st.session_state: st.session_state["spec_filter"] = "ALL"
if fmt_all: st.session_state["spec_filter"] = "ALL"
elif fmt_v1: st.session_state["spec_filter"] = "V1"
elif fmt_v12: st.session_state["spec_filter"] = "V1/V2"
elif fmt_v2: st.session_state["spec_filter"] = "V2"
elif fmt_rps: st.session_state["spec_filter"] = "RPS"
elif fmt_pig: st.session_state["spec_filter"] = "Pigment"
elif fmt_amz: st.session_state["spec_filter"] = "Amazon"

curr_filter = st.session_state["spec_filter"]
specs_filtered = get_all_resin_specs_df(curr_filter)
s_c1, s_c2 = st.columns((3, 1))
with s_c1:
    search_query = st.text_input("🔍 Quick Search by SKU, Resin Name, or Code")
with s_c2:
    st.markdown(f"<br><span style='color:#38BDF8; font-weight:700;'>Showing: {curr_filter} ({len(specs_filtered)} Resins)</span>", unsafe_allow_html=True)

if search_query.strip():
    specs_filtered = specs_filtered[
        specs_filtered["resin_name"].str.contains(search_query, case=False, na=False) |
        specs_filtered["sku"].str.contains(search_query, case=False, na=False) |
        specs_filtered["resin_code"].str.contains(search_query, case=False, na=False)
    ]

if not specs_filtered.empty:
    specs_filtered["calculated_kg"] = (specs_filtered["actual_spec_g"] / 1000.0).round(4)
    display_specs = specs_filtered[["id", "cartridge_type", "sku", "resin_code", "resin_name", "actual_spec_g", "min_weight_g", "max_weight_g", "calculated_kg", "multiplier", "lifetime_months"]]
    st.markdown(f'<div style="overflow-x: auto;">{display_specs.to_html(index=False)}</div>', unsafe_allow_html=True)
else:
    st.info("No resins found for the current filter.")

with st.expander("✏️ Edit or Delete Resin Specifications"):
    all_specs_df = get_all_resin_specs_df("ALL")
    if not all_specs_df.empty:
        selected_spec_name = st.selectbox("Select Formulation", all_specs_df["resin_name"].tolist())
        spec_row = all_specs_df[all_specs_df["resin_name"] == selected_spec_name].iloc[0]
        spec_id = int(spec_row["id"])

        e_col1, e_col2 = st.columns([3, 1])
        with e_col1:
            with st.form(f"edit_spec_form_{spec_id}"):
                ec1, ec2, ec3 = st.columns(3)
                with ec1: new_spec = st.number_input("Target Spec (g)", value=float(spec_row["actual_spec_g"]), step=5.0)
                with ec2: new_min = st.number_input("Min Weight (g)", value=float(spec_row["min_weight_g"]), step=5.0)
                with ec3: new_max = st.number_input("Max Weight (g)", value=float(spec_row["max_weight_g"]), step=5.0)
                if st.form_submit_button("💾 Save Specification Update", type="primary", use_container_width=True):
                    bulk_update_resin_specs(pd.DataFrame([{"id": spec_id, "sku": spec_row["sku"], "resin_code": spec_row["resin_code"], "resin_name": spec_row["resin_name"], "actual_spec_g": new_spec, "min_weight_g": new_min, "max_weight_g": new_max, "multiplier": spec_row["multiplier"], "lifetime_months": spec_row["lifetime_months"]}]))
                    st.success(f"✅ Updated tolerances for {selected_spec_name}!")
                    st.rerun()
        with e_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🗑️ Delete {selected_spec_name}", type="primary", use_container_width=True):
                delete_resin_spec(spec_id)
                st.toast(f"Deleted '{selected_spec_name}'!")
                st.rerun()
