"""
pages/Device_Registry.py - Find, assign, and tag-map floor machines.

This is the "find, assign, put it in analytics" UI: register a machine
(whatever protocol it speaks), point it at the PumpStation it physically
sits on, tell it which of its raw tags mean what, and the background
gateway process (run_gateway.py) takes it from there — its readings start
showing up in ProductionLog the same way a hand-typed hourly count would,
so Analytics_Hub/Manager_Cockpit/Live_Reactors need no changes at all.

Adding a device here does NOT start polling it — that's run_gateway.py's
job, running as its own process. This page only edits the `devices` /
`device_tag_maps` rows it reads from.
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    get_active_pumps, get_all_pumps_df, get_all_reactors_df, check_authentication, do_logout,
    get_plant_settings, role_can_administer,
)
from database import esc
from device_crud import (
    get_devices_df, get_device_dict, create_device, update_device, delete_device, set_device_enabled,
    get_tag_map_df, upsert_tag_map_row, delete_tag_map_row, get_recent_readings_df, test_device_connection,
)
from device_gateway.registry import PROTOCOL_LABELS
from device_gateway.normalize import CANONICAL_METRICS

st.set_page_config(page_title="Device Gateway | Formlabs MES", page_icon="🔌", layout="wide")
st.logo("assets/formlabs_logo.png")


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
st.markdown(THEMES.get(active_theme, THEMES["Default Dark"]), unsafe_allow_html=True)

cookie_manager = stx.CookieManager(key="device_registry_cookies")
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

if not role_can_administer(st.session_state.get("user_role")):
    st.error("🔒 Access Denied: Restricted to IT Administrators.")
    st.stop()

# The gateway is off in most plants. Turning it on is a decision somebody
# makes in Plant Settings, not something you fall into by opening a page, so
# this says where the switch is instead of showing an empty registry.
if not bool(get_plant_settings().get("enable_device_gateway", 0)):
    st.warning("🔌 The hardware gateway is switched off for this plant.")
    st.caption(
        "Turn it on in IT Admin under Plant Settings, then come back here to "
        "register machines. Nothing is polled until the gateway process is "
        "running as well.")
    st.page_link("pages/Admin_Panel.py", label="Open IT Admin", icon="🛡️")
    st.stop()

with st.sidebar:
    st.markdown("---")
    st.markdown(f"### 👤 {st.session_state.get('user_name', 'Operator')}")
    st.caption(f"Role: `{str(st.session_state.get('user_role', 'unknown')).upper()}`")
    st.markdown("#### 🗺️ Navigation")
    st.page_link("Home.py", label="Live SCADA", icon="⚡")
    st.page_link("pages/Operator_Form.py", label="Operator Form", icon="📝")
    st.page_link("pages/Manager_Cockpit.py", label="Manager Cockpit", icon="📊")
    st.page_link("pages/Live_Reactors.py", label="Live Reactors", icon="🛢️")
    st.page_link("pages/Analytics_Hub.py", label="Analytics Hub", icon="🌌")
    st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️")
    st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")
    st.markdown("---")
    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="dr_logout_btn"):
        do_logout(cookie_manager)
        # Every other page sends you back to the sign-in screen; this one used
        # to rerun in place, which on a page that requires a login is a guard
        # bouncing you somewhere anyway - just less predictably.
        st.switch_page("Home.py")


def _time_ago(dt) -> str:
    if dt is None:
        return "never"
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except Exception:
            return "unknown"
    now = datetime.utcnow()
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = delta.total_seconds()
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


STATUS_COLORS = {"Online": "#10B981", "Offline": "#F59E0B", "Error": "#EF4444", "Unknown": "#64748B"}

st.title("🔌 Device Gateway")
st.caption(
    "Register machines here — filling stations, scales, label printers, whatever's next — "
    "regardless of what protocol they speak. Assign each one to the pump station it sits on, "
    "map its tags, and the gateway service does the rest: readings land in Analytics the same "
    "way a hand-typed count does. This page edits the device registry; run_gateway.py is the "
    "process that actually polls."
)

df_devices = get_devices_df()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Devices", len(df_devices))
k2.metric("Online", int((df_devices["status"] == "Online").sum()) if not df_devices.empty else 0)
k3.metric("Error", int((df_devices["status"] == "Error").sum()) if not df_devices.empty else 0)
k4.metric("Disabled", int((~df_devices["is_enabled"]).sum()) if not df_devices.empty else 0)

tab_devices, tab_add, tab_readings = st.tabs(["📋 Devices", "➕ Add / Test Device", "📈 Recent Readings"])

# ============================== DEVICES TAB ================================
with tab_devices:
    if df_devices.empty:
        st.info("No devices registered yet — add one in the **Add / Test Device** tab.")
    else:
        for _, row in df_devices.iterrows():
            color = STATUS_COLORS.get(row["status"], STATUS_COLORS["Unknown"])
            with st.container():
                c_info, c_actions = st.columns([4, 1])
                with c_info:
                    st.markdown(
                        f"<div style='background:#0F172A; padding:12px 16px; border-radius:6px; "
                        f"border:1px solid #1E293B; margin-bottom:6px;'>"
                        f"<b style='color:#FFFFFF; font-size:1.05rem;'>{esc(row['device_name'])}</b> "
                        f"<span style='color:{color}; font-weight:bold; font-size:0.85rem;'>● {esc(row['status'])}</span>"
                        f"<br><span style='color:#94A3B8; font-size:0.85rem;'>"
                        f"{PROTOCOL_LABELS.get(row['protocol'], row['protocol'])} · role: {row['device_role']} · "
                        f"pump: {row['assigned_pump']} · reactor: {row['assigned_reactor']} · "
                        f"last seen {_time_ago(row['last_seen_at'])}</span>"
                        + (f"<br><span style='color:#EF4444; font-size:0.8rem;'>{row['last_error']}</span>"
                           if row.get("last_error") else "")
                        + "</div>", unsafe_allow_html=True,
                    )
                with c_actions:
                    toggle_label = "⏸️ Disable" if row["is_enabled"] else "▶️ Enable"
                    if st.button(toggle_label, key=f"toggle_{row['id']}", use_container_width=True):
                        set_device_enabled(int(row["id"]), not bool(row["is_enabled"]))
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"del_dev_{row['id']}", use_container_width=True):
                        delete_device(int(row["id"]))
                        st.rerun()

                with st.expander(f"🏷️ Tag Map — {row['device_name']}"):
                    df_tags = get_tag_map_df(int(row["id"]))
                    if not df_tags.empty:
                        st.dataframe(df_tags.drop(columns=["id"]), use_container_width=True, hide_index=True)
                        del_col1, del_col2 = st.columns([3, 1])
                        with del_col2:
                            tag_to_delete = st.selectbox(
                                "Remove row", ["—"] + df_tags["raw_tag"].tolist(),
                                key=f"tagdel_{row['id']}", label_visibility="collapsed",
                            )
                            if tag_to_delete != "—" and st.button("Remove", key=f"tagdelbtn_{row['id']}"):
                                tag_id = int(df_tags[df_tags["raw_tag"] == tag_to_delete]["id"].iloc[0])
                                delete_tag_map_row(tag_id)
                                st.rerun()
                    else:
                        st.caption("No tags mapped yet.")

                    st.markdown("**Add / update a tag**")
                    tc1, tc2, tc3, tc4, tc5 = st.columns([2, 2, 1, 1, 1])
                    raw_tag = tc1.text_input("Raw tag", key=f"rawtag_{row['id']}",
                                              help="Register address / node id / MQTT topic / regex / JSON path — depends on the device's protocol.")
                    canonical = tc2.selectbox("Canonical metric", list(CANONICAL_METRICS),
                                               key=f"canon_{row['id']}")
                    dtype = tc3.selectbox("Type", ["float", "int", "string", "bool"], key=f"dtype_{row['id']}")
                    scale = tc4.number_input("Scale ×", value=1.0, step=0.1, key=f"scale_{row['id']}")
                    unit = tc5.text_input("Unit", key=f"unit_{row['id']}", placeholder="g")
                    if st.button("💾 Save Tag", key=f"savetag_{row['id']}"):
                        if raw_tag.strip():
                            upsert_tag_map_row(int(row["id"]), raw_tag.strip(), canonical, dtype, scale, unit)
                            st.toast("Tag saved.")
                            st.rerun()
                        else:
                            st.error("Raw tag can't be empty.")

# ============================== ADD / TEST TAB ==============================
with tab_add:
    st.markdown("#### Register a Device")

    col1, col2 = st.columns(2)
    with col1:
        device_name = st.text_input("Device Name", placeholder="e.g. Filling Station 3 (ICC HMI)")
        device_role = st.selectbox("Role", ["filling_station", "scale", "label_printer", "reactor_sensor", "other"])
        protocol = st.selectbox("Protocol", list(PROTOCOL_LABELS), format_func=lambda p: PROTOCOL_LABELS[p])
    with col2:
        pumps = get_all_pumps_df()
        pump_options = {"— none —": None}
        if not pumps.empty:
            pump_options.update({r["station_name"]: int(r["id"]) for _, r in pumps.iterrows()})
        pump_label = st.selectbox("Assign to Pump Station", list(pump_options))

        reactors = get_all_reactors_df()
        reactor_options = {"— none —": None}
        if reactors is not None and not reactors.empty:
            reactor_options.update({r["reactor_name"]: int(r["id"]) for _, r in reactors.iterrows()})
        reactor_label = st.selectbox("Assign to Reactor", list(reactor_options))

        poll_interval = st.number_input("Poll Interval (seconds)", value=5.0, min_value=0.5, step=0.5)

    st.markdown("##### Connection Details")
    connection: dict = {}
    if protocol == "modbus_tcp":
        c1, c2, c3 = st.columns(3)
        connection["host"] = c1.text_input("Host / IP", placeholder="10.0.4.22")
        connection["port"] = c2.number_input("Port", value=502)
        connection["unit_id"] = c3.number_input("Unit / Slave ID", value=1)
    elif protocol == "modbus_rtu":
        c1, c2, c3, c4 = st.columns(4)
        connection["port"] = c1.text_input("COM Port", placeholder="COM5")
        connection["baud"] = c2.number_input("Baud", value=9600)
        connection["parity"] = c3.selectbox("Parity", ["N", "E", "O"])
        connection["unit_id"] = c4.number_input("Unit / Slave ID", value=1)
    elif protocol == "opcua":
        connection["endpoint"] = st.text_input("Endpoint URL", placeholder="opc.tcp://10.0.4.40:4840")
        c1, c2 = st.columns(2)
        connection["username"] = c1.text_input("Username (optional)") or None
        connection["password"] = c2.text_input("Password (optional)", type="password") or None
    elif protocol == "mqtt":
        c1, c2 = st.columns(2)
        connection["host"] = c1.text_input("Broker Host", placeholder="10.0.4.5")
        connection["port"] = c2.number_input("Broker Port", value=1883)
        c3, c4 = st.columns(2)
        connection["username"] = c3.text_input("Username (optional)") or None
        connection["password"] = c4.text_input("Password (optional)", type="password") or None
    elif protocol == "serial_ascii":
        c1, c2, c3 = st.columns(3)
        connection["port"] = c1.text_input("COM Port", placeholder="COM4")
        connection["baud"] = c2.number_input("Baud", value=9600)
        connection["read_timeout_s"] = c3.number_input("Read Timeout (s)", value=1.0)
        connection["request_command"] = st.text_input(
            "Request Command (leave blank for continuous-stream scales)",
            placeholder=r"P\r\n") or None
    elif protocol == "http_poll":
        connection["url"] = st.text_input("URL", placeholder="http://10.0.4.60/api/status")
        c1, c2 = st.columns(2)
        connection["method"] = c1.selectbox("Method", ["GET", "POST"])
        connection["timeout_s"] = c2.number_input("Timeout (s)", value=5.0)

    st.markdown("##### Probe Tags (optional — see what the machine actually reports before saving)")
    probe_text = st.text_area(
        "One raw tag per line",
        placeholder="Modbus: register addresses (e.g. 40001)\nOPC-UA: node ids\nMQTT: topics\n"
                    "serial_ascii: a regex with a (?P<value>...) group\nhttp_poll: dotted JSON paths",
        height=100,
    )
    if st.button("🔎 Test Connection"):
        probe_tags = [line.strip() for line in probe_text.splitlines() if line.strip()]
        temp_tag_map = [{"raw_tag": t, "canonical_metric": t, "data_type": "float", "scale_factor": 1.0}
                        for t in probe_tags]
        with st.spinner("Connecting..."):
            result = test_device_connection(protocol, connection, temp_tag_map)
        if "error" in result:
            st.error(f"Connection failed: {result['error']}")
        else:
            st.success("Connected successfully.")
            st.json(result.get("raw", {}))

    st.markdown("---")
    notes = st.text_area("Notes", placeholder="Optional")
    if st.button("💾 Save Device", type="primary", use_container_width=True):
        if not device_name.strip():
            st.error("Device name is required.")
        else:
            new_id = create_device(
                device_name=device_name, device_role=device_role, protocol=protocol,
                connection=connection, poll_interval_s=poll_interval,
                pump_station_id=pump_options[pump_label], reactor_id=reactor_options[reactor_label],
                notes=notes,
            )
            if new_id:
                st.toast(f"✅ Added {device_name} — map its tags in the Devices tab.")
                st.rerun()
            else:
                st.error("A device with that name already exists.")

# ============================== READINGS TAB ================================
with tab_readings:
    if df_devices.empty:
        st.info("No devices registered yet.")
    else:
        device_label = st.selectbox("Device", df_devices["device_name"].tolist())
        device_id = int(df_devices[df_devices["device_name"] == device_label]["id"].iloc[0])
        hours = st.slider("Look back (hours)", 1, 72, 4)
        df_readings = get_recent_readings_df(device_id, hours=hours)
        if df_readings.empty:
            st.info("No readings yet for this device in that window — check that run_gateway.py is running.")
        else:
            numeric = df_readings.dropna(subset=["value_numeric"])
            if not numeric.empty:
                pivoted = numeric.pivot_table(index="timestamp", columns="metric", values="value_numeric")
                st.line_chart(pivoted)
            st.dataframe(
                df_readings[["timestamp", "metric", "value_numeric", "value_text"]],
                use_container_width=True, hide_index=True,
            )
