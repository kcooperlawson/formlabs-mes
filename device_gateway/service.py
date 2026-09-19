"""
device_gateway/service.py - The background poller.

One thread per enabled Device, each running its own connect -> poll loop
at that device's own poll_interval_s, writing through ReadingWriter (see
writer.py). The outer run_forever() loop re-checks the `devices` table
every RESCAN_INTERVAL_S seconds and starts a worker for anything newly
enabled — so adding a device on the Device Registry admin page takes
effect within a few seconds, no restart needed. A worker also notices for
itself when its own device gets disabled or deleted, and exits.

A device whose adapter throws (unreachable host, wrong COM port, bad
credentials) doesn't take the rest of the gateway down with it — that
device's worker logs the error, marks the device Error/last_error in the
DB (so it shows up on the admin page), and retries with exponential
backoff up to MAX_BACKOFF_S.

Losing the DATABASE doesn't take the gateway down either. The gateway PC and
the MES PC are two machines with a network between them, and that network
will drop for a few seconds now and then - a switch reboot, a firewall
failover, the MES PC restarting. The rescan loop used to have no error
handling at all, so the first failed query ended the process for good and
nothing was read again until somebody noticed and restarted it by hand. Now
every loop here treats a database error as an outage to wait out: it logs
once (and a reminder every minute), retries every DB_RETRY_S seconds, and
carries on exactly where it was the moment the database answers again.
Machines that report a running total (units_poured_total) lose nothing over
an outage - the first reading afterwards is compared with the last one that
was saved.

Two more things run alongside the device workers:
  * a heartbeat into gateway_nodes every RESCAN_INTERVAL_S, which is how the
    Device Registry can tell a stopped gateway from a quiet one;
  * JobRunner, which picks up Find Devices / Test Connection requests the
    admin page addressed to THIS PC and runs them here, next to the hardware.
"""
import os
import socket
import sys
import threading
import time
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy.exc import SQLAlchemyError

import device_crud
from app_logger import logger
from db_core import ScopedSession
from device_models import Device, DeviceTagMap

from .discovery import local_ip
from .jobs import run_job
from .registry import build_adapter_from_device
from .writer import ReadingWriter

RESCAN_INTERVAL_S = 10
MAX_BACKOFF_S = 60
DB_RETRY_S = 5
JOB_POLL_INTERVAL_S = 2
# A device that connects but returns nothing for this long gets reconnected -
# the session underneath may be dead in a way the protocol library hides.
NO_DATA_RECONNECT_S = 60


