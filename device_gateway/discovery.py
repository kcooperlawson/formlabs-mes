"""
device_gateway/discovery.py - "Find devices" support for the admin page.

The rest of the Device Gateway asks a person to already know a machine's
IP/port or COM port before they can add it. This module is what lets the
admin page instead show a scannable list — serial ports plugged into this
PC, and machines answering on the usual gateway ports on the local
network — so adding a device can look like picking a Wi-Fi network instead
of typing in connection details from a notebook.

Two independent things it finds, matching the two adapter families:

  - Serial ports (list_serial_ports): every COM port Windows currently
    sees, via pyserial's device enumeration. Covers modbus_rtu and
    serial_ascii (the bench scales this is a Serial or USB-to-serial
    device on this PC, not a network scan).

  - Network hosts (scan_network): a fast TCP connect-scan of a subnet for
    the ports the network-based protocols conventionally listen on
    (502 Modbus TCP, 4840 OPC-UA, 1883 MQTT, 80/443 HTTP). Finding an open
    port is a hint, not a confirmed identification — a host with 502 open
    is *probably* a Modbus TCP server, not guaranteed one, the same way a
    Wi-Fi picker shows you a network name before you've actually connected
    to it. The existing "Test Connection" probe (test_device_connection in
    device_crud.py) is still what actually confirms a protocol works
    before a device is saved.

Both are read-only against the machines involved: this only opens outbound
TCP connections and closes them immediately (or, for serial, only reads OS
port metadata) — nothing is written to any device, and this only ever
touches the local network this PC is on.

Requires nothing beyond what's already needed by the adapters:
pyserial for list_serial_ports (already required by modbus_rtu/serial_ascii
— see requirements-device-gateway.txt), and the standard library
(socket, ipaddress, concurrent.futures) for scan_network.
"""
import ipaddress
import socket
import concurrent.futures as _futures

# Ports worth probing, and the protocol they conventionally imply. This is
# a hint for the admin page's UI, not a guarantee - plenty of gear answers
# on 80 without being an http_poll target this app understands, and some
# Modbus servers listen on other ports entirely. It's meant to turn "here's
# a bare IP address" into "here's a labeled candidate," same as a Wi-Fi
# picker shows you a plausible network name before you've actually joined it.
_SCAN_PORTS = {
    502: "modbus_tcp",
    4840: "opcua",
    1883: "mqtt",
    80: "http_poll",
    443: "http_poll",
}

DEFAULT_SCAN_PORTS = tuple(_SCAN_PORTS)


def local_ip() -> str:
    """Best-effort LAN IP for this machine (not 127.0.0.1). Same no-
    dependency trick used by service_announcer.py: open a UDP socket
    'connected' to a public address without sending anything, purely so
    the OS reports which local interface/IP it would route through."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        s.close()


def guess_local_subnet() -> str:
    """A /24 CIDR built from this PC's own LAN IP, e.g. '192.168.0.0/24' -
    the sane default for the admin page's subnet field on the overwhelming
    majority of small plant networks (one flat /24 off one switch). Shown
    as an editable default, not forced - a bigger site with VLANs or a
    /23-and-up range should type in whatever range actually applies."""
    ip = local_ip()
    try:
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        return str(network)
    except ValueError:
        return "192.168.1.0/24"


def list_serial_ports() -> list:
    """Every COM/serial port this PC currently sees, via the OS - not a
    probe of what's plugged into each one, just device enumeration. Covers
    the modbus_rtu / serial_ascii side of "find devices": plug in a scale
    or a serial-to-RS485 dongle, hit refresh, see it appear.

    Returns a list of dicts:
        [{"port": "COM4", "description": "USB Serial Port (COM4)",
          "manufacturer": "FTDI", "hwid": "USB VID:PID=0403:6001 ..."}]

    Empty list (never raises) if pyserial isn't installed or nothing is
    plugged in - the caller shows "nothing found" either way, since there's
    no actionable difference for the person clicking the button.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    ports = []
    try:
        for p in list_ports.comports():
            ports.append({
                "port": p.device,
                "description": p.description or "",
                "manufacturer": getattr(p, "manufacturer", None) or "",
                "hwid": p.hwid or "",
            })
    except Exception:
        return []
    return sorted(ports, key=lambda r: r["port"])


def _probe_host(ip: str, ports, timeout_s: float) -> dict | None:
    open_ports = []
    for port in ports:
        try:
            with socket.create_connection((str(ip), port), timeout=timeout_s):
                open_ports.append(port)
        except Exception:
            continue
    if not open_ports:
        return None

    hostname = None
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except Exception:
        pass

    # Lead with whichever protocol's port was found first in _SCAN_PORTS'
    # declared order, so the common case (a lone 502 or 4840) gets a single
    # clean guess rather than an arbitrary one.
    guessed_protocol = next((_SCAN_PORTS[p] for p in _SCAN_PORTS if p in open_ports), None)

    return {
        "ip": str(ip),
        "hostname": hostname,
        "open_ports": open_ports,
        "guessed_protocol": guessed_protocol,
    }


def scan_network(subnet_cidr: str, ports=DEFAULT_SCAN_PORTS, timeout_s: float = 0.3,
                  max_workers: int = 100) -> list:
    """Sweeps every host address in subnet_cidr (e.g. '192.168.0.0/24')
    with a short outbound TCP connect attempt on each of `ports`, in
    parallel. Nothing is sent beyond the TCP handshake itself, and nothing
    is written anywhere - this only ever opens (and immediately closes)
    plain TCP connections on the local network this PC is already on, the
    same as opening the machine's own web UI in a browser would.

    Returns candidates only (hosts with at least one of `ports` open), each
    as {"ip", "hostname", "open_ports", "guessed_protocol"} - see
    _probe_host. A few hundred hosts at the default timeout typically
    finishes in a handful of seconds; a wider-than-/24 range will take
    proportionally longer since every extra host is another few sockets.

    Raises ValueError if subnet_cidr doesn't parse - the caller should
    show that back to the person rather than silently scanning nothing.
    """
    network = ipaddress.ip_network(subnet_cidr, strict=False)
    hosts = list(network.hosts())

    # A fat-fingered "10.0.0.0/8" would mean 16 million probes - refuse
    # rather than let the button hang the page for an hour.
    if len(hosts) > 4096:
        raise ValueError(
            f"{subnet_cidr} has {len(hosts):,} host addresses - that's too "
            f"wide to scan from here. Use a /20 or smaller (a /24, one "
            f"switch's worth of addresses, is the usual case)."
        )

    found = []
    with _futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_probe_host, ip, ports, timeout_s) for ip in hosts]
        for fut in _futures.as_completed(futures):
            result = fut.result()
            if result:
                found.append(result)

    found.sort(key=lambda r: tuple(int(part) for part in r["ip"].split(".")))
    return found
