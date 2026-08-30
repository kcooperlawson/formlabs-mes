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
"""
import os
import sys
import time
import threading
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app_logger import logger
from db_core import ScopedSession
from device_models import Device, DeviceTagMap

from .registry import build_adapter_from_device
from .writer import ReadingWriter

RESCAN_INTERVAL_S = 10
MAX_BACKOFF_S = 60


class DeviceWorker(threading.Thread):
    def __init__(self, device_id: int, writer: ReadingWriter):
        super().__init__(daemon=True, name=f"device-{device_id}")
        self.device_id = device_id
        self.writer = writer
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        backoff = 1
        while not self._stop.is_set():
            device, tag_rows = self._load()
            if device is None or not device.is_enabled:
                return

            adapter = None
            try:
                adapter = build_adapter_from_device(device, tag_rows)
                adapter.connect()
                self._set_status(device.id, "Online", None)
                backoff = 1

                while not self._stop.is_set():
                    live_device, _ = self._load()
                    if live_device is None or not live_device.is_enabled:
                        return

                    mapped = adapter.poll()
                    self.writer.apply(live_device, mapped)
                    self._set_status(live_device.id, "Online", None)
                    self._stop.wait(live_device.poll_interval_s or 5.0)
                return
            except Exception as exc:
                logger.exception(f"[device_gateway] {device.device_name}: adapter error")
                self._set_status(device.id, "Error", str(exc))
            finally:
                if adapter is not None:
                    try:
                        adapter.close()
                    except Exception:
                        pass

            if self._stop.is_set():
                return
            self._stop.wait(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

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
    def _set_status(device_id: int, status: str, error: str | None):
        session = ScopedSession()
        try:
            device = session.get(Device, device_id)
            if device:
                device.status = status
                device.last_error = error
                if status == "Online":
                    device.last_seen_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()


def run_forever():
    logger.info("[device_gateway] gateway service starting")
    writer = ReadingWriter()
    workers: dict[int, DeviceWorker] = {}

    try:
        while True:
            session = ScopedSession()
            try:
                enabled_ids = [row[0] for row in
                               session.query(Device.id).filter(Device.is_enabled.is_(True)).all()]
            finally:
                session.close()

            for device_id in enabled_ids:
                worker = workers.get(device_id)
                if worker is None or not worker.is_alive():
                    worker = DeviceWorker(device_id, writer)
                    worker.start()
                    workers[device_id] = worker

            for device_id in list(workers):
                if device_id not in enabled_ids:
                    workers.pop(device_id).stop()

            time.sleep(RESCAN_INTERVAL_S)
    except KeyboardInterrupt:
        logger.info("[device_gateway] stopping")
        for worker in workers.values():
            worker.stop()
