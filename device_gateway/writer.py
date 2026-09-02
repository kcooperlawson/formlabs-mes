"""
device_gateway/writer.py - Turns a normalized reading into MES history.

Deliberately does NOT write ProductionLog/AssignedRun rows with raw SQL.
Instead it calls straight into crud.py's own add_hourly_log() /
add_downtime_log() — the exact functions Operator_Form.py calls when a
human types a count in by hand. That means:

  * Every business rule already encoded there (AssignedRun progress,
    marking a run "Done" at target, FK resolution against
    users/pump_stations/resin_specs) applies to gateway-sourced data too,
    automatically, with zero duplication.
  * Analytics_Hub, Manager_Cockpit, Live_Reactors, Tv_Dashboard — none of
    them need to change. They already read ProductionLog/AssignedRun; they
    have no way to tell whether a row came from a keyboard or a machine.
  * If that business logic changes later, the gateway doesn't drift out of
    sync with it.

Every reading is also written to DeviceReading regardless of role or
metric, as a raw audit trail (see device_models.py) — useful for
machine-level telemetry (fault codes, uptime) that isn't meant to become a
production count.
"""
import os
import sys
from datetime import datetime, date

# device_gateway/ lives at the repo root alongside crud.py/models.py/etc.
# Make sure that root is on sys.path regardless of the working directory
# the gateway process happens to be started from.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app_logger import logger
from db_core import ScopedSession
from models import PumpStation, Reactor, ResinSpec
from device_models import DeviceReading

from .normalize import FILLING_STATION_TRIGGER_METRICS

GATEWAY_OPERATOR_NAME = "Automated Gateway"


def _current_shift() -> str:
    """Which shift a machine-sourced reading belongs to.

    Delegates to shifts.current_shift so a gateway row lands in exactly the
    same bucket a human's entry would. This used to carry its own list of
    three shifts and pick by sorting the start times, which had two faults:
    it offered a shift this plant does not run, and sorting cannot answer
    01:30 - that is earlier than every start time, so the naive result was
    the last entry by luck rather than by reasoning about the wrap-around.

    Falls back to "Shift 1" if settings cannot be read, matching
    ProductionLog.shift's own column default.
    """
    try:
        from crud import get_plant_settings
        from shifts import current_shift
        return current_shift(get_plant_settings())
    except Exception:
        return "Shift 1"


class ReadingWriter:
    """One instance per gateway process (see service.py) — it holds the
    small bit of state needed to turn a lifetime counter into a per-poll
    delta for devices that only report `units_poured_total` rather than a
    ready-made `units_poured_delta`."""

    def __init__(self):
        self._last_total: dict = {}

    def resolve_units_delta(self, device_id: int, mapped: dict):
        if "units_poured_delta" in mapped:
            delta = mapped["units_poured_delta"]
            return int(delta) if delta else 0
        if "cycle_complete" in mapped and mapped["cycle_complete"]:
            return 1
        if "units_poured_total" in mapped:
            total = int(mapped["units_poured_total"])
            previous = self._last_total.get(device_id)
            self._last_total[device_id] = total
            if previous is None:
                return 0  # first reading after startup: establish baseline, log nothing yet
            return max(0, total - previous)
        return 0

    def apply(self, device, mapped: dict):
        """device: a device_models.Device row. mapped: canonical metric ->
        value, already scaled/typed by the adapter (see adapters/base.py)."""
        if not mapped:
            return

        session = ScopedSession()
        try:
            now = datetime.utcnow()
            for metric, value in mapped.items():
                session.add(DeviceReading(
                    device_id=device.id,
                    timestamp=now,
                    metric=metric,
                    value_numeric=value if isinstance(value, (int, float)) else None,
                    value_text=None if isinstance(value, (int, float)) else str(value),
                ))
            session.commit()
        finally:
            session.close()

        if device.device_role == "filling_station" and any(m in mapped for m in FILLING_STATION_TRIGGER_METRICS) \
                or "units_poured_total" in mapped:
            self._log_filling_cycle(device, mapped)

    def _log_filling_cycle(self, device, mapped: dict):
        delta = self.resolve_units_delta(device.id, mapped)
        if delta <= 0:
            return

        from crud import add_hourly_log  # local import: keep crud.py's own imports out of module load time

        session = ScopedSession()
        try:
            pump = session.get(PumpStation, device.pump_station_id) if device.pump_station_id else None
            reactor = None
            if device.reactor_id:
                reactor = session.get(Reactor, device.reactor_id)
            elif device.pump_station_id:
                reactor = session.query(Reactor).filter(Reactor.assigned_pump_id == device.pump_station_id).first()

            pump_station_name = pump.station_name if pump else device.device_name
            resin_spec = session.get(ResinSpec, reactor.current_resin_id) if (reactor and reactor.current_resin_id) else None
            resin_type = (reactor.current_resin if reactor else None) or ""
            cartridge_type = resin_spec.cartridge_type if resin_spec else "V2"
            lot_number = str(mapped.get("resin_lot_number") or "")
        finally:
            session.close()

        try:
            add_hourly_log(
                operator_name=GATEWAY_OPERATOR_NAME,
                pump_station=pump_station_name,
                shift=_current_shift(),
                cartridge_type=cartridge_type,
                resin_type=resin_type,
                lot_number=lot_number,
                bottles=delta,
                scrap_empty=0,
                scrap_filled=int(mapped.get("scrap_count") or 0),
                notes=f"Auto-logged by Device Gateway ({device.device_name})",
                log_type="Hourly Bottle Count",
            )
            logger.info(f"[device_gateway] {device.device_name}: logged {delta} unit(s) to {pump_station_name!r}")
        except Exception:
            logger.exception(f"[device_gateway] {device.device_name}: add_hourly_log failed")
