"""
service_announcer.py - Advertises this machine's MES database on the local
network via mDNS (the same zero-config protocol Bonjour/Chromecast/network
printers use), so a Device Gateway running on a different floor PC can find
it automatically instead of someone typing an IP address into a .env file
by hand every time the app moves to a new machine.

Broadcasts ONLY host, port, and database name - NEVER the password. Every
gateway machine keeps its own DB_USER/DB_PASSWORD locally in its own .env
(see service_discovery.py); only the "where is it" part ever travels over
the network.

Started once, automatically, from Home.py at startup (wrapped in
@st.cache_resource there so it survives Streamlit's rerun-the-script-on-
every-click model without re-registering). Safe to import and call
start_announcing() more than once in the same process regardless - the
module-level guard below makes every call after the first a no-op.

Requires the 'zeroconf' package (see requirements.txt). If it isn't
installed, this logs a warning and does nothing rather than crashing the
app - gateways on other machines just fall back to a manually-set DB_URL
in that case.
"""
import os
import socket
import atexit

from app_logger import logger

SERVICE_TYPE = "_formlabsmes._tcp.local."

_zeroconf = None
_service_info = None


def _local_ip() -> str:
    """Best-effort LAN IP for this machine (not 127.0.0.1). Opens a UDP
    socket 'connected' to a public address without actually sending
    anything, purely so the OS tells us which local interface/IP it would
    route through - the standard no-dependency trick for this."""
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


def start_announcing():
    global _zeroconf, _service_info
    if _zeroconf is not None:
        return  # already announcing in this process

    db_url = os.getenv("DB_URL")
    if not db_url:
        logger.warning("[service_announcer] DB_URL not set - nothing to announce")
        return

    try:
        from zeroconf import Zeroconf, ServiceInfo
        from sqlalchemy.engine import make_url
    except ImportError:
        logger.warning(
            "[service_announcer] 'zeroconf' package not installed - gateways on "
            "other PCs will need a manual DB_URL in their .env instead of "
            "auto-discovery. Run: pip install zeroconf"
        )
        return

    try:
        url = make_url(db_url)
        ip = _local_ip()
        hostname = socket.gethostname()
        # mDNS instance names have to be unique on the network and are
        # conventionally "<something>.<service type>" - the hostname makes
        # each plant PC's announcement distinguishable if more than one
        # ever ends up on the same network.
        instance_name = f"{hostname}-formlabsmes.{SERVICE_TYPE}"

        props = {
            "dbname": (url.database or ""),
            "plant": hostname,
        }

        info = ServiceInfo(
            SERVICE_TYPE,
            instance_name,
            addresses=[socket.inet_aton(ip)],
            port=url.port or 5432,
            properties=props,
            server=f"{hostname}.local.",
        )

        zc = Zeroconf()
        zc.register_service(info)
        _zeroconf = zc
        _service_info = info

        logger.info(
            f"[service_announcer] announcing formlabsmes database at {ip}:{info.port} "
            f"(db={url.database!r}, host={hostname!r}) as {instance_name!r}"
        )
        atexit.register(_stop_announcing)
    except Exception:
        logger.exception("[service_announcer] failed to start mDNS announcement")


def _stop_announcing():
    global _zeroconf, _service_info
    if _zeroconf is not None:
        try:
            _zeroconf.unregister_service(_service_info)
            _zeroconf.close()
        except Exception:
            pass
        _zeroconf = None
        _service_info = None
