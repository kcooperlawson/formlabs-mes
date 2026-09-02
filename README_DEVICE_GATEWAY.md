# Device Gateway

Backend for wiring real plant equipment — pump/filling controllers, bench scales, eventually label printers — into Formlabs MES, without having to hardcode what protocol each machine speaks.

## Why it's built this way

I don't know upfront what protocol every machine on the floor uses, so the schema doesn't assume one. Every machine gets a row in a `devices` table with a `protocol` column, and the actual polling logic for each protocol lives in its own small **adapter** file behind one shared interface (`connect()` / `poll()` / `close()`). The rest of the system — the gateway loop, the admin page, the DB write logic — never looks at `protocol` again after it's picked the right adapter. Adding a machine that speaks something not covered here means writing one new adapter file and registering it in one place (`device_gateway/registry.py`); nothing else changes.

Six adapters ship in this scaffold, covering what plant-floor equipment overwhelmingly turns out to speak:

| Protocol | File | Typical fit |
|---|---|---|
| Modbus TCP | `adapters/modbus_tcp.py` | Most PLC-driven HMI panels — probably the pump/filling controllers. Worth asking whoever maintains them if it has a Modbus TCP server before assuming anything more exotic — it's usually one setting in the PLC project even when the touchscreen doesn't advertise it. |
| Modbus RTU | `adapters/modbus_rtu.py` | Same, over RS-485/RS-232 serial, for older panels with no Ethernet port. |
| OPC-UA | `adapters/opcua_client.py` | Newer/"Industry 4.0" equipment, or anything behind a UA gateway. |
| MQTT | `adapters/mqtt_client.py` | IIoT-style machines, or a Raspberry Pi bolted onto an older machine publishing to a broker. |
| Serial ASCII | `adapters/serial_ascii.py` | Bench scales — this is almost certainly what the two ULINE H-1650 / Mettler Toledo scales on the carts speak. Most scales stream or print plain text over RS-232/USB-serial; the adapter doesn't hardcode a vendor's format, it applies whatever regex you give it per tag. |
| HTTP/REST | `adapters/http_poll.py` | Newer label printers or controllers with a local web API / status JSON endpoint. |

## How a reading becomes an Analytics number

The gateway never writes raw SQL into `production_logs`. It calls `crud.py`'s own `add_hourly_log()` — the same function `Operator_Form.py` calls when someone types a count in by hand — tagged with an operator name of `"Automated Gateway"`. That means:

- Every business rule already in `crud.py` (AssignedRun progress toward target, marking a run "Done", resolving FKs against users/pump_stations/resin_specs) applies to machine-sourced data automatically, no duplicated logic to drift out of sync.
- `Analytics_Hub.py`, `Manager_Cockpit.py`, `Live_Reactors.py`, `Tv_Dashboard.py` don't need to change. They already read `ProductionLog`/`AssignedRun` and have no way to tell whether a row came from a keyboard or a machine.

