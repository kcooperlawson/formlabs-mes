"""
adapters/serial_ascii.py - Plain-text serial devices: bench scales, mostly.

The ULINE H-1650 scales and the Mettler Toledo load-cell modules visible
in the cart photos are exactly this category — most bench/counting scales
speak a simple continuous or on-demand ASCII protocol over RS-232/USB-
serial (each vendor's exact framing differs, but it's always "a line of
text with a number and maybe a unit in it"), not an industrial fieldbus.
This adapter doesn't try to know every vendor's format up front; instead
each DeviceTagMap row supplies its own regex, so it adapts to whatever
that scale actually prints without new code.

connection_json:
    {
      "port": "COM4", "baud": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
      "read_timeout_s": 1.0,
      "request_command": null   // e.g. "P\r\n" for scales that only reply
                                 // when asked (a "print"/on-demand command);
                                 // leave null for scales that stream
                                 // continuously on their own.
    }

DeviceTagMap.raw_tag for this adapter is a regex with a named group
`value`, applied against each line as it's received, e.g.:
    weight, continuous stream "   118.045 g\r\n"   ->  r"(?P<value>[-\d.]+)\s*g"
    labeled protocol "ST,GS,+000118.045,g"          ->  r"GS,\+?(?P<value>[-\d.]+)"

If the scale only streams while actively weighing (like the negative
tare readouts in the photos — "-88.5", "-118.0"), that's fine: poll()
just returns whatever the most recent matching line was, which is exactly
"weight right now."

Requires: pyserial (see requirements-device-gateway.txt)
"""
import re
import threading
import time
from .base import DeviceAdapter


class SerialASCIIAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.serial = None
        self._latest: dict = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        # Set by the reader thread when the port itself fails (USB cable
        # pulled, adapter lost power). _read_raw raises it, so the gateway
        # reconnects and the device shows Error instead of repeating the
        # last weight it ever saw as if the scale were still there.
        self._port_error = None
        self._compiled = [
            (t["raw_tag"], re.compile(t["raw_tag"])) for t in self.tag_map
        ]

    def connect(self) -> None:
        import serial
        self.serial = serial.Serial(
            port=self.connection["port"],
            baudrate=int(self.connection.get("baud", 9600)),
            bytesize=int(self.connection.get("bytesize", 8)),
            parity=self.connection.get("parity", "N"),
            stopbits=int(self.connection.get("stopbits", 1)),
            timeout=float(self.connection.get("read_timeout_s", 1.0)),
        )
        if not self.connection.get("request_command"):
            self._stop.clear()
            self._thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._thread.start()

    def _reader_loop(self):
        import serial
        while not self._stop.is_set():
            try:
                line = self.serial.readline().decode(errors="ignore").strip()
            except (serial.SerialException, OSError) as exc:
                if not self._stop.is_set():
                    self._port_error = exc
                return
            except Exception:
                time.sleep(0.5)
                continue
            if not line:
                continue
            self._apply_line(line)

    def _apply_line(self, line: str):
        with self._lock:
            for raw_tag, pattern in self._compiled:
                match = pattern.search(line)
                if match:
                    try:
                        self._latest[raw_tag] = match.group("value")
                    except IndexError:
                        # Regex without a named `value` group — fall back
                        # to the whole match so it's obvious in Test
                        # Connection output that the pattern needs fixing.
                        self._latest[raw_tag] = match.group(0)

    def _read_raw(self) -> dict:
        if self._port_error is not None:
            raise ConnectionError(
                f"Serial: lost {self.connection.get('port')} ({self._port_error}) - "
                f"is the cable or USB adapter still plugged in?")
        request_command = self.connection.get("request_command")
        if request_command:
            self.serial.reset_input_buffer()
            self.serial.write(request_command.encode())
            line = self.serial.readline().decode(errors="ignore").strip()
            if line:
                self._apply_line(line)
        with self._lock:
            return dict(self._latest)

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self.serial:
            self.serial.close()
