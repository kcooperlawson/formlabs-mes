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
  discovery.py                    # "find devices" - serial port enumeration + local-subnet TCP scan for the admin page
  writer.py                       # normalized reading -> DeviceReading row + (if it's a fill cycle) add_hourly_log()
  service.py                      # the background poller: one thread per enabled device, hot-reloads the devices table
  jobs.py                         # Find Devices / Test Connection requests, run on the gateway PC for the admin page
  field_check.py                  # `run_gateway.py --check`: can THIS PC reach the database and every machine?
migrations/versions/0024_gateway_nodes_and_jobs.py  # gateway check-ins + the job table (4.07)
run_gateway.py                    # `python run_gateway.py` — standalone entrypoint, run as its own process/service
dev/simulate_gateway_network.py   # fake PLC + pullable network cables: proves the gateway rides out outages
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

- `START_HERE.bat`, option 3 — the main app, including the Device Registry page in the React frontend. It also announces the database on the local network (see auto-discovery below) so a gateway running elsewhere can find it.
- `python run_gateway.py` (`START_HERE.bat`, option 4) — the background poller. Run it on whatever machine actually has network/USB/COM-port access to the equipment being registered (a floor PC, not necessarily wherever Postgres lives) — see the docstring at the top of `run_gateway.py` for wrapping it as a Windows service or systemd unit so it survives reboots.

Run it on **one** PC. Every gateway polls every enabled device, so two running at once read each machine twice and log its production twice — the Device Registry shows a red warning if it sees that.

### Before trusting a floor PC: `run_gateway.py --check`

`START_HERE.bat`, option 12, on the floor PC itself. It logs in to the database the same way the gateway does, then checks that this PC's `GATEWAY_ENCRYPTION_KEY` can open every saved device, that every network device's address answers from *this* PC, that every serial device's COM port is present on *this* PC, and does one real read from each. It prints `[ok]` / `[X]` per item with the reason, and exits 1 if anything failed. Nothing on the MES side can test this for you — whether a PLC is reachable depends entirely on which network and which cables the floor PC has.

### When the network drops

The gateway waits out a database outage instead of exiting: it logs `can't reach the MES database` once (and a reminder every minute), retries every few seconds, and carries on as soon as the database answers. Machines that report a running total (`units_poured_total`) lose no counts over an outage — the first reading afterwards is compared with the last one saved. At startup it does the same: if the MES PC isn't up yet, it explains why it can't connect and keeps trying, so a floor PC that boots first still ends up connected.

Before 4.07 the first failed query ended the process, and nothing was read again until someone restarted it by hand.

### What the statuses mean

| Status | Meaning |
|---|---|
| Online | Real readings are arriving. |
| No data | Connected, but none of the mapped tags returned a value (or no tags are mapped yet). Reconnected after a minute of this. |
| Error | The machine can't be reached or refused the read — the message says which. |
| Not reporting | Nothing is reading this device: no gateway has checked in recently, or the gateway is running but hasn't produced a reading for this device in three polls. Worked out by the MES when the page loads, never stored. |

A gateway on 4.06 or older doesn't check in, so apply an update on the gateway PC as well as the MES PC.

## Auto-discovery — running the gateway on a different PC than Postgres

If `run_gateway.py` runs on the same PC as Postgres (simplest setup), skip this section — it already works with zero configuration.

If it runs on a different floor PC, which is the whole point of the gateway being its own process, here's how that actually works:

Zip the whole project folder as-is (`.env` included) and unzip it on the other PC. Run it. No file needs editing, even if the app later moves to yet another PC.

`run_gateway.py` always searches the local network first for the main app announcing itself (`service_announcer.py`, started automatically by `api/main.py`), and connects to whatever it finds. It pulls login credentials out of whatever's already in that copied-over `.env` — the username/password embedded in `DB_URL` if that's a real connection string, or `PG_PASS` (the same key the backup/restore tooling already uses) otherwise — so the same `.env` works unmodified whether it's sitting on the PC hosting Postgres or a gateway three rooms away. If nothing answers on the network, it falls back to that PC's own `DB_URL` directly (covers running gateway + Postgres on the same box) before giving up with a clear message about what to check.

The one thing that has to be done manually, one time, on whichever PC hosts the database:

