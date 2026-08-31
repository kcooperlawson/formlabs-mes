
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from database import (
    get_assigned_runs_df, create_assigned_run, update_assigned_run_progress,
    update_run_status, delete_assigned_run, sync_all_runs_with_logs,
    get_all_resin_specs_df, get_active_operators, get_active_pumps,
    get_plant_settings, get_all_reactors_df, complete_run_with_custom_total,
    reconcile_pouring_to_packing, get_all_users_df, get_all_pumps_df, do_logout
)
from database import esc

st.set_page_config(page_title="Assigned Runs | Formlabs MES", page_icon="🎯", layout="wide")


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

st.subheader("🎯 Fleet Production Progress & Work Order Dispatch")

df_runs = get_assigned_runs_df()
df_reactors = get_all_reactors_df()
df_users = get_all_users_df()
df_pumps = get_all_pumps_df()
active_operators_list = get_active_operators()
active_pumps_list = get_active_pumps()

col_k1, col_k2, col_k3, col_k4 = st.columns(4)
total_target = df_runs["target_units"].sum() if not df_runs.empty else 0
total_actual = df_runs["current_units"].sum() if not df_runs.empty else 0
fleet_pct = (total_actual / total_target * 100) if total_target > 0 else 0
active_runs_count = len(df_runs[df_runs["status"].isin(["Active", "Pouring"])]) if not df_runs.empty else 0
queued_count = len(df_runs[df_runs["status"] == "Queued"]) if not df_runs.empty else 0
done_count = len(df_runs[df_runs["status"] == "Done"]) if not df_runs.empty else 0

with col_k1:
    st.metric("Fleet Production Progress", f"{total_actual:,} / {total_target:,} units", delta=f"{fleet_pct:.1f}% Completed")
with col_k2:
    st.metric("Active Runs Status", f"{active_runs_count} Active", delta=f"{queued_count} Queued | {done_count} Done")
with col_k3:
    st.metric("Tracked Pumps", f"{len(df_pumps)} Configured", delta=f"{len(df_runs['pump_station'].unique()) if not df_runs.empty else 0} In Use")
with col_k4:
    st.metric("Active Operators", f"{len(active_operators_list)} Ready", delta="Live Machine Sync")

st.markdown("---")

