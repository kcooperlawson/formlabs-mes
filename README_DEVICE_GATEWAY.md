# Device Gateway

A protocol-agnostic backend for wiring real machines — the pump/filling
controllers, the bench scales, and eventually the label printers and
whatever else — into Formlabs MES, without needing to know in advance
what protocol each one speaks.

## Why this shape

You don't know what protocol "he" used on the other machines, and that's
fine — the design doesn't ask you to know up front. Every machine gets one
row in a `devices` table with a `protocol` column; the actual polling
logic for each protocol lives in its own small **adapter** file behind one
shared interface (`connect()` / `poll()` / `close()`). The rest of the
system — the gateway loop, the admin page, the write-to-database logic —
never looks at `protocol` again after picking the right adapter. Adding a
machine that speaks a protocol nothing here supports yet means writing one
new adapter file and registering it in one place
(`device_gateway/registry.py`); nothing else changes.

Six adapters ship in this scaffold, chosen to cover what plant-floor
equipment overwhelmingly turns out to speak:

| Protocol | File | Typical fit |
|---|---|---|
| Modbus TCP | `adapters/modbus_tcp.py` | Most PLC-driven HMI panels — including, most likely, the pump/filling controllers in your photos. Ask whoever maintains them "does it have a Modbus TCP server?" before assuming anything more exotic is needed; it's usually one setting in the PLC project even when the touchscreen doesn't advertise it. |
| Modbus RTU | `adapters/modbus_rtu.py` | Same, over RS-485/RS-232 serial, for older panels with no Ethernet port. |
| OPC-UA | `adapters/opcua_client.py` | Newer/"Industry 4.0" equipment, or anything behind a UA gateway. |
| MQTT | `adapters/mqtt_client.py` | IIoT-style machines, or a Raspberry Pi bolted onto an older machine that publishes to a broker. |
| Serial ASCII | `adapters/serial_ascii.py` | Bench scales — **this is almost certainly what the two ULINE H-1650 / Mettler Toledo scales on your carts speak.** Most scales stream or print plain text over RS-232/USB-serial; the adapter doesn't hardcode a vendor's format, it applies whatever regex you give it per tag. |
| HTTP/REST | `adapters/http_poll.py` | Newer label printers or controllers with a local web API / status JSON endpoint. |

## How a reading becomes an Analytics number

This is the part that matters most: **the gateway never writes raw SQL
into `production_logs`.** It calls `crud.py`'s own `add_hourly_log()` —
the exact function `Operator_Form.py` calls when a person types a count in
by hand — tagged with an operator name of `"Automated Gateway"`. That
means:

- Every business rule already in `crud.py` (AssignedRun progress toward
  target, marking a run "Done", resolving FKs against
  users/pump_stations/resin_specs) applies to machine-sourced data
  automatically, with no duplicated logic to drift out of sync.
- `Analytics_Hub.py`, `Manager_Cockpit.py`, `Live_Reactors.py`,
  `Tv_Dashboard.py` — **none of them need to change.** They already read
  `ProductionLog`/`AssignedRun`; they have no way to tell whether a row
  came from a keyboard or a machine.

Every reading is also written to a new `device_readings` table regardless
of whether it triggers a production-log row — a raw audit trail for
machine-level telemetry (fault codes, uptime, raw weight curves) that
Analytics can query directly later if you want a dedicated view for it.

## What's in this delivery

```
device_models.py                  # Device, DeviceTagMap, DeviceReading (new tables)
device_crud.py                    # CRUD for them, same ScopedSession pattern as crud.py
migrations/versions/0002_device_gateway_schema.py   # Alembic migration for the above
device_gateway/
  adapters/
    base.py                       # the DeviceAdapter interface every protocol implements
    modbus_tcp.py  modbus_rtu.py  opcua_client.py  mqtt_client.py  serial_ascii.py  http_poll.py
  registry.py                     # protocol name -> adapter class (the one place to edit for a 7th protocol)
  normalize.py                    # the canonical metric vocabulary (weight_g, units_poured_delta, ...)
  writer.py                       # normalized reading -> DeviceReading row + (if it's a fill cycle) add_hourly_log()
  service.py                      # the background poller: one thread per enabled device, hot-reloads the devices table
run_gateway.py                    # `python run_gateway.py` — standalone entrypoint, run as its own process/service
pages/Device_Registry.py          # the admin UI: find, add, assign, test-connect, tag-map, watch recent readings
requirements-device-gateway.txt   # pymodbus, pyserial, opcua, paho-mqtt
```

## Wiring it in (three small edits to existing files)

1. **`database.py`** — add two lines to the facade imports so
   `pages/Device_Registry.py` (and anything else) can `from database
   import ...` the same way every other page does:

   ```python
   from device_models import Device, DeviceTagMap, DeviceReading
   from device_crud import *
   ```

2. **Run the migration.** Same pattern as your existing `0001_baseline`:

   ```
   alembic upgrade head
   ```

   (`init_db()` in `crud.py` already runs this on every boot, so in
   practice you may not need to do anything manually — just start the app
   once after dropping these files in.)

3. **Sidebar links** — `pages/Device_Registry.py` already includes a
   `st.page_link` for itself. Add the same one line to the sidebar block
   in whichever other pages you want a shortcut from (Admin_Panel.py is
   the natural one, since this page is admin-gated the same way):

   ```python
   st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")
   ```

4. **Install the extra dependencies:**

   ```
   pip install -r requirements-device-gateway.txt
   ```

## Running it

Two processes from here on, same as most SCADA/MES split:

- `streamlit run Home.py` — unchanged, this is the UI including the new
  Device Registry page.
- `python run_gateway.py` — **new**, the background poller. Run it on a
  machine with actual network/USB/COM-port access to the equipment you
  register (a floor PC, not necessarily wherever Postgres lives) — see the
  docstring at the top of `run_gateway.py` for wrapping it as a Windows
  service or systemd unit so it survives reboots.

## Rollout plan — start with what you can already see

You don't need to wire up the filling controller first. In fact, the
lowest-risk first target is almost certainly one of the two ULINE bench
scales on the carts:

1. Find out what the scale's data port actually is — RS-232 DB9, or a USB
   port that shows up as a virtual COM port. Uline scales in this class
   typically support a continuous or on-demand ASCII output over one of
   those.
2. Plug it into whatever PC will run `run_gateway.py`, note the COM port
   Windows assigns it, and add it as a device with protocol
   `serial_ascii`.
3. Use the **Test Connection** probe in the admin page with a generic
   regex like `(?P<value>[-\d.]+)` against a few raw lines to see the
   actual framing (units, sign, whitespace) before writing the tag map.
4. Once one scale is flowing into `device_readings`, you've proven the
   whole path — gateway process, adapter, DB write — end to end, with a
   simple device. *Then* go after the filling/pump HMI (start by asking
   whoever maintains it whether it has a Modbus TCP server; that's the
   likeliest path for that class of controller) and eventually the label
   printers, adding one adapter/device at a time without anything else in
   the app changing.

## Adding a 7th protocol later

1. `device_gateway/adapters/your_protocol.py` — subclass `DeviceAdapter`
   from `adapters/base.py`, implement `connect()`, `_read_raw()`,
   `close()`.
2. One line in `device_gateway/registry.py`'s `ADAPTERS` dict (and
   `PROTOCOL_LABELS`, so it shows up in the admin page's dropdown).

Nothing in `service.py`, `writer.py`, or `pages/Device_Registry.py` needs
to change — they all work against the shared `DeviceAdapter` interface and
the canonical metric names in `normalize.py`, not against any one
protocol's specifics.