- In `postgresql.conf` (find its path with `SHOW config_file;` in `psql`, or check the `data\` folder next to `PG_BIN_DIR`), set `listen_addresses = '*'`
- In `pg_hba.conf` (same folder), add a line allowing the plant's subnet, e.g. for a typical home/small-office range: `host formlabs_mes postgres 192.168.0.0/24 scram-sha-256` (match whatever auth method the other `host` lines in that file already use — `scram-sha-256` is Postgres 18's default)
- Restart the PostgreSQL service (`services.msc` → `postgresql-x64-18` → Restart) so both changes take effect
- Open port 5432 to that subnet in Windows Firewall (it usually prompts for this the first time something listens on a new port; otherwise add an inbound rule manually)

This is plant-network exposure, not internet exposure — nothing here opens Postgres to anything outside the local network. It's a one-time setting on the database PC, not something to redo per move or per gateway.

**Escape hatch:** if a floor PC's network genuinely can't pass mDNS traffic (managed switch doing client isolation, a separate VLAN, etc.), set `GATEWAY_DB_URL` in that one PC's `.env` to a full, manually-typed connection string. Skips discovery entirely for that machine only — everything else keeps auto-discovering as normal.

**If the MES PC uses the bundled database** (the normal setup from 4.08 on — `pgdata\` next to the project, no PostgreSQL install), it is private to that PC by default: it listens on 127.0.0.1 only, on a port picked fresh at every start, with no password. A gateway PC can't reach that, and no `.env` line will make it.

On the MES PC, run **`START_HERE.bat` option 15** once. It gives the database a fixed port (5433 by default) and a real password, allows the postgres login from the plant's subnet with `scram-sha-256`, and prints the two things left to do: one Windows Firewall rule on that PC, and one line for the gateway PC's `.env`:

```
GATEWAY_DB_URL=postgresql://postgres:PASSWORD@MES-PC-IP:5433/formlabs_mes
```

Then check it from the gateway PC with `START_HERE.bat` option 12. Turning it off again (option 15, then D) puts the database back to being private on the next start.

**On a corporate network, plan on the escape hatch.** mDNS is multicast, and multicast rarely crosses from one VLAN or subnet to another, which is exactly the layout of a plant network next to a corporate one. What the floor PC needs instead:

- `GATEWAY_DB_URL=postgresql://USER:PASSWORD@MES-PC-NAME-OR-IP:5432/formlabs_mes` in its `.env`
- a `pg_hba.conf` line on the MES PC for the floor PC's address (`host formlabs_mes postgres 10.x.x.x/32 scram-sha-256`)
- TCP 5432 allowed from the floor PC to the MES PC — Windows Firewall on the MES PC, and any firewall between the two networks
- the same `GATEWAY_ENCRYPTION_KEY` line as the MES PC's `.env`. The MES PC creates that key the first time a device is saved, so a floor PC set up before that has none; copy the line across by hand.

If any of those is missing, `run_gateway.py` says which one in plain words at startup (a `pg_hba.conf` rejection prints the exact line to add; a timeout points at the firewall; a `localhost` address points out the `.env` was copied from the MES PC), and `--check` reports it too.

## Find Devices — a Wi-Fi-picker-style scan instead of typing in connection details

The **🔍 Find Devices** tab on `pages/Device_Registry.py` (`device_gateway/discovery.py`) turns "I need this machine's IP address or COM port" into a list to click, the same way connecting to Wi-Fi does:

- **Serial / COM ports** — enumerates every port Windows currently sees plugged in (via `pyserial`, already a dependency for `modbus_rtu`/`serial_ascii`), so a scale or an RS-485 USB dongle appears the moment it's plugged in. Click **Use →** and it prefills COM port + a `serial_ascii` starting point in the Add tab.
- **Network scan** — a fast, read-only TCP connect-sweep of one subnet (defaulted from this PC's own LAN IP, editable for VLANs/other ranges) against the ports the network protocols conventionally use: 502 (Modbus TCP), 4840 (OPC-UA), 1883 (MQTT), 80/443 (HTTP). A host with one of those open shows up as a candidate with a guessed protocol; click **Use →** to prefill it. An open port is a hint, not a confirmed identification — always run **Test Connection** afterward (same probe the Add tab already used) before saving.

This only opens plain outbound TCP connections on the local network and closes them immediately, or reads OS-level serial port metadata — nothing is written to any machine, and nothing leaves the subnet you type in.

**Where it runs.** Both Find Devices and Test Connection have a **Look for machines from / Test from** picker listing every gateway PC that has checked in, plus the MES server itself. It defaults to the running gateway. Picking a gateway leaves a job in the `gateway_jobs` table; that gateway picks it up within a couple of seconds, runs the scan or the test on its own PC — its COM ports, its network — and writes the result back for the page (`device_gateway/jobs.py`). Before 4.07 these always ran inside the API process on the MES server, so from a corporate PC they listed the server's COM ports and scanned the server's subnet, not the floor's. A Test Connection password is encrypted while the job waits and cleared once it finishes.

For Modbus, a probe tag reads one raw register (`40001`); add `:float` or `:int32` for a two-register value (`40002:float`).

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
