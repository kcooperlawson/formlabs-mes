"""The readiness check's reasoning, without needing a machine to be wrong.

preflight.py answers "is this PC ready to run the plant". Half of it pokes at
the machine - sockets, subprocesses, Postgres - and can only be exercised on a
real one. The other half decides what those facts mean, and that is the half
where a mistake is expensive: a check that reports "ready" on a PC that is not
is worse than no check, because somebody carried a laptop to the floor on the
strength of it.

So the judgements take plain values and are checked here against the
situations that matter and cannot be produced on demand: a Postgres older than
the pg_dump pointed at it, a schema left behind by a dump from an earlier
release, a machine with no network, a firewall rule nobody added.

The manifest comparison is here too, for the same reason. Its failure case -
a restore that ran but brought fewer rows than it should have - is the one
nobody can rehearse, and it is the one that decides whether a plant's history
survives a change of machine.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import preflight as pf  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 66)
print("IS THIS PC READY")
print("=" * 66)

# --- Python -----------------------------------------------------------------
check("an old Python fails outright",
      pf.judge_python((3, 9, 7), True)["state"], pf.FAIL)
check("and says which version to install",
      "3.11" in pf.judge_python((3, 9, 7), True)["fix"], True)
check("a good one outside the venv is a warning, not a failure",
      pf.judge_python((3, 12, 1), False)["state"], pf.WARN)
check("because the checks still tell the truth about the machine",
      pf.judge_python((3, 12, 1), False)["state"] != pf.FAIL, True)
check("a good one inside the venv passes",
      pf.judge_python((3, 11, 9), True)["state"], pf.OK)
print("  Python OK")

# --- dependencies ------------------------------------------------------------
check("missing packages fail", pf.judge_dependencies(["bcrypt"])["state"], pf.FAIL)
check("and are named, so it is obvious what went wrong",
      "bcrypt" in pf.judge_dependencies(["bcrypt"])["detail"], True)
check("a full set passes", pf.judge_dependencies([])["state"], pf.OK)
print("  dependencies OK")

# --- the database and its schema --------------------------------------------
check("an unreachable database fails",
      pf.judge_database(False, "?", "connection refused")["state"], pf.FAIL)
check("and the real error is shown, not swallowed",
      "connection refused" in pf.judge_database(False, "?", "connection refused")["detail"],
      True)
check("a reachable one passes", pf.judge_database(True, "formlabs_mes")["state"], pf.OK)

# The case that arrives with a restored dump: data is there, schema is behind.
check("a schema behind the app fails",
      pf.judge_schema("0009_simple_mode", "0011_vessel_identity")["state"], pf.FAIL)
check("and names both versions rather than just complaining",
      "0009_simple_mode" in pf.judge_schema("0009_simple_mode", "0011_vessel_identity")["detail"],
      True)
check("a matching one passes",
      pf.judge_schema("0011_vessel_identity", "0011_vessel_identity")["state"], pf.OK)
check("an unstamped database fails", pf.judge_schema(None, "0011_x")["state"], pf.FAIL)
check("not knowing the expected version is only a warning",
      pf.judge_schema("0011_x", None)["state"], pf.WARN)
print("  database and schema OK")

# --- the trap that ruins a move ---------------------------------------------
# pg_dump older than the server cannot read it, and the restore fails partway
# through with a message about an "invalid command" that mentions no versions.
check("pg_dump older than the server fails",
      pf.judge_pg_tools(True, (15, 0), (16, 0))["state"], pf.FAIL)
check("and says so in versions, which is the actual problem",
      "15" in pf.judge_pg_tools(True, (15, 0), (16, 0))["detail"], True)
check("newer than the server is fine",
      pf.judge_pg_tools(True, (17, 0), (16, 0))["state"], pf.OK)
check("the same version is fine",
      pf.judge_pg_tools(True, (16, 2), (16, 0))["state"], pf.OK)
check("no tools at all fails", pf.judge_pg_tools(False, None, None)["state"], pf.FAIL)
check("and unknown versions do not invent a failure",
      pf.judge_pg_tools(True, None, None)["state"], pf.OK)
print("  backup tools OK")

# --- proving a backup works before it is needed -----------------------------
check("a backup that could not be taken fails",
      pf.judge_backup(None, None, "pg_dump exited 1")["state"], pf.FAIL)
check("one that was taken passes",
      pf.judge_backup("mes_backup_20260906_070000.sql", 2_400_000)["state"], pf.OK)
check("and its size is reported, so an empty one is visible",
      "2.3 MB" in pf.judge_backup("x.sql", 2_400_000)["detail"], True)
print("  test backup OK")

# --- packages the plant can manage without -----------------------------------
# openpyxl was missing on the plant PC and nothing said so until a page went
# blank. It is a warning and not a failure because every screen still works
# and the record still exports as CSV: reporting a working machine as unready
# is how a check stops being read.
check("no optional packages missing passes", pf.judge_optional({})["state"], pf.OK)
check("a missing one warns rather than failing",
      pf.judge_optional({"openpyxl": "Excel downloads"})["state"], pf.WARN)
check("it says what stops working",
      "Excel downloads" in pf.judge_optional({"openpyxl": "Excel downloads"})["detail"], True)
check("and hands over the command that installs it",
      "pip install openpyxl" in pf.judge_optional({"openpyxl": "x"})["fix"], True)
check("a missing optional package never makes a PC unready",
      pf.exit_code([pf.judge_optional({"openpyxl": "x"})]), 0)
print("  optional packages OK")

# --- the port and the firewall ----------------------------------------------
check("a port held by something else fails", pf.judge_port(False, False)["state"], pf.FAIL)
check("a port held by our own app is fine", pf.judge_port(False, True)["state"], pf.OK)
check("a free port is fine", pf.judge_port(True, False)["state"], pf.OK)

# A missing firewall rule is a warning rather than a failure: Windows often
# adds its own when it prompts, so the phones may work anyway - but if they
# do not, this is the only place that says why.
check("no firewall rule warns", pf.judge_firewall(True, False)["state"], pf.WARN)
check("and hands over the exact command",
      "netsh advfirewall" in pf.judge_firewall(True, False)["fix"], True)
check("a rule present passes", pf.judge_firewall(True, True)["state"], pf.OK)
check("not knowing warns rather than failing",
      pf.judge_firewall(True, None)["state"], pf.WARN)
check("and off Windows it is simply not applicable",
      pf.judge_firewall(False, None)["state"], pf.INFO)
print("  port and firewall OK")

# --- what to give the phones ------------------------------------------------
addr = pf.judge_addresses("PLANT-LAPTOP", ["192.168.1.42"])
check("the machine name is offered", "http://PLANT-LAPTOP:8501" in addr["detail"], True)
check("the address is too", "http://192.168.1.42:8501" in addr["detail"], True)
check("and the name is the one marked for bookmarking",
      addr["detail"].index("PLANT-LAPTOP") < addr["detail"].index("192.168.1.42"), True)
check("with the reason spelled out, because it is the whole point",
      "rejoins" in addr["fix"], True)
check("a machine with no network says so",
      pf.judge_addresses("", [])["state"], pf.WARN)
print("  addresses OK")

# --- disk and clock ----------------------------------------------------------
check("a nearly full disk fails", pf.judge_disk(500 * 1024 ** 2)["state"], pf.FAIL)
check("a tight one warns", pf.judge_disk(3 * 1024 ** 3)["state"], pf.WARN)
check("a healthy one passes", pf.judge_disk(200 * 1024 ** 3)["state"], pf.OK)
check("an unreadable one warns rather than failing", pf.judge_disk(None)["state"], pf.WARN)
check("a machine in another timezone warns",
      pf.judge_clock("PST", "EDT")["state"], pf.WARN)
check("but is told it is not a fault",
      "not a fault" in pf.judge_clock("PST", "EDT")["fix"], True)
check("a matching one passes", pf.judge_clock("EDT", "EDT")["state"], pf.OK)
print("  disk and clock OK")

# --- the verdict -------------------------------------------------------------
# The property that matters most: a PC with a real problem must never be
# reported ready, and warnings must never hold up a plant that is fine.
ready = [pf.check("a", pf.OK, "x"), pf.check("b", pf.WARN, "y"), pf.check("c", pf.INFO, "z")]
broken = ready + [pf.check("d", pf.FAIL, "w")]
check("warnings alone do not make a PC unready", pf.exit_code(ready), 0)
check("one failure does", pf.exit_code(broken), 1)
check("and the summary says so in words", "NOT READY" in pf.report(broken), True)
check("a clean run says it plainly", "READY. This PC can run the plant." in pf.report(
    [pf.check("a", pf.OK, "x")]), True)
check("a run with warnings does not claim to be clean",
      "READY, with 1 thing(s) worth knowing about." in pf.report(ready), True)
check("every remedy is printed under its own check",
      "do this" in pf.report([pf.check("a", pf.FAIL, "broken", "do this")]), True)
print("  the verdict OK")

# --- the manifest, which decides whether a move is trusted ------------------
sys.path.insert(0, str(ROOT))
import _migration_helper as mh  # noqa: E402


def compare(expected_counts, actual_counts):
    """Run the comparison with both sides supplied, and return its exit code."""
    import io
    import contextlib
    import utils
    orig_read, orig_live = utils.read_backup_manifest, utils.database_manifest
    utils.read_backup_manifest = lambda name: {"counts": expected_counts,
                                               "newest_log": None}
    utils.database_manifest = lambda: {"counts": actual_counts, "newest_log": None}
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = mh.cmd_verify_restore("any.sql")
        return code, buf.getvalue()
    finally:
        utils.read_backup_manifest, utils.database_manifest = orig_read, orig_live


code, out = compare({"production_logs": 12431, "users": 6},
                    {"production_logs": 12431, "users": 6})
check("a complete restore passes", code, 0)
check("and says so", "VERIFY_OK" in out, True)

code, out = compare({"production_logs": 12431, "users": 6},
                    {"production_logs": 9, "users": 6})
check("a restore missing rows fails", code, 1)
check("and names the table that came across short", "production_logs" in out, True)
check("and says not to start logging on it yet", "Do not start logging" in out, True)

# More rows than the backup is not a fault: the plant may simply have carried
# on working on this machine since the dump was taken.
code, _ = compare({"production_logs": 100}, {"production_logs": 140})
check("a database ahead of the backup is not a failure", code, 0)

code, out = compare({}, {"production_logs": 5})
check("a dump from before manifests existed is skipped, not failed", code, 0)
check("and says why", "VERIFY_SKIPPED" in out, True)
print("  restore verification OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} PREFLIGHT CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} PREFLIGHT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
