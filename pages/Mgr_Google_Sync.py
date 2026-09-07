
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import (get_production_logs_df, do_logout, container_litres, log_litres,
                      get_sheet_targets_df, add_sheet_target, update_sheet_target,
                      delete_sheet_target, record_sheet_sync, esc)
import sheet_sync

st.set_page_config(page_title="Google Cloud Sync | Formlabs MES", page_icon="☁️", layout="wide")


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
current_user = st.session_state.get("user_name", "Manager")
current_uid = st.session_state.get("user_id")
is_admin = current_role == "admin"

st.subheader("☁️ External Reporting & Google Cloud Sync Control Panel")
st.caption("Send the record to a spreadsheet of your own. Choose what to send and how far "
           "back, pick the columns, and push. Every push is manual and on demand.")

df_logs = get_production_logs_df()

# ===================== WHERE IT GOES =====================
# This used to be one webhook in a .env file: one destination for the whole
# plant, set by whoever installed the application, and unchangeable from
# inside it. When that line was missing - which on this install it was - the
# page said "webhook missing" and there was nothing anybody standing here
# could do about it. Now a destination is a row, and anybody who can see this
# page can add their own.
_all_targets = get_sheet_targets_df()
_rows = _all_targets.to_dict("records") if not _all_targets.empty else []
_mine = sheet_sync.visible_targets(_rows, current_uid, is_admin)

st.markdown("#### 📗 Destination")

if not _mine:
    st.info("No spreadsheet is linked yet. Add one below — it takes about two minutes "
            "and you only do it once per sheet.")
    target = None
else:
    _labels = {sheet_sync.target_label(r): r for r in _mine}
    _pick = st.selectbox("Send to", list(_labels.keys()), key="gs_target")
    target = _labels[_pick]

    d1, d2 = st.columns([3, 1])
    with d1:
        st.caption(sheet_sync.last_sync_text(target.get("last_sync_at"),
                                             target.get("last_status")))
    with d2:
        # A destination that has quietly stopped working - a deployment
        # revoked, a sheet deleted, a URL that was never live - is
        # indistinguishable from a healthy one until somebody needs the
        # numbers. This asks it, without writing anything to the sheet.
        if st.button("🔌 Test", use_container_width=True, key="gs_test"):
            try:
                import requests
                r = requests.get(target["webhook_url"], timeout=20)
                if r.status_code == 200 and "formlabs-mes-ok" in r.text:
                    st.success("Answered. This sheet is reachable.")
                elif r.status_code == 200:
                    st.warning("Something answered, but not the MES script. "
                               "Check the script is the one below and redeploy.")
                else:
                    st.error(f"No good answer ({r.status_code}). "
                             "The deployment may have been revoked — redeploy and paste "
                             "the new /exec address.")
            except Exception as exc:
                st.error(f"Could not reach it: {str(exc)[:160]}")

with st.expander("➕ Link a spreadsheet of your own", expanded=not _mine):
    # Everybody pastes the spreadsheet link first, because that is the link
    # they have. Saying why that cannot work, and handing over the four steps
    # and the script in the same breath, is the difference between this being
    # usable and being a validation error.
    st.markdown("A Google Sheet is a document — it has no inbox, so it cannot be "
                "sent rows directly. Giving your sheet an address takes four steps:")
    for i, step in enumerate(sheet_sync.SETUP_STEPS, 1):
        st.markdown(f"{i}. {step}")
    with st.expander("📜 The script to paste (step 2)", expanded=False):
        st.code(sheet_sync.APPS_SCRIPT, language="javascript")

    st.markdown("---")
    n1, n2 = st.columns([1, 2])
    with n1:
        new_name = st.text_input("Name it", placeholder="My weekly report",
                                 max_chars=80, key="gs_new_name")
    with n2:
        new_url = st.text_input("Web app address (ends in /exec)",
                                placeholder="https://script.google.com/macros/s/…/exec",
                                key="gs_new_url")
    new_shared = st.checkbox("Let other managers send to this sheet too",
                             value=False, key="gs_new_shared",
                             help="Leave this off and the sheet is yours alone. "
                                  "Nobody else will see it in the list.")

    _verdict = sheet_sync.classify_url(new_url)
    if new_url and _verdict["message"]:
        (st.success if _verdict["ok"] else st.error)(_verdict["message"])

    if st.button("💾 Link this sheet", type="primary", use_container_width=True,
                 disabled=not (_verdict["ok"] and new_name.strip()), key="gs_add"):
        ok, msg = add_sheet_target(new_name, _verdict["url"], current_uid,
                                   current_user, new_shared)
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()

