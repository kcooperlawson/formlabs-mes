"""
device_gateway/field_check.py - `python run_gateway.py --check`.

Answers "will the gateway work on THIS PC?" before anyone relies on it. It
has to be run on the floor PC itself: whether the database, the PLCs and the
COM ports are reachable depends entirely on which network and which cables
this particular PC has, which nothing on the MES side can test.

run_gateway.py has already logged into the database before this runs. From
there it checks, read-only:
  * whether this PC's GATEWAY_ENCRYPTION_KEY can open every saved device;
  * which gateway PCs are checking in (two at once double-count production);
  * each enabled device: its host/port answers a TCP connection, or its COM
    port is present - then a real one-shot read through its own adapter,
    exactly what the gateway will do.

Exit code 0 when nothing is wrong, 1 otherwise, so it can be scripted.
"""
import concurrent.futures
import socket
from urllib.parse import urlparse

OK, BAD, WARN, INFO = "  [ok]", "  [X] ", "  [!] ", "      "
ADAPTER_TIMEOUT_S = 12.0


def _network_target(protocol: str, connection: dict):
    """(host, port) for a network protocol, else None."""
    if protocol == "modbus_tcp":
        return connection.get("host"), int(connection.get("port") or 502)
    if protocol == "mqtt":
        return connection.get("host"), int(connection.get("port") or 1883)
    if protocol == "opcua":
        parsed = urlparse(str(connection.get("endpoint") or ""))
        return parsed.hostname, parsed.port or 4840
    if protocol == "http_poll":
        parsed = urlparse(str(connection.get("url") or ""))
        return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    return None


def _tcp_reach(host: str, port: int, timeout_s: float = 3.0):
    """(True, None) or (False, a plain-words reason)."""
    if not host:
        return False, "no host is filled in for this device"
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True, None
    except socket.gaierror:
        return False, f"this PC can't look up the name {host!r}"
    except ConnectionRefusedError:
        return False, (f"{host} answered, but nothing is listening on port {port} - "
                       f"is the machine's server/protocol switched on?")
    except (socket.timeout, TimeoutError):
        return False, (f"nothing answered from {host}:{port} within {timeout_s:.0f} s - "
                       f"wrong address, powered off, or a firewall/VLAN between this PC and it")
    except OSError as exc:
        return False, f"{host}:{port} - {exc}"


def _adapter_read(device, tag_rows):
    """One connect + read + close through the device's real adapter, bounded."""
    from .registry import build_adapter_from_device

    def attempt():
        adapter = build_adapter_from_device(device, tag_rows)
        adapter.connect()
        try:
            return adapter.poll()
        finally:
            adapter.close()

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(attempt).result(timeout=ADAPTER_TIMEOUT_S), None
    except concurrent.futures.TimeoutError:
        return None, f"no answer within {ADAPTER_TIMEOUT_S:.0f} s"
    except Exception as exc:
        return None, (str(exc).strip() or type(exc).__name__)[:300]
    finally:
        pool.shutdown(wait=False)


def run_check() -> int:
    import device_crud
    from db_core import ScopedSession
    from device_models import Device, DeviceTagMap
    from gateway_crypto import KeyMismatchError, decrypt_connection_strict

    from .discovery import list_serial_ports, local_ip

    problems = 0
    hostname = socket.gethostname()
    print()
    print("  ===================================================")
    print(f"   DEVICE GATEWAY CHECK - {hostname} ({local_ip()})")
    print("  ===================================================")
    print()
    print(OK, "Logged in to the MES database")

    session = ScopedSession()
    try:
        devices = session.query(Device).filter(Device.is_enabled.is_(True)).order_by(Device.device_name).all()
        tags = {d.id: session.query(DeviceTagMap).filter(DeviceTagMap.device_id == d.id).all() for d in devices}
        for d in devices:
            _ = (d.id, d.device_name, d.protocol, d.connection_json, d.poll_interval_s, d.device_role,
                 d.is_enabled, d.pump_station_id, d.reactor_id)
            for t in tags[d.id]:
                _ = (t.raw_tag, t.canonical_metric, t.data_type, t.scale_factor)
    finally:
        session.close()

    # --- other gateways ---------------------------------------------------
    others = [g for g in device_crud.get_gateway_nodes() if g["online"] and g["hostname"] != hostname]
    if others:
        problems += 1
        print(BAD, "Another gateway is already running: " + ", ".join(g["hostname"] for g in others))
        print(INFO, "Two gateways poll every device twice and log production twice. Run it on one PC only.")
    else:
        print(OK, "No other gateway PC is running right now")

    # --- the encryption key -------------------------------------------------
    readable = {}
    key_problem = None
    for d in devices:
        try:
            readable[d.id] = decrypt_connection_strict(d.connection_json)
        except KeyMismatchError as exc:
            key_problem = str(exc)
    if key_problem:
        problems += 1
        print(BAD, f"{len(devices) - len(readable)} of {len(devices)} device(s) can't be read with this PC's key")
        print(INFO, key_problem)
    elif devices:
        print(OK, f"This PC's encryption key opens all {len(devices)} enabled device(s)")

    # --- serial ports -------------------------------------------------------
    ports = list_serial_ports()
    port_names = {p["port"].upper() for p in ports}
    if ports:
        print(OK, "Serial ports on this PC: " + ", ".join(
            f"{p['port']} ({p['description']})" if p["description"] else p["port"] for p in ports))
    else:
        print(INFO, "No serial/COM ports on this PC")

    # --- each device --------------------------------------------------------
    print()
    if not devices:
        print(WARN, "No devices are registered and enabled yet - nothing else to check.")
    for d in devices:
        print(f"  {d.device_name}  ({d.protocol})")
        connection = readable.get(d.id)
        if connection is None:
            print(BAD, "skipped - its connection details can't be read (see the key problem above)")
            continue

        if d.protocol == "simulator":
            print(OK, "simulated - no hardware to reach")
        elif d.protocol in ("serial_ascii", "modbus_rtu"):
            port = str(connection.get("port") or "")
            if port.upper() in port_names:
                print(OK, f"{port} is present on this PC")
            else:
                problems += 1
                here = ", ".join(sorted(port_names)) or "none"
                print(BAD, f"{port or '(no port set)'} isn't on this PC (ports here: {here}) - "
                           f"wrong port, cable unplugged, or this device is cabled to a different PC")
                continue
        else:
            target = _network_target(d.protocol, connection)
            if target:
                reached, why = _tcp_reach(*target)
                if not reached:
                    problems += 1
                    print(BAD, why)
                    continue
                print(OK, f"{target[0]}:{target[1]} answers from this PC")

        values, error = _adapter_read(d, tags[d.id])
        if error:
            if "access is denied" in error.lower() or "permissionerror" in error.lower():
                print(WARN, f"port is in use - usually because the gateway is already running here and has it open ({error})")
            else:
                problems += 1
                print(BAD, f"connected, but the read failed: {error}")
        elif values:
            shown = ", ".join(f"{k}={v}" for k, v in list(values.items())[:4])
            print(OK, f"read {len(values)} value(s): {shown}")
        elif not tags[d.id]:
            print(WARN, "connected, but no tags are mapped yet, so nothing will be recorded")
        else:
            print(WARN, "connected, but none of its mapped tags returned a value just now")

    print()
    if problems:
        print(f"  {problems} problem(s) above. Fix them, then run this check again.")
    else:
        print("  Everything this PC needs is reachable. Start the gateway with START_HERE.bat, option 4.")
    print()
    return 1 if problems else 0
