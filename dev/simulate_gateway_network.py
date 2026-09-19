"""Simulate a floor-PC Device Gateway on a flaky network, and check it copes.

    venv\\Scripts\\python.exe dev\\simulate_gateway_network.py
    venv\\Scripts\\python.exe dev\\simulate_gateway_network.py --with-mdns

Everything happens on this one PC, and none of it touches the real project
folder, its .env, its logs, or the database the app runs on:

  "MES PC"    a copy of the app in a temp folder, on a scratch database. This
              script registers devices through the real API and reads
              /api/devices exactly as the Device Registry page does.
  "Floor PC"  a second copy with its own .env, running the real
              run_gateway.py as a separate process.
  Fake PLC    a small Modbus TCP server: a pour counter that goes up every
              3 s, and a fill weight around 850 g.
  Two cables  fault-injecting TCP proxies between the gateway and the
              database, and between the gateway and the PLC, that can be
              unplugged (connections reset) or stalled (bytes swallowed,
              nothing ever answers).

It then pulls those cables, restarts things, breaks the configuration in the
ways a real floor PC gets broken, and checks what the gateway does and what
the Device Registry says about it. Takes about ten minutes, because it waits
out real timeouts and retries.

What it can't reproduce: a corporate firewall, VLANs, or multicast being
blocked between subnets. For those, run `run_gateway.py --check` on the real
floor PC (START_HERE.bat, option 12).

--with-mdns adds one phase that announces the scratch database over mDNS for
about 30 seconds. That announcement goes out on the real LAN, so it is off by
default.
"""
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PY = str(PROJECT / "venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
SIM_DB = "formlabs_gateway_sim"
PLC_PORT, PLC_LINK_PORT, DB_LINK_PORT = 15020, 15502, 15432
UNROUTABLE = "192.0.2.1"  # RFC 5737 TEST-NET-1: guaranteed to lead nowhere

WORK = Path(tempfile.mkdtemp(prefix="gateway_sim_"))
MES, FLOOR, OUT = WORK / "mes_pc", WORK / "floor_pc", WORK / "out"
T0 = time.time()
FAILS, CHECKS = [], 0


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


def check(cond, label):
    global CHECKS
    CHECKS += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {label}", flush=True)
    if not cond:
        FAILS.append(label)


# ---------------------------------------------------------------------------
# the two PCs
# ---------------------------------------------------------------------------
IGNORE = shutil.ignore_patterns(
    "venv", "frontend", "pgdata", "dist", ".git", "wheels", "backups", "resin_backups", "docs", "logs",
    "uploads", "updates", "rollback", "__pycache__", "node_modules", "combined_code.txt", ".env",
    "tests", "dev", "*.pdf", "*.zip")


def build_copies():
    for d in (MES, FLOOR):
        shutil.copytree(PROJECT, d, ignore=IGNORE)
    OUT.mkdir()


def production_credentials():
    from sqlalchemy.engine import make_url
    for line in (PROJECT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DB_URL="):
            url = make_url(line.split("=", 1)[1].strip().strip("'\""))
            return url.username, url.password, url.database
    raise SystemExit("No DB_URL in .env - nothing to take a login from.")


def write_env(folder: Path, **kv):
    (folder / ".env").write_text("".join(f"{k}={v}\n" for k, v in kv.items() if v is not None), encoding="utf-8")


# ---------------------------------------------------------------------------
# fake PLC: Modbus TCP, function codes 3 and 4 only
# ---------------------------------------------------------------------------
class FakePLC:
    def __init__(self, port):
        self.registers = [0] * 16
        self.start = time.time()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(16)
        threading.Thread(target=self._tick, daemon=True).start()
        threading.Thread(target=self._accept, daemon=True).start()

    def _tick(self):
        while True:
            elapsed = time.time() - self.start
            self.registers[0] = int(elapsed // 3) & 0xFFFF
            weight = 850.0 + 6.0 * ((elapsed % 3) / 3 - 0.5)
            self.registers[1], self.registers[2] = struct.unpack(">HH", struct.pack(">f", weight))
            time.sleep(0.25)

    def _accept(self):
        while True:
            conn, _ = self.sock.accept()
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    @staticmethod
    def _recvall(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError
            buf += chunk
        return buf

    def _serve(self, conn):
        try:
            while True:
                tid, _pid, length, unit = struct.unpack(">HHHB", self._recvall(conn, 7))
                pdu = self._recvall(conn, length - 1)
                fc = pdu[0]
                if fc in (3, 4):
                    start, count = struct.unpack(">HH", pdu[1:5])
                    values = self.registers[start:start + count]
                    body = (bytes([fc | 0x80, 2]) if len(values) < count
                            else bytes([fc, 2 * count]) + b"".join(struct.pack(">H", v) for v in values))
                else:
                    body = bytes([fc | 0x80, 1])
                conn.sendall(struct.pack(">HHHB", tid, 0, len(body) + 1, unit) + body)
        except Exception:
            pass
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# a network cable you can pull
# ---------------------------------------------------------------------------
def _reset(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


class Link:
    """up: forwards. down: port closed and every connection reset (a host
    that's off, a firewall that rejects). stall: connections accepted, bytes
    swallowed, nothing ever answers - the worst kind of silent drop, since not
    even a TCP error ever reaches the client."""

    def __init__(self, name, listen_port, target_port):
        self.name, self.listen_port, self.target_port = name, listen_port, target_port
        self.mode, self.lock, self.socks, self.listener = "up", threading.Lock(), [], None
        self._open()

    def _open(self):
        s = socket.socket()
        s.bind(("127.0.0.1", self.listen_port))
        s.listen(64)
        self.listener = s
        threading.Thread(target=self._accept, args=(s,), daemon=True).start()

    def _accept(self, s):
        while True:
            try:
                client, _ = s.accept()
            except OSError:
                return
            with self.lock:
                self.socks.append(client)
            if self.mode == "stall":
                continue
            try:
                upstream = socket.create_connection(("127.0.0.1", self.target_port), timeout=5)
                upstream.settimeout(None)
            except OSError:
                _reset(client)
                continue
            with self.lock:
                self.socks.append(upstream)
            threading.Thread(target=self._pump, args=(client, upstream), daemon=True).start()
            threading.Thread(target=self._pump, args=(upstream, client), daemon=True).start()

    def _pump(self, src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                if self.mode == "up":
                    dst.sendall(data)
        except OSError:
            pass
        _reset(src)
        _reset(dst)

    def _kill_all(self):
        with self.lock:
            socks, self.socks = self.socks, []
        for s in socks:
            _reset(s)

    def set(self, mode):
        previous, self.mode = self.mode, mode
        if mode == "down":
            try:
                self.listener.close()
            except OSError:
                pass
            self._kill_all()
        elif mode == "up":
            self._kill_all()  # flows that died while cut are gone for good
            if previous == "down":
                self._open()
        log(f"cable {self.name}: {previous} -> {mode}")


# ---------------------------------------------------------------------------
# the gateway process
# ---------------------------------------------------------------------------
STRIP_ENV = {"DB_URL", "DB_USER", "DB_PASSWORD", "PG_PASS", "GATEWAY_DB_URL", "GATEWAY_ENCRYPTION_KEY",
             "DISCOVERY_TIMEOUT_S", "TEST_DB_URL", "PYTHONPATH"}


class Gateway:
    def __init__(self, label, *args):
        env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
        env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        self.label = label
        self.path = OUT / f"gateway_{label}.txt"
        self.out = open(self.path, "w", encoding="utf-8")
        self.proc = subprocess.Popen([PY, "run_gateway.py", *args], cwd=FLOOR, env=env,
                                     stdout=self.out, stderr=subprocess.STDOUT)
        log(f"gateway [{label}] started")

    def alive(self):
        return self.proc.poll() is None

    def text(self):
        self.out.flush()
        return self.path.read_text(encoding="utf-8", errors="replace")

    def wait_exit(self, timeout):
        try:
            return self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def stop(self):
        if self.alive():
            self.proc.terminate()
            self.proc.wait(15)
        self.out.close()


# ---------------------------------------------------------------------------
def main():
    build_copies()
    user, password, production_db = production_credentials()
    if production_db == SIM_DB:
        raise SystemExit("REFUSING TO RUN: the scratch database name is the production one.")

    import sqlalchemy as sa
    from sqlalchemy.engine import URL
    from cryptography.fernet import Fernet

    def url(host, port, db):
        return URL.create("postgresql", user, password, host, port, db).render_as_string(hide_password=False)

    admin = sa.create_engine(url("localhost", 5432, "postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f"DROP DATABASE IF EXISTS {SIM_DB} WITH (FORCE)"))
        c.execute(sa.text(f"CREATE DATABASE {SIM_DB}"))

    key = Fernet.generate_key().decode()
    direct_url, linked_url = url("localhost", 5432, SIM_DB), url("127.0.0.1", DB_LINK_PORT, SIM_DB)

    # ---- the MES PC: this process, running from its own copy
    write_env(MES, DB_URL=direct_url, GATEWAY_ENCRYPTION_KEY=key)
    for k in STRIP_ENV:
        os.environ.pop(k, None)
    os.environ.update(DB_URL=direct_url, GATEWAY_ENCRYPTION_KEY=key)
    os.chdir(MES)
    sys.path.insert(0, str(MES))

    import crud
    crud.init_db()
    from starlette.testclient import TestClient
    import api.main
    client = TestClient(api.main.app)
    csrf = {"x-mes-client": "1"}
    r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=csrf)
    assert r.status_code == 200, f"seeded admin login failed: {r.status_code} {r.text}"
    crud.update_plant_settings({"enable_device_gateway": True})
    meta = client.get("/api/devices/meta").json()
    pump_id = meta["pumps"][0]["id"] if meta["pumps"] else None

    def add_device(body, tags=()):
        r = client.post("/api/devices", json=body, headers=csrf)
        assert r.status_code == 201, r.text
        for t in tags:
            client.post(f"/api/devices/{r.json()['id']}/tags", json=t, headers=csrf)
        return r.json()["id"]

    FakePLC(PLC_PORT)
    plc_cable = Link("gateway->PLC", PLC_LINK_PORT, PLC_PORT)
    db_cable = Link("gateway->database", DB_LINK_PORT, 5432)

    plc_id = add_device(
        {"device_name": "Filler PLC", "device_role": "filling_station", "protocol": "modbus_tcp",
         "connection": {"host": "127.0.0.1", "port": PLC_LINK_PORT, "unit_id": 1, "timeout_s": 3},
         "poll_interval_s": 2.0, "pump_station_id": pump_id},
        [{"raw_tag": "40001", "canonical_metric": "units_poured_total", "data_type": "int", "scale_factor": 1.0, "unit": ""},
         {"raw_tag": "40002", "canonical_metric": "weight_g", "data_type": "float", "scale_factor": 1.0, "unit": "g"}])
    add_device({"device_name": "Cart Scale (simulated)", "device_role": "scale", "protocol": "simulator",
                "connection": {"sim_profile": "scale", "cycle_seconds": 6}, "poll_interval_s": 2.0})
    unreachable_id = add_device({"device_name": "PLC nobody can reach", "device_role": "other", "protocol": "modbus_tcp",
                "connection": {"host": UNROUTABLE, "port": 502, "unit_id": 1, "timeout_s": 3}, "poll_interval_s": 2.0},
               [{"raw_tag": "40001", "canonical_metric": "machine_state", "data_type": "int", "scale_factor": 1.0, "unit": ""}])

    watch = sa.create_engine(direct_url)

    def devices():
        return {d["device_name"]: d for d in client.get("/api/devices").json()}

    def reading_age(name):
        with watch.connect() as c:
            age = c.execute(sa.text(
                "select extract(epoch from timezone('utc', now()) - max(r.timestamp)) from device_readings r "
                "join devices d on d.id = r.device_id where d.device_name = :n"), {"n": name}).scalar()
        return float(age) if age is not None else None

    def fresh(name, within=8):
        age = reading_age(name)
        return age is not None and age <= within

    def wait_for(pred, timeout):
        started = time.time()
        while time.time() - started < timeout:
            try:
                if pred():
                    return round(time.time() - started, 1)
            except Exception:
                pass
            time.sleep(1)
        return None

    def counts_add_up():
        """Every pour the PLC counted while the gateway was watching made it
        into production_logs, outages included."""
        with watch.connect() as c:
            first, last = c.execute(sa.text(
                "select min(value_numeric), max(value_numeric) from device_readings "
                "where device_id = :d and metric = 'units_poured_total'"), {"d": plc_id}).one()
            logged = c.execute(sa.text(
                "select coalesce(sum(bottles_filled), 0) from production_logs "
                "where operator_name = 'Automated Gateway'")).scalar()
        return int(logged), int((last or 0) - (first or 0))

    def floor_env(**over):
        base = dict(DB_URL="auto", DB_USER=user, DB_PASSWORD=password, GATEWAY_ENCRYPTION_KEY=key,
                    GATEWAY_DB_URL=linked_url)
        base.update(over)
        write_env(FLOOR, **base)

    gateways = []

    def start(label, *args):
        g = Gateway(label, *args)
        gateways.append(g)
        return g

    try:
        # -------------------------------------------------------------------
        print("\n== 1. Normal running")
        floor_env()
        gw = start("main")
        t = wait_for(lambda: fresh("Filler PLC") and fresh("Cart Scale (simulated)"), 60)
        check(t is not None, f"the gateway reads the PLC and the scale (live after {t} s)")
        nodes = client.get("/api/devices/gateways").json()
        check(len(nodes) == 1 and nodes[0]["online"], f"the Device Registry sees one gateway checking in (got {nodes})")
        time.sleep(12)
        d = devices()
        check(d["Filler PLC"]["status"] == "Online", f"Filler PLC shows Online (got {d['Filler PLC']['status']})")
        check(d["PLC nobody can reach"]["status"] == "Error" and "192.0.2.1" in (d["PLC nobody can reach"]["last_error"] or ""),
              f"an unreachable PLC shows Error, naming its address (got {d['PLC nobody can reach']})")
        check((d["Filler PLC"]["last_seen_at"] or "").endswith("+00:00"), f"timestamps carry their UTC offset (got {d['Filler PLC']['last_seen_at']})")
        logged, counted = counts_add_up()
        # Within one: the newest reading can be saved a moment before its pour is logged.
        check(logged > 0 and abs(logged - counted) <= 1, f"production logged matches the PLC counter ({logged} logged, {counted} counted)")

        # -------------------------------------------------------------------
        print("\n== 2. Find Devices and Test Connection run on the gateway PC")
        host = nodes[0]["hostname"]
        r = client.post(f"/api/devices/gateways/{host}/jobs", headers=csrf, json={
            "kind": "test_connection",
            "params": {"protocol": "modbus_tcp", "connection": {"host": "127.0.0.1", "port": PLC_LINK_PORT, "unit_id": 1},
                       "probe_tags": ["40001", "40002:float"]}})
        job_id = r.json()["id"]
        job = None
        for _ in range(30):
            job = client.get(f"/api/devices/gateway-jobs/{job_id}").json()
            if job["status"] in ("done", "error"):
                break
            time.sleep(1)
        raw = (job.get("result") or {}).get("raw", {})
        check(job["status"] == "done" and (job.get("result") or {}).get("ok"), f"a Test Connection job comes back from the gateway (got {job})")
        check(isinstance(raw.get("40001"), int) and 840 < float(raw.get("40002", 0)) < 860,
              f"...with the counter as a whole number and 40002:float as the fill weight (got {raw})")
        check(f"running test_connection for the Device Registry (job {job_id})" in gw.text(),
              "...and it was the gateway process that ran it, not the server")
        r = client.post(f"/api/devices/gateways/{host}/jobs", headers=csrf, json={"kind": "serial_ports", "params": {}})
        job_id = r.json()["id"]
        for _ in range(30):
            job = client.get(f"/api/devices/gateway-jobs/{job_id}").json()
            if job["status"] in ("done", "error"):
                break
            time.sleep(1)
        check(job["status"] == "done" and isinstance(job["result"], list), f"a serial-port listing comes back from the gateway (got {job})")

        # -------------------------------------------------------------------
        print("\n== 3. PLC cable pulled")
        plc_cable.set("down")
        t = wait_for(lambda: devices()["Filler PLC"]["status"] == "Error", 30)
        check(t is not None, f"Filler PLC turns Error (after {t} s) instead of staying Online")
        d = devices()["Filler PLC"]
        check("no response" in (d["last_error"] or "") or "could not reach" in (d["last_error"] or ""),
              f"...and says why (got {d['last_error']!r})")
        check(fresh("Cart Scale (simulated)"), "the other device keeps being read")
        time.sleep(10)
        plc_cable.set("up")
        t = wait_for(lambda: fresh("Filler PLC", 4) and devices()["Filler PLC"]["status"] == "Online", 90)
        check(t is not None, f"Filler PLC comes back by itself when the cable is back (after {t} s)")

        # -------------------------------------------------------------------
        print("\n== 4. PLC cable stalls (packets silently dropped)")
        plc_cable.set("stall")
        t = wait_for(lambda: devices()["Filler PLC"]["status"] == "Error", 40)
        check(t is not None, f"Filler PLC turns Error on a silent stall too (after {t} s)")
        plc_cable.set("up")
        t = wait_for(lambda: fresh("Filler PLC", 4) and devices()["Filler PLC"]["status"] == "Online", 90)
        check(t is not None, f"...and recovers when it clears (after {t} s)")

        # -------------------------------------------------------------------
        print("\n== 5. Database cable pulled for 25 s")
        db_cable.set("down")
        time.sleep(25)
        check(gw.alive(), "the gateway is still running during the outage")
        db_cable.set("up")
        t = wait_for(lambda: fresh("Filler PLC", 5) and fresh("Cart Scale (simulated)", 5), 90)
        check(t is not None and gw.alive(), f"readings resume by themselves after the outage (after {t} s)")
        check("can't reach the MES database" in gw.text() and "reachable again" in gw.text(),
              "the gateway logged the outage and the recovery in plain words")

        # -------------------------------------------------------------------
        print("\n== 6. Database cable stalls for 45 s")
        db_cable.set("stall")
        time.sleep(45)
        check(gw.alive(), "the gateway is still running during the stall")
        db_cable.set("up")
        t = wait_for(lambda: fresh("Filler PLC", 5) and fresh("Cart Scale (simulated)", 5), 150)
        check(t is not None and gw.alive(), f"readings resume by themselves after the stall (after {t} s)")
        time.sleep(8)
        logged, counted = counts_add_up()
        check(abs(logged - counted) <= 1, f"no pours were lost across both outages ({logged} logged, {counted} counted)")

        # -------------------------------------------------------------------
        print("\n== 7. run_gateway.py --check on the floor PC")
        # The deliberately unreachable PLC would (correctly) fail the check.
        client.put(f"/api/devices/{unreachable_id}/enabled?enabled=false", headers=csrf)
        chk = start("check", "--check")
        code = chk.wait_exit(90)
        check(code == 0, f"--check passes while everything is reachable (exit {code})")
        plc_cable.set("down")
        chk2 = start("check_plc_down", "--check")
        code = chk2.wait_exit(90)
        check(code == 1 and "Filler PLC" in chk2.text() and "[X]" in chk2.text(), f"--check fails and names the PLC when its cable is out (exit {code})")
        plc_cable.set("up")

        # -------------------------------------------------------------------
        print("\n== 8. The gateway PC is switched off")
        gw.stop()
        log("gateway stopped")
        t = wait_for(lambda: devices()["Filler PLC"]["status"] == "Not reporting", 90)
        d = devices()["Filler PLC"]
        check(t is not None, f"Filler PLC shows Not reporting once the gateway is gone (after {t} s), not Online")
        check("stuck waiting on this device" not in (d["last_error"] or ""),
              f"...without blaming the device while the gateway is only just gone (got {d['last_error']!r})")
        t = wait_for(lambda: "No gateway PC has checked in" in (devices()["Filler PLC"]["last_error"] or ""), 90)
        check(t is not None, f"...and then says plainly that no gateway is checking in (got {devices()['Filler PLC']['last_error']!r})")
        check(not client.get("/api/devices/gateways").json()[0]["online"], "the gateway list shows it offline")

        # -------------------------------------------------------------------
        print("\n== 9. Floor PC's .env has a different encryption key")
        floor_env(GATEWAY_ENCRYPTION_KEY=Fernet.generate_key().decode())
        wrong = start("wrong_key")
        t = wait_for(lambda: "GATEWAY_ENCRYPTION_KEY" in (devices()["Filler PLC"]["last_error"] or ""), 60)
        check(t is not None, f"the device error names GATEWAY_ENCRYPTION_KEY instead of KeyError 'host' (got {devices()['Filler PLC']['last_error']!r})")
        wrong.stop()

        # -------------------------------------------------------------------
        print("\n== 10. GATEWAY_DB_URL points somewhere unreachable")
        floor_env(GATEWAY_DB_URL=url(UNROUTABLE, 5432, SIM_DB))
        lost = start("db_unroutable")
        t = wait_for(lambda: "Nothing answered from" in lost.text(), 60)
        check(t is not None, f"it explains that nothing answered (after {t} s)")
        time.sleep(3)
        check(lost.alive() and "Trying again" in lost.text(), "...and keeps trying rather than exiting")
        lost.stop()

        # -------------------------------------------------------------------
        print("\n== 11. mDNS blocked and a .env copied from the MES PC")
        floor_env(GATEWAY_DB_URL=None, DB_URL=url("localhost", 59999, SIM_DB), DB_USER=None, DB_PASSWORD=None)
        copied = start("copied_env")
        t = wait_for(lambda: "Nothing is listening on localhost" in copied.text(), 60)
        check(t is not None, f"it explains the .env points at this PC, and what to set instead (after {t} s)")
        check("GATEWAY_DB_URL=" in copied.text(), "...including the GATEWAY_DB_URL line to add")
        copied.stop()

        # -------------------------------------------------------------------
        print("\n== 12. The database comes back while the gateway is waiting for it")
        db_cable.set("down")
        floor_env()
        waiting = start("waits_for_db")
        time.sleep(20)
        check(waiting.alive(), "a gateway started while the MES PC is down waits instead of exiting")
        db_cable.set("up")
        t = wait_for(lambda: fresh("Filler PLC", 5), 150)
        check(t is not None, f"...and starts reading on its own once the database is back (after {t} s)")
        waiting.stop()

        # -------------------------------------------------------------------
        if "--with-mdns" in sys.argv:
            print("\n== 13. Zero-config: finds the database over mDNS")
            import service_announcer
            from service_discovery import discover
            service_announcer.start_announcing()
            seen = discover(timeout_s=6)
            if len(seen) == 1 and seen[0]["dbname"] == SIM_DB:
                floor_env(GATEWAY_DB_URL=None, DB_URL="auto")
                found = start("mdns")
                time.sleep(30)
                text = found.text()
                check("Connected to the MES database" in text or "pg_hba.conf" in text,
                      "it either connects, or explains the exact pg_hba.conf line this PC needs")
                if "pg_hba.conf" in text:
                    log("note: this PC's PostgreSQL doesn't accept LAN logins yet - see gateway_mdns.txt")
                found.stop()
            else:
                log(f"skipped - the announcement wasn't seen exactly once ({seen})")
            service_announcer._stop_announcing()

    except Exception:
        FAILS.append("the simulation itself crashed")
        traceback.print_exc()
    finally:
        for g in gateways:
            try:
                g.stop()
            except Exception:
                pass
        watch.dispose()
        try:
            __import__("db_core").engine.dispose()
        except Exception:
            pass
        try:
            with admin.connect() as c:
                c.execute(sa.text(f"DROP DATABASE IF EXISTS {SIM_DB} WITH (FORCE)"))
        except Exception as exc:
            print(f"could not drop the scratch database {SIM_DB}: {exc}")

    print("\n" + "=" * 66)
    if FAILS:
        print(f"{len(FAILS)} of {CHECKS} GATEWAY SIMULATION CHECKS FAILED:")
        for f in FAILS:
            print(f"  - {f}")
    else:
        print(f"ALL {CHECKS} GATEWAY SIMULATION CHECKS PASSED")
    print(f"Gateway output for each phase: {OUT}")
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
