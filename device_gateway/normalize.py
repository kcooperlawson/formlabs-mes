"""
device_gateway/normalize.py - The canonical metric vocabulary.

Every adapter, no matter what protocol it speaks, ends up returning a dict
keyed by names from this list (that's what a DeviceTagMap row's
`canonical_metric` is chosen from in the admin UI). writer.py only ever
has to understand these names, not one raw tag naming scheme per vendor
per protocol — that's what makes "find, assign, and it just shows up in
analytics" possible regardless of what a given machine calls its own tags.

Add a new metric here when a device reports something genuinely new; don't
add a metric per device — these are supposed to be shared across every
machine of a given role.
"""

CANONICAL_METRICS = {
    # --- filling / pump stations ---
    "weight_g": "Instantaneous scale reading, grams",
    "net_weight_g": "Net pour weight of the most recent completed cycle, grams",
    "units_poured_delta": "Units poured since the last reading (a per-cycle pulse/counter)",
    "units_poured_total": "Lifetime/shift cycle counter as reported by the machine",
    "cycle_complete": "Boolean/pulse: a fill cycle just finished",
    "machine_state": "Free-text machine state, e.g. Pouring / Idle / Fault / Manual",
    "fault_code": "Free-text or numeric fault/alarm code",
    "resin_lot_number": "Lot number as entered/read at the machine",
    "scrap_count": "Rejected/scrapped unit counter",

    # --- label printers / packing ---
    "labels_printed_delta": "Labels printed since the last reading",
    "labels_printed_total": "Lifetime label counter",
    "print_fault": "Boolean/text: printer fault (out of ribbon, jam, ...)",

    # --- reactors / tanks ---
    "level_pct": "Tank/reactor fill level, percent",
    "temperature_c": "Temperature, Celsius",
}

# Which canonical metrics writer.py treats as "this should turn into a
# ProductionLog row" for a device with device_role == "filling_station".
# Keeping this list here (not hardcoded in writer.py) makes it obvious
# what triggers a write when someone's staring at the tag map wondering
# why nothing showed up in Analytics yet.
FILLING_STATION_TRIGGER_METRICS = ("units_poured_delta", "cycle_complete")
