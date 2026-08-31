
import os
import sys


import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

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
from ui_shell import render_shell
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

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