def _app_version() -> str:
    try:
        with open(os.path.join(_REPO_ROOT, "VERSION"), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _is_database_error(exc: BaseException) -> bool:
    return isinstance(exc, SQLAlchemyError)


def _short(exc: BaseException) -> str:
    detail = getattr(exc, "orig", None) or exc
    text = str(detail).strip().splitlines()
    return (text[0] if text else type(exc).__name__)[:200]


class _DatabaseOutage:
    """One place that knows whether the database is currently unreachable, so
    fifty device threads failing at once log one line, not fifty."""
    REMIND_EVERY_S = 60

    def __init__(self):
        self._lock = threading.Lock()
        self._since = None
        self._last_log = 0.0

    def failed(self, exc: BaseException):
        with self._lock:
            now = time.monotonic()
            if self._since is None:
                self._since = self._last_log = now
                logger.warning(f"[device_gateway] can't reach the MES database ({_short(exc)}). "
                               f"The gateway keeps running and retries every {DB_RETRY_S} s.")
            elif now - self._last_log >= self.REMIND_EVERY_S:
                self._last_log = now
                logger.warning(f"[device_gateway] still can't reach the MES database after "
                               f"{now - self._since:.0f} s ({_short(exc)}) - still retrying.")

    def recovered(self):
        with self._lock:
            if self._since is not None:
                logger.info(f"[device_gateway] MES database reachable again after "
                            f"{time.monotonic() - self._since:.0f} s - carrying on.")
                self._since = None


DB_OUTAGE = _DatabaseOutage()


class _NoDataTooLong(Exception):
    pass


class DeviceWorker(threading.Thread):
    def __init__(self, device_id: int, writer: ReadingWriter):
        super().__init__(daemon=True, name=f"device-{device_id}")
        self.device_id = device_id
        self.writer = writer
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        backoff = 1
        while not self._stop_event.is_set():
            adapter = None
            wait = backoff
            label = f"device {self.device_id}"
            try:
                device, tag_rows = self._load()
                if device is None or not device.is_enabled:
                    return
                label = device.device_name

                adapter = build_adapter_from_device(device, tag_rows)
                adapter.connect()
                empty_since = None

                while not self._stop_event.is_set():
                    live_device, live_tags = self._load()
                    if live_device is None or not live_device.is_enabled:
                        return

                    mapped = adapter.poll()
                    if mapped:
                        self.writer.apply(live_device, mapped)
                        self._set_status(live_device.id, "Online", None, seen=True)
                        DB_OUTAGE.recovered()
                        empty_since, backoff = None, 1
                    else:
                        # Connected, but nothing came back. This used to be
                        # written as Online (and "last seen just now") on
                        # every poll, which is how a PLC that dropped off the
                        # network stayed green on the admin page.
                        empty_since = empty_since or time.monotonic()
                        silent_s = time.monotonic() - empty_since
                        if not live_tags:
                            message = "Connected, but no tags are mapped yet - add them under Tag Map."
                        else:
                            message = (f"Connected, but none of its {len(live_tags)} mapped tag(s) "
                                       f"returned a value for {silent_s:.0f} s.")
                        self._set_status(live_device.id, "No data", message)
                        if live_tags and silent_s >= NO_DATA_RECONNECT_S:
                            raise _NoDataTooLong(message + " Reconnecting.")
                    self._stop_event.wait(live_device.poll_interval_s or 5.0)
                return
            except Exception as exc:
                if _is_database_error(exc):
                    # Not this device's fault, and there's nowhere to write
                    # an Error to anyway. Wait the outage out.
                    DB_OUTAGE.failed(exc)
                    wait = DB_RETRY_S
                else:
                    logger.warning(f"[device_gateway] {label}: {_short(exc)}")
                    self._set_status(self.device_id, "Error", str(exc)[:1000])
                    backoff = min(backoff * 2, MAX_BACKOFF_S)
            finally:
                if adapter is not None:
                    try:
                        adapter.close()
                    except Exception:
                        pass

            if self._stop_event.is_set():
                return
            self._stop_event.wait(wait)

    def _load(self):
        session = ScopedSession()
        try:
            device = session.get(Device, self.device_id)
            if device is None:
                return None, []
            tag_rows = session.query(DeviceTagMap).filter(DeviceTagMap.device_id == device.id).all()
            # Force these onto the instance before the session closes, so
            # the caller can use them safely after ScopedSession() is torn
            # down (avoids a DetachedInstanceError on later attribute
            # access from a different thread's session).
            _ = (device.id, device.device_name, device.device_role, device.protocol,
                 device.connection_json, device.poll_interval_s, device.is_enabled,
                 device.pump_station_id, device.reactor_id)
            for t in tag_rows:
                _ = (t.raw_tag, t.canonical_metric, t.data_type, t.scale_factor)
            return device, tag_rows
        finally:
            session.close()

    @staticmethod
    def _set_status(device_id: int, status: str, error: str | None, seen: bool = False):
        """Never raises. If the database is down the status can't be written,
        and the next _load() will notice the outage anyway."""
        session = ScopedSession()
        try:
            device = session.get(Device, device_id)
            if device:
                device.status = status
                device.last_error = error
                if seen:
                    # The database's clock, not this PC's: the MES side
                    # compares this with its own "now" to decide whether
                    # the device has gone quiet.
                    device.last_seen_at = device_crud.db_utc_now()
                session.commit()
        except Exception as exc:
            session.rollback()
            if _is_database_error(exc):
                DB_OUTAGE.failed(exc)
        finally:
            session.close()


class JobRunner(threading.Thread):
    """Runs Find Devices / Test Connection requests addressed to this PC."""

    def __init__(self, hostname: str):
        super().__init__(daemon=True, name="gateway-jobs")
        self.hostname = hostname
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        from gateway_crypto import KeyMismatchError

        while not self._stop_event.is_set():
            wait = JOB_POLL_INTERVAL_S
            try:
                job = device_crud.claim_next_gateway_job(self.hostname)
                if job is not None:
                    wait = 0
                    logger.info(f"[device_gateway] running {job['kind']} for the Device Registry (job {job['id']})")
                    try:
                        params = device_crud.decode_gateway_job_params(job)
                        result = run_job(job["kind"], params)
                        device_crud.finish_gateway_job(job["id"], result=result)
                    except KeyMismatchError as exc:
                        device_crud.finish_gateway_job(job["id"], error=str(exc))
                    except Exception as exc:
                        if _is_database_error(exc):
                            raise
                        device_crud.finish_gateway_job(job["id"], error=_short(exc))
            except Exception as exc:
                if _is_database_error(exc):
                    DB_OUTAGE.failed(exc)
                    wait = DB_RETRY_S
                else:
                    logger.exception("[device_gateway] job runner error")
            self._stop_event.wait(wait)


def _warn_about_unreadable_devices():
    """Say once, at start-up, if this PC's encryption key can't open the saved
    devices - rather than leaving it to be discovered one Error at a time."""
    from gateway_crypto import KeyMismatchError, decrypt_connection_strict

    session = ScopedSession()
    try:
        rows = session.query(Device.device_name, Device.connection_json).filter(Device.is_enabled.is_(True)).all()
    finally:
        session.close()
    unreadable = []
    for name, stored in rows:
        try:
            decrypt_connection_strict(stored)
        except KeyMismatchError as exc:
            unreadable.append((name, str(exc)))
    if unreadable:
        logger.error(f"[device_gateway] {len(unreadable)} device(s) can't be read on this PC "
                     f"({', '.join(n for n, _ in unreadable[:5])}): {unreadable[0][1]}")


def run_forever():
    hostname = socket.gethostname()
    started_at = datetime.utcnow()
    version = _app_version()
    logger.info(f"[device_gateway] gateway service starting on {hostname} ({local_ip()}), version {version or '?'}")
    writer = ReadingWriter()
    workers: dict[int, DeviceWorker] = {}
    jobs = JobRunner(hostname)
    jobs.start()
    checked_keys = False

    try:
        while True:
            wait = RESCAN_INTERVAL_S
            try:
                device_crud.record_gateway_heartbeat(hostname, local_ip(), version, started_at)
                session = ScopedSession()
                try:
                    enabled_ids = [row[0] for row in
                                   session.query(Device.id).filter(Device.is_enabled.is_(True)).all()]
                finally:
                    session.close()
                DB_OUTAGE.recovered()

                if not checked_keys:
                    checked_keys = True
                    _warn_about_unreadable_devices()

                for device_id in enabled_ids:
                    worker = workers.get(device_id)
                    if worker is None or not worker.is_alive():
                        worker = DeviceWorker(device_id, writer)
                        worker.start()
                        workers[device_id] = worker

                for device_id in list(workers):
                    if device_id not in enabled_ids:
                        workers.pop(device_id).stop()
            except Exception as exc:
                if _is_database_error(exc):
                    DB_OUTAGE.failed(exc)
                    wait = DB_RETRY_S
                else:
                    logger.exception("[device_gateway] rescan failed - retrying")

            time.sleep(wait)
    except KeyboardInterrupt:
        logger.info("[device_gateway] stopping")
        jobs.stop()
        for worker in workers.values():
            worker.stop()