with st.expander("➕ Create & Assign New Work Order", expanded=True):
    st.markdown("##### 📋 Work Order Type")
    plant_config = get_plant_settings()
    if plant_config.get("enable_packing", True):
        run_type_selection = st.radio("Dispatch Type", ("Pouring", "Packing"), horizontal=True)
    else:
        run_type_selection = "Pouring"
        st.info("📦 Packing Module is currently disabled in Plant Settings.")

    with st.form("create_run_dispatch_form"):
        if run_type_selection == "Pouring":
            st.markdown("##### 🛢️ 1. Reactor Vessel & Tank Configuration")
            r_c1, r_c2, r_c3 = st.columns(3)
            with r_c1:
                reactor_list = df_reactors["reactor_name"].tolist() if not df_reactors.empty else ["No Reactors Configured"]
                reactor_id = st.selectbox("Reactor Tank", reactor_list)
            with r_c2:
                reactor_size_val = int(df_reactors[df_reactors["reactor_name"] == reactor_id]["max_capacity_l"].iloc[0]) if not df_reactors.empty and reactor_id in df_reactors["reactor_name"].values else 5000
                st.info(f"Capacity: {reactor_size_val:,} L")
            with r_c3:
                lot_number = st.text_input("Batch Lot ID", value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01")
        else:
            st.markdown("##### 📦 1. Packing Source Information")
            r_c1, r_c3 = st.columns([1, 2])
            with r_c1:
                st.info("Source: Floor WIP (Unpacked Units)")
                reactor_id = "Floor WIP"
                reactor_size_val = 0
            with r_c3:
                lot_number = st.text_input("Batch Lot ID to Pack", value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01")

        st.markdown("##### 🧪 2. Resin Material & Packaging Target")
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            cartridge_type = st.selectbox("Container Format", ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"))
            cart_code = "RPS" if "RPS" in cartridge_type else ("V1" if "V1" in cartridge_type else ("Pigment" if "Pigment" in cartridge_type else "V2"))
        with m_c2:
            specs_df = get_all_resin_specs_df(cart_code)
            if specs_df.empty:
                specs_df = get_all_resin_specs_df("ALL")
            resin_list = sorted(specs_df["resin_name"].unique().tolist()) if not specs_df.empty else ["No Resins"]
            selected_resin = st.selectbox("Resin Formulation", resin_list)
        with m_c3:
            default_target = int(reactor_size_val / 5.0) if cart_code == "RPS" and run_type_selection == "Pouring" else (int(reactor_size_val / 1.0) if run_type_selection == "Pouring" else 500)
            target_units = st.number_input("Target Units", min_value=1, max_value=50000, value=default_target, step=50)

        st.markdown("##### 👤 3. Station & Personnel Assignment")
        s_c1, s_c2, s_c3 = st.columns(3)
        with s_c1:
            assigned_pump = st.selectbox("Assigned Station", active_pumps_list)
        with s_c2:
            target_role = "packer" if run_type_selection == "Packing" else "operator"
            personnel_list = df_users[df_users["role"] == target_role]["full_name"].tolist() if not df_users.empty else ["No personnel"]
            assigned_op = st.selectbox("Assigned Personnel", personnel_list if personnel_list else ["No personnel"])
        with s_c3:
            initial_status = st.selectbox("Initial Run Status", ("Active", "Queued"))
            status_code = "Active" if "Active" in initial_status else "Queued"

        run_notes = st.text_input("Special Process Instructions / Run Notes", placeholder="e.g. Needs updated warning labels.")
        submit_label = "🚀 Dispatch Pouring Run" if run_type_selection == "Pouring" else "📦 Dispatch Packing Run"

        if st.form_submit_button(submit_label, type="primary", use_container_width=True):
            auto_detected = create_assigned_run(
                reactor_id=reactor_id, reactor_size_l=reactor_size_val, resin_type=selected_resin,
                cartridge_type=cart_code, target_units=int(target_units), assigned_operator=assigned_op,
                pump_station=assigned_pump, lot_number=lot_number, notes=run_notes, status=status_code,
                run_type=run_type_selection
            )
            st.toast(f"✅ Dispatched {selected_resin}!")
            st.rerun()

active_tab, completed_tab = st.tabs(["🚀 Active & Queued Runs", "✅ Completed Work Orders"])

with active_tab:
    h_col1, h_col2 = st.columns((3, 1))
    with h_col1:
        st.markdown("### 📋 Active & Queued Assigned Runs")
    with h_col2:
        if st.button("🔄 Sync Progress with Logs", use_container_width=True):
            sync_all_runs_with_logs()
            st.toast("✅ Synchronized run progress with production logs!")
            st.rerun()

    active_df = df_runs[df_runs["status"] != "Done"] if not df_runs.empty else pd.DataFrame()
    if not active_df.empty:
        for _, run in active_df.iterrows():
            with st.container():
                prog_pct = min(1.0, run["current_units"] / run["target_units"]) if run["target_units"] > 0 else 0.0
                status_color = "#10B981" if run["status"] in ["Active", "Pouring"] else ("#F59E0B" if run["status"] == "Queued" else "#64748B")

                st.markdown(f"""
                <div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:16px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="background:{status_color}; color:#FFFFFF; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:4px;">● {run['status'].upper()}</span>
                            <span style="font-size:1.15rem; font-weight:800; color:#FFFFFF; margin-left:8px;">{esc(run['resin_type'])}</span>
                            <span style="color:#00D2FF; font-weight:700; font-size:0.85rem; margin-left:6px;">[{esc(run['cartridge_type'])}]</span>
                        </div>
                        <div style="color:#94A3B8; font-size:0.85rem;">
                            🛢️ <b>{esc(run.get('reactor_id', 'Reactor 1'))}</b> ({run.get('reactor_size_l', 5000):,} L) &nbsp;|&nbsp; 🏷️ <b>{esc(run['pump_station'])}</b> &nbsp;|&nbsp; 👤 <b>{esc(run['assigned_operator'])}</b>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(prog_pct, text=f"Output: {run['current_units']:,} / {run['target_units']:,} Units ({prog_pct * 100:.1f}%) | Lot: {run.get('lot_number', 'N/A')}")

                b_c1, b_c2, b_c3, b_c4 = st.columns(4)
                with b_c1:
                    if st.button("+50 Units", key=f"p50_{run['id']}", use_container_width=True):
                        update_assigned_run_progress(run['id'], 50, operator_name=st.session_state.get("user_name", "Manager"))
                        st.rerun()
                with b_c2:
                    if st.button("+100 Units", key=f"p100_{run['id']}", use_container_width=True):
                        update_assigned_run_progress(run['id'], 100, operator_name=st.session_state.get("user_name", "Manager"))
                        st.rerun()
                with b_c3:
                    if run["status"] == "Queued":
                        if st.button("▶️ Start", key=f"start_{run['id']}", use_container_width=True):
                            update_run_status(run['id'], "Active")
                            st.rerun()
                    else:
                        if st.button("⏸️ Queue", key=f"queue_{run['id']}", use_container_width=True):
                            update_run_status(run['id'], "Queued")
                            st.rerun()
                with b_c4:
                    if st.button("🗑️ Delete", key=f"del_run_{run['id']}", use_container_width=True):
                        delete_assigned_run(run['id'])
                        st.rerun()

                with st.expander(f"⚙️ Set Final Count & Close Work Order #{run['id']}"):
                    with st.form(f"custom_complete_form_{run['id']}"):
                        final_input_val = st.number_input("Final Total Units Produced", value=int(run["current_units"]), step=10)
                        if st.form_submit_button("💾 Save Final Count & Archive Run", type="primary"):
                            complete_run_with_custom_total(run['id'], int(final_input_val))
                            reconcile_pouring_to_packing(str(run['lot_number']), int(final_input_val))
                            st.success(f"Work Order #{run['id']} finalized!")
                            st.rerun()
                st.markdown("---")
    else:
        st.info("No assigned runs currently active.")

with completed_tab:
    st.markdown("### 📚 Completed Work Order History")
    comp_df = df_runs[df_runs["status"] == "Done"].copy() if not df_runs.empty else pd.DataFrame()
    if not comp_df.empty:
        comp_df["created_at"] = pd.to_datetime(comp_df["created_at"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %H:%M:%S")
        cf1, cf2, cf3 = st.columns(3)
        with cf1: f_type = st.selectbox("Run Type Filter", ["All", "Pouring", "Packing"])
        with cf2: op_list = ["All"] + sorted(comp_df["assigned_operator"].dropna().unique().tolist()); f_op = st.selectbox("Operator Filter", op_list)
        with cf3: lot_list = ["All"] + sorted(comp_df["lot_number"].astype(str).unique().tolist()); f_lot = st.selectbox("Lot Number Filter", lot_list)

        if f_type != "All": comp_df = comp_df[comp_df["run_type"] == f_type]
        if f_op != "All": comp_df = comp_df[comp_df["assigned_operator"] == f_op]
        if f_lot != "All": comp_df = comp_df[comp_df["lot_number"] == f_lot]

        if not comp_df.empty:
            display_cols = ["id", "created_at", "run_type", "resin_type", "cartridge_type", "lot_number", "target_units", "current_units", "assigned_operator", "pump_station"]
            st.markdown(f'<div style="overflow-x: auto;">{comp_df[display_cols].to_html(index=False)}</div>', unsafe_allow_html=True)

            st.markdown("---")
            with st.expander("🗑️ Delete a Completed Work Order"):
                st.caption(
                    "Permanently removes this archived Work Order. This does NOT delete the "
                    "underlying production logs that were poured/packed against it — use "
                    "**Log Management & Cleanup** from the Manager Cockpit for that."
                )
                _del_options = {
                    f"#{r['id']} — {r['resin_type']} [{r['cartridge_type']}] · {r['pump_station']} · {r['current_units']:,} units · {r['created_at']}": r['id']
                    for _, r in comp_df.iterrows()
                }
                _del_label = st.selectbox("Select Work Order to delete", list(_del_options.keys()), key="del_completed_run_select")
                if st.button("🗑️ Permanently Delete Selected Work Order", key="del_completed_run_btn"):
                    delete_assigned_run(_del_options[_del_label])
                    st.success(f"Deleted {_del_label}")
                    st.rerun()
        else:
            st.info("No completed orders match the current filters.")
    else:
        st.info("No completed work orders logged yet.")
