"""
adapters/simulator.py - No real hardware: generates a plausible, repeating
fill cycle on a timer, so the Device Gateway can be tried out, demoed, or
used to train someone on Analytics / the TV Dashboard / SCADA without a
single wire connected to anything. Registered exactly like a real protocol
(see registry.py) — the gateway service, writer.py, and the admin UI don't
know or care that this one is faking it.

connection_json:
    {
      "sim_profile": "pump",       // "pump" (filling station) or "scale"
      "cycle_seconds": 8,          // how long one fill cycle takes
      "target_weight_g": 850,      // where the fill weight settles
      "noise_pct": 1.5,            // random jitter, roughly +/- this % of target
      "fault_rate_pct": 0          // pump only: % chance a given cycle faults
    }
All fields are optional — an empty {} falls back to the defaults above.

Raw tags are already canonical-metric names (weight_g, units_poured_delta,
machine_state, fault_code — see normalize.py), on purpose: a demo device
needs zero vendor-tag research. device_crud.create_device() auto-fills the
tag map for a simulator device for exactly this reason, but mapping
weight_g -> weight_g by hand in the tag editor works identically.

Time-based, not step-based: every poll samples wherever
(time.time() - connect-time) lands in the cycle, so behavior is the same
whether this gets polled every 1s or every 30s, and several simulated
devices started at different moments don't move in lockstep.

Needs nothing beyond the Python standard library — unlike every other
adapter here, there's no real protocol underneath it to install a client
library for.
"""
import random
import time

from .base import DeviceAdapter


class SimulatorAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.profile = str(self.connection.get("sim_profile") or "pump").lower()
        self.cycle_s = float(self.connection.get("cycle_seconds") or 8) or 8.0
        self.target_g = float(self.connection.get("target_weight_g") or 850) or 850.0
        self.noise_pct = float(self.connection.get("noise_pct") or 0)
        self.fault_rate = float(self.connection.get("fault_rate_pct") or 0) / 100.0
        self._rng = random.Random()
        self._start = time.time()
        self._cycles_seen = 0

    def connect(self) -> None:
        # Restart the cycle from the top on every (re)connect - including
        # Test Connection's one-shot preview - rather than free-running from
        # whenever the adapter object happened to be constructed.
        self._start = time.time()
        self._cycles_seen = 0

    def close(self) -> None:
        pass  # nothing real to release

    def _weight_curve(self, phase: float) -> float:
        """phase in [0, 1) across one cycle: ramps up over the first 60%
        (pouring), holds near target for the next 25% (settling), drops
        back toward 0 for the rest (bottle swapped out). A recognisable
        fill/settle/empty shape, not a real physical model."""
        if phase < 0.6:
            level = self.target_g * (phase / 0.6)
        elif phase < 0.85:
            level = self.target_g
        else:
            level = self.target_g * max(0.0, 1 - (phase - 0.85) / 0.15)
        noise = self._rng.gauss(0, self.target_g * self.noise_pct / 100.0) if self.noise_pct else 0.0
        return max(0.0, level + noise)

    def _read_raw(self) -> dict:
        elapsed = time.time() - self._start
        cycle_index = int(elapsed // self.cycle_s)
        phase = (elapsed % self.cycle_s) / self.cycle_s

        raw = {"weight_g": round(self._weight_curve(phase), 1)}
        if self.profile == "scale":
            return raw

        # Pump profile also reports the cycle counter and a coarse machine
        # state - counting elapsed cycles (not just "did a boundary just
        # happen") means a slow poll interval still reports every cycle
        # that occurred in between, instead of silently losing them.
        delta = max(0, cycle_index - self._cycles_seen)
        self._cycles_seen = cycle_index
        raw["units_poured_delta"] = delta
        raw["machine_state"] = "Pouring" if phase < 0.85 else "Idle"
        raw["fault_code"] = "SIM-FAULT" if (delta and self.fault_rate and self._rng.random() < self.fault_rate) else ""
        return raw
