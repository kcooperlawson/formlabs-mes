"""
service_discovery.py - Finds the MES database announced by
service_announcer.py on the local network, so run_gateway.py can be
pointed at it without anyone typing an IP address into that machine's
.env - the same .env file works unmodified whether it's sitting on the
PC that hosts Postgres or on a gateway-only PC three rooms away.

Only the host/port/database name travel over the network. Credentials
never do - run_gateway.py combines whatever this function finds with
username/password already present in THIS machine's own .env.

Requires the 'zeroconf' package (see requirements.txt).
"""
import time

SERVICE_TYPE = "_formlabsmes._tcp.local."


class _Listener:
    def __init__(self):
        self.found = []

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            self.found.append(info)

    def update_service(self, zc, type_, name):
        pass

    def remove_service(self, zc, type_, name):
        pass


def _parse(info):
    addresses = info.parsed_addresses()
    if not addresses:
        return None
    props = {}
    for k, v in (info.properties or {}).items():
        try:
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            props[key] = val
        except Exception:
            continue
    return {
        "host": addresses[0],
        "port": info.port,
        "dbname": props.get("dbname", ""),
        "plant": props.get("plant", ""),
    }


def discover(timeout_s: float = 5.0, settle_s: float = 1.0):
    """Listens for formlabsmes database announcements on the local network
    and returns a list of dicts:

        [{"host": "192.168.0.13", "port": 5432, "dbname": "formlabs_mes",
          "plant": "DESKTOP-ABC123"}, ...]

    Returns as soon as something is found and stays quiet for settle_s
    seconds (so a launch on a healthy network is fast - typically well
    under a second, not a fixed multi-second wait every time) - but never
    waits past timeout_s total even if nothing ever answers. Empty list if
    none are found in time - either nothing is announcing right now, or
    this network doesn't pass mDNS/multicast traffic between these two
    machines (different VLAN, managed switch with client isolation, etc).
    """
    from zeroconf import Zeroconf, ServiceBrowser

    zc = Zeroconf()
    listener = _Listener()
    ServiceBrowser(zc, SERVICE_TYPE, listener)

    try:
        deadline = time.monotonic() + timeout_s
        last_count = 0
        stable_since = None
        while time.monotonic() < deadline:
            time.sleep(0.1)
            count = len(listener.found)
            if count > last_count:
                last_count = count
                stable_since = time.monotonic()
            elif count > 0 and stable_since is not None and (time.monotonic() - stable_since) >= settle_s:
                break
    finally:
        zc.close()

    results = []
    seen_names = set()
    for info in listener.found:
        parsed = _parse(info)
        if parsed and info.name not in seen_names:
            seen_names.add(info.name)
            results.append(parsed)
    return results