Every reading also gets written to a new `device_readings` table regardless of whether it triggers a production-log row — a raw audit trail for machine-level telemetry (fault codes, uptime, raw weight curves) I can query directly later if I want a dedicated view for it.

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
service_announcer.py              # advertises this PC's database on the local network (mDNS) - runs inside Home.py
service_discovery.py              # finds that announcement - used by run_gateway.py
pages/Device_Registry.py          # the admin UI: find, add, assign, test-connect, tag-map, watch recent readings
requirements-device-gateway.txt   # pymodbus, pyserial, opcua, paho-mqtt
```

## Wiring it in (three small edits to existing files)

1. **`database.py`** — add two lines to the facade imports so `pages/Device_Registry.py` (and anything else) can `from database import ...` the same way every other page does:

   ```python
   from device_models import Device, DeviceTagMap, DeviceReading
   from device_crud import *
   ```

2. **Run the migration.** Same pattern as the existing `0001_baseline`:

   ```
   alembic upgrade head
   ```

   (`init_db()` in `crud.py` already runs this on every boot, so in practice this might just happen on its own the first time the app starts after these files are dropped in.)

3. **Sidebar links** — `pages/Device_Registry.py` already includes a `st.page_link` for itself. Add the same line to the sidebar block in whichever other pages should have a shortcut (`Admin_Panel.py` makes sense, since this page is admin-gated the same way):

   ```python
   st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")
   ```

4. **Install the extra dependencies:**

   ```
   pip install -r requirements-device-gateway.txt
   ```

## Running it

Two processes, same as most SCADA/MES setups split this way:

- `streamlit run Home.py` — unchanged, this is the UI including the new Device Registry page. It now also announces the database on the local network (see auto-discovery below) so a gateway running elsewhere can find it.
- `python run_gateway.py` — new, the background poller. Run it on whatever machine actually has network/USB/COM-port access to the equipment being registered (a floor PC, not necessarily wherever Postgres lives) — see the docstring at the top of `run_gateway.py` for wrapping it as a Windows service or systemd unit so it survives reboots.

## Auto-discovery — running the gateway on a different PC than Postgres

If `run_gateway.py` runs on the same PC as Postgres (simplest setup), skip this section — it already works with zero configuration.

If it runs on a different floor PC, which is the whole point of the gateway being its own process, here's how that actually works:

Zip the whole project folder as-is (`.env` included) and unzip it on the other PC. Run it. No file needs editing, even if the app later moves to yet another PC.

`run_gateway.py` always searches the local network first for the main app announcing itself (`service_announcer.py`, running automatically inside `Home.py`), and connects to whatever it finds. It pulls login credentials out of whatever's already in that copied-over `.env` — the username/password embedded in `DB_URL` if that's a real connection string, or `PG_PASS` (the same key the backup/restore tooling already uses) otherwise — so the same `.env` works unmodified whether it's sitting on the PC hosting Postgres or a gateway three rooms away. If nothing answers on the network, it falls back to that PC's own `DB_URL` directly (covers running gateway + Postgres on the same box) before giving up with a clear message about what to check.

The one thing that has to be done manually, one time, on whichever PC hosts the database:

- In `postgresql.conf` (find its path with `SHOW config_file;` in `psql`, or check the `data\` folder next to `PG_BIN_DIR`), set `listen_addresses = '*'`
- In `pg_hba.conf` (same folder), add a line allowing the plant's subnet, e.g. for a typical home/small-office range: `host formlabs_mes postgres 192.168.0.0/24 scram-sha-256` (match whatever auth method the other `host` lines in that file already use — `scram-sha-256` is Postgres 18's default)
- Restart the PostgreSQL service (`services.msc` → `postgresql-x64-18` → Restart) so both changes take effect
- Open port 5432 to that subnet in Windows Firewall (it usually prompts for this the first time something listens on a new port; otherwise add an inbound rule manually)

This is plant-network exposure, not internet exposure — nothing here opens Postgres to anything outside the local network. It's a one-time setting on the database PC, not something to redo per move or per gateway.

**Escape hatch:** if a floor PC's network genuinely can't pass mDNS traffic (managed switch doing client isolation, a separate VLAN, etc.), set `GATEWAY_DB_URL` in that one PC's `.env` to a full, manually-typed connection string. Skips discovery entirely for that machine only — everything else keeps auto-discovering as normal.

## Rollout plan — start with what's easiest to test

No need to wire up the filling controller first. The lowest-risk first target is one of the two ULINE bench scales on the carts:

1. Find out what the scale's data port actually is — RS-232 DB9, or a USB port that shows up as a virtual COM port. ULINE scales in this class typically support continuous or on-demand ASCII output over one of those.
2. Plug it into whatever PC will run `run_gateway.py`, note the COM port Windows assigns it, and add it as a device with protocol `serial_ascii`.
3. Use the Test Connection probe in the admin page with a generic regex like `(?P<value>[-\d.]+)` against a few raw lines to see the actual framing (units, sign, whitespace) before writing the tag map.
4. Once one scale is flowing into `device_readings`, that proves the whole path — gateway process, adapter, DB write — end to end, with a simple device. Then go after the filling/pump HMI (ask whoever maintains it whether it has a Modbus TCP server first — likeliest path for that class of controller) and eventually the label printers, one adapter/device at a time, without anything else in the app changing.

## Adding a 7th protocol later

1. `device_gateway/adapters/your_protocol.py` — subclass `DeviceAdapter` from `adapters/base.py`, implement `connect()`, `_read_raw()`, `close()`.
2. One line in `device_gateway/registry.py`'s `ADAPTERS` dict (and `PROTOCOL_LABELS`, so it shows up in the admin page's dropdown).

Nothing in `service.py`, `writer.py`, or `pages/Device_Registry.py` needs to change — they all work against the shared `DeviceAdapter` interface and the canonical metric names in `normalize.py`, not any one protocol's specifics.