if _mine:
    with st.expander("✏️ Sheets you have linked", expanded=False):
        # Only your own, and an administrator's, are editable here. A shared
        # sheet belongs to whoever added it: seeing it in the list is not the
        # same as being allowed to repoint it.
        _editable = [r for r in _mine
                     if is_admin or (r.get("owner_user_id") is not None
                                     and r.get("owner_user_id") == current_uid)]
        if not _editable:
            st.caption("The sheets in your list were shared by somebody else, so only "
                       "they can change them.")
        for r in _editable:
            with st.form(f"gs_edit_{r['id']}"):
                e1, e2, e3, e4 = st.columns([1.2, 2.4, 0.8, 0.8])
                nm = e1.text_input("Name", value=r["name"], key=f"gs_n_{r['id']}",
                                   label_visibility="collapsed")
                ur = e2.text_input("Address", value=r["webhook_url"], key=f"gs_u_{r['id']}",
                                   label_visibility="collapsed")
                sh = e3.checkbox("Shared", value=bool(r["is_shared"]), key=f"gs_s_{r['id']}")
                saved = e4.form_submit_button("💾 Save", use_container_width=True)
                if saved:
                    update_sheet_target(r["id"], nm, ur, sh)
                    st.rerun()
            if st.button(f"🗑️ Remove '{esc(r['name'])}'", key=f"gs_d_{r['id']}"):
                delete_sheet_target(r["id"])
                st.rerun()
            st.markdown("<hr style='margin:6px 0; border-color:#1E2B45;'>",
                        unsafe_allow_html=True)

st.markdown("---")

# ===================== WHAT GOES =====================
# There was a third control here - "Automation Trigger Preference", offering a
# manual push, an auto-sync on shift handover, and a scheduled webhook. Only
# the first existed: the chosen value was never read except to word the
# spinner, so the other two produced the same manual push with a different
# sentence over it. A control that appears to configure something and does not
# is worse than no control - and one of its options named a screen that has
# since been removed for describing itself as more than it was, which is the
# same fault twice.
col_a, col_b = st.columns(2)
with col_a:
    export_mode = st.radio("1. Select Data Payload Type", ["📊 Aggregated Calculated Metrics (KPI Summary)", "📋 Raw Production Audit Stream"], key="mgr_gsheet_payload")

with col_b:
    sync_horizon = st.selectbox("2. Time Horizon Scope", tuple(sheet_sync.HORIZONS.keys()))

# The horizon now actually narrows the export. It used to be read into a
# variable and ignored: "Live Today" on a plant with two years of history sent
# two years of history, and the only sign was a row count nobody was checking.
df_logs = sheet_sync.filter_by_horizon(df_logs, sync_horizon)

st.markdown("---")
st.markdown("#### ⚙️ Payload Column Customization")

