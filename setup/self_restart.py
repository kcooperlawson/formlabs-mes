"""Restarts the app after a successful update, so new code actually takes
effect without someone having to notice the update finished and close and
reopen the launcher by hand.

The app is asked to stop; whatever STARTED it is what starts it again.

That matters because there are two ways to run this app and they are not
interchangeable. START_HERE.bat option 3 runs uvicorn against this PC's own
PostgreSQL. Portable mode (run_mes_portable.bat -> api/portable_launcher.py)
also runs the DATABASE inside that same process, out of pgdata\\. The 4.08
version of this file always relaunched plain uvicorn, which on a portable PC
killed the bundled database and brought the app back up with nothing behind
it. Nothing here builds a launch command any more:

  * a restart marker file is written (updates\\.restart-requested);
  * the server is asked to shut down the way Ctrl+C would, so portable mode
    runs its own "stop the database" path on the way out;
  * both launchers run their app inside a loop: when the app exits and that
    marker is there, they delete it and start the same thing again - the
    portable launcher restarts the database too, because that is what it
    does on every start.

A PC whose app was started some other way (a bare `uvicorn` in a terminal, a
developer's editor) has no loop watching it, so for that case only, a small
detached helper waits for this process to exit and starts the app again the
same way it is running now. A PC running under a service supervisor (nssm)
needs neither: the supervisor notices the exit and restarts it, which is why
the helper is skipped whenever a supervisor is present.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MARKER_NAME = ".restart-requested"
# If the polite shutdown hasn't taken hold by now, something is wedged
# (a request stuck in a long read, a thread refusing to end). Leave anyway:
# a portable database left running is recovered on the next start, while an
# app that never restarts leaves the PC on the old code with nobody watching.
HARD_EXIT_AFTER_S = 20.0


def marker_path(root: Path | str | None = None) -> Path:
    return Path(root or ROOT) / "updates" / MARKER_NAME


def launch_mode() -> str:
    """"portable" when api/portable_launcher.py started this process (it sets
    MES_LAUNCH_MODE itself), else "server"."""
    return os.getenv("MES_LAUNCH_MODE", "").strip().lower() or "server"


def supervised() -> bool:
    """True when a launcher loop (START_HERE.bat option 3, or
    run_mes_portable.bat) is waiting to start this app again, or a service
    supervisor is. Both set their own variable before launching."""
    return os.getenv("MES_SUPERVISED", "").strip() == "1" or bool(os.getenv("NSSM_SERVICE_NAME", "").strip())


def _relaunch_command(root: Path) -> list[str]:
    """Only for an app nothing is watching - start it the same way it is
    running now, not some other way."""
    python = root / "venv" / "Scripts" / "python.exe"
    python = python if python.is_file() else Path(sys.executable)
    if launch_mode() == "portable":
        return [str(python), "-m", "api.portable_launcher"]

    ssl_args = []
    cert, key = root / "certs" / "mes.crt", root / "certs" / "mes.key"
    if cert.exists() and key.exists():
        ssl_args = ["--ssl-certfile", str(cert), "--ssl-keyfile", str(key)]
    return [str(python), "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0",
            "--port", os.getenv("MES_PORT", "8000"), *ssl_args]


def _spawn_unsupervised_relaunch(root: Path) -> None:
    """Waits for THIS process to exit, then starts the app again. Waiting
    matters: the new process can't bind the port until the old one has let
    it go, and on a portable PC it can't start the database until the old
    one has stopped it."""
    python = root / "venv" / "Scripts" / "python.exe"
    python = python if python.is_file() else Path(sys.executable)
    helper = (
        "import subprocess, time\n"
        f"pid = {os.getpid()}\n"
        # psutil comes with pgserver, so it's there in portable mode; a PC on
        # its own PostgreSQL may not have it, and a fixed wait is fine there.
        "try:\n"
        "    import psutil\n"
        "    deadline = time.time() + 60\n"
        "    while time.time() < deadline and psutil.pid_exists(pid):\n"
        "        time.sleep(0.5)\n"
        "except ImportError:\n"
        "    time.sleep(10)\n"
        "time.sleep(2)\n"
        f"subprocess.Popen({_relaunch_command(root)!r}, cwd={str(root)!r},\n"
        "    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,\n"
        "    close_fds=True)\n"
    )
    subprocess.Popen(
        [str(python), "-c", helper],
        cwd=str(root),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def _ask_server_to_stop() -> None:
    """Ends the server the way Ctrl+C does, so uvicorn.run() RETURNS - which
    is what lets portable mode's own `finally` stop the bundled database
    before the process goes.

    SIGINT, not SIGTERM. On Windows, raising SIGTERM inside the process
    terminates it outright (exit code 3) without uvicorn's handler running at
    all - measured, not assumed - which would leave the portable database
    running behind a dead app. SIGINT is the one uvicorn treats as Ctrl+C on
    every platform. It is raised in THIS process only, so the launcher's
    command window is unaffected and its loop starts the app again.
    """
    try:
        signal.raise_signal(signal.SIGINT)
    except Exception:
        os._exit(0)


def _hard_exit_watchdog() -> None:
    os._exit(0)


def request_restart(root: Path | None = None, delay_seconds: float = 2.0) -> str:
    """Asks the app to restart, and returns how it will happen: "supervised"
    (a launcher loop will start it again), "relaunch" (nothing is watching,
    so a helper will), or "manual" (this platform can't, so somebody has to).

    Call this right before a request handler returns its response: the delay
    is what lets that response reach the browser before the server stops.
    """
    root = Path(root or ROOT)
    marker = marker_path(root)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{datetime.now():%Y-%m-%d %H:%M:%S} update applied\n", encoding="utf-8")
    except OSError:
        pass

    if os.name != "nt" and not supervised():
        # A developer running the API on their own machine never wants their
        # shell killed out from under them by a plant-PC feature.
        return "manual"

    mode = "supervised"
    if not supervised():
        mode = "relaunch"
        _spawn_unsupervised_relaunch(root)

    threading.Timer(delay_seconds, _ask_server_to_stop).start()
    threading.Timer(delay_seconds + HARD_EXIT_AFTER_S, _hard_exit_watchdog).start()
    return mode


# 4.08 called this schedule_restart() and returned a bool. Kept so an older
# caller still works during an update that replaces these files one at a time.
def schedule_restart(root: Path | None = None, delay_seconds: float = 3.0) -> bool:
    return request_restart(root, delay_seconds) != "manual"