if export_mode == "📊 Aggregated Calculated Metrics (KPI Summary)":
    if not df_logs.empty:
        calc_df = df_logs.copy()
        calc_df["date_str"] = pd.to_datetime(calc_df["date"]).dt.strftime("%Y-%m-%d")

        def get_row_liters(r):
            b_count = float(r.get("bottles_filled", 0) or 0)
            c_type = str(r.get("cartridge_type", "V2")).strip().upper()
            return log_litres(b_count, c_type, r.get("litres_poured"))

        calc_df["liters_calc"] = calc_df.apply(get_row_liters, axis=1)
        calc_df["total_scrap"] = calc_df["scrap_empty"].fillna(0) + calc_df["scrap_filled"].fillna(0)

        summary_df = calc_df.groupby(
            ["date_str", "shift", "resin_type", "cartridge_type", "operator_name", "pump_station"]
        ).agg(
            Total_Poured_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Packed_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Packing Count"].sum()),
            Volume_Output_Liters=("liters_calc", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Scrap_Units=("total_scrap", "sum"),
            Log_Count=("id", "count")
        ).reset_index()

        summary_df["Quality FPY (%)"] = (summary_df["Total_Poured_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(100.0).round(2)
        summary_df["Scrap Rate (%)"] = (summary_df["Total_Scrap_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(0.0).round(2)
        summary_df["Pending Floor WIP"] = (summary_df["Total_Poured_Units"] - summary_df["Total_Packed_Units"]).clip(lower=0)
        summary_df["Est Skids Built"] = (summary_df["Total_Packed_Units"] / 500.0).round(2)

        summary_df.rename(columns={
            "date_str": "Date", "shift": "Shift", "resin_type": "Resin Formulation",
            "cartridge_type": "Container Format", "operator_name": "Operator Name",
            "pump_station": "Pump Station", "Total_Poured_Units": "Units Poured",
            "Total_Packed_Units": "Units Packed", "Volume_Output_Liters": "Volume Output (Liters)",
            "Total_Scrap_Units": "Scrap Reject Units"
        }, inplace=True)

        export_payload_df = summary_df
    else:
        export_payload_df = pd.DataFrame()
else:
    if not df_logs.empty:
        export_payload_df = df_logs.drop(columns=[c for c in ["date_obj", "date_str"] if c in df_logs.columns]).copy()
    else:
        export_payload_df = pd.DataFrame()

available_metrics = list(export_payload_df.columns) if not export_payload_df.empty else []
selected_export_cols = st.multiselect("Toggle Metrics / Statistics to Include in Payload:", options=available_metrics, default=available_metrics)

# Say what is about to be sent, and where, before it is sent. The row count is
# the one number that shows the horizon is being honoured.
if target:
    st.caption(f"Ready to send **{len(export_payload_df):,} rows** to "
               f"**{esc(target['name'])}** — {esc(sync_horizon)}.")

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 Execute Google Sheets Transmission", type="primary",
             use_container_width=True, disabled=target is None):
    if not selected_export_cols:
        st.warning("⚠️ Please select at least one metric column to export.")
    elif export_payload_df.empty:
        st.warning("⚠️ Nothing to send for that time horizon. Widen the scope, or check "
                   "that production has been logged.")
    else:
        with st.spinner("Packaging payload and transmitting..."):
            try:
                import requests
                final_df = export_payload_df[selected_export_cols].copy().astype(str)
                payload = final_df.to_dict(orient="records")
                target_tab = "KPI Summary" if "Aggregated" in export_mode else "Raw Audit Logs"
                wrapped_payload = {"sheet_name": target_tab, "data": payload}
                response = requests.post(target["webhook_url"], json=wrapped_payload, timeout=60)
                if response.status_code == 200:
                    record_sheet_sync(target["id"], "ok", len(final_df))
                    st.success(f"✅ Dispatched {len(final_df)} records to tab '{target_tab}' "
                               f"in {esc(target['name'])}.")
                else:
                    record_sheet_sync(target["id"], f"HTTP {response.status_code}", 0)
                    st.error(f"❌ Transmission Failed ({response.status_code}): {response.text[:200]}")
            except Exception as e:
                record_sheet_sync(target["id"], str(e)[:180], 0)
                st.error(f"❌ Transmission Error: {str(e)[:200]}")
