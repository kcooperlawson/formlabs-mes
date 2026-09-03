"""The three states a database can be in when the app starts, and whether
each of them ends up at head.

This is the code that runs before anything else on every boot, and it is the
only code whose failure mode is "the app does not start on the other PC". The
suite already proves the app works once the schema is right; nothing proved
how the schema gets right.

The three states:

  1. **Empty.** A new install. Every migration runs from nothing.
  2. **Pre-Alembic.** The app's tables exist because an older version of
     init_db() created them with `Base.metadata.create_all()` plus a list of
     raw ALTER TABLEs, and no revision was ever recorded. Restoring an older
     backup onto a second machine lands here.
  3. **Stamped and behind.** The normal case: the database was last touched by
     an earlier release and is a few revisions short of the code now running.

State 2 is why this file exists. Stamping used to be the *alternative* to
upgrading rather than a step before it, so a pre-Alembic database was marked
as being at the baseline and then ran the rest of that boot against a schema
seven revisions behind the models. It died on the first settings read with
"column plant_settings.shift_count does not exist". Every path has to finish
at head, and state 3 additionally has to finish with its data intact - a
migration that quietly emptied a table would satisfy "reached head" and be a
catastrophe.

Each state needs its own process, because init_db() guards itself against
running twice inside one (Alembic's environment is not re-entrant), so this
script re-executes itself in a subprocess per case.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

DB = "formlabs_boot_paths"
HEAD = "0008_pump_form_url"

# Columns added after the baseline, one per migration that added any. If the
# boot path stopped short, these are what would be missing - and they are what
# the models select on the first query, so their absence is not cosmetic.
LATE_COLUMNS = [
    ("lot_verifications", "id"),            # 0003
    ("daily_checklists", "pump_station"),   # 0004
    ("resin_specs", "color_tag"),           # 0005
    ("production_logs", "check_weight_g"),  # 0006
    ("plant_settings", "shift_count"),      # 0007
    ("plant_settings", "pump_form_url"),    # 0008
]


# --------------------------------------------------------------- child side --
def _engine():
    import db_core
    return db_core.engine


def _revision():
    import sqlalchemy as sa
    with _engine().connect() as c:
        try:
            return c.execute(sa.text("select version_num from alembic_version")).scalar()
        except Exception:
            return None


def _has(table, col):
    import sqlalchemy as sa
    with _engine().connect() as c:
        return c.execute(sa.text(
            "select 1 from information_schema.columns "
            "where table_name=:t and column_name=:c"), {"t": table, "c": col}).first() is not None


def _report(case):
    """Everything the parent needs to judge one boot, on one line each."""
    import crud
    print(f"REV {_revision()}")
    for t, col in LATE_COLUMNS:
        print(f"COL {t}.{col} {_has(t, col)}")
    try:
        n = len(crud.get_plant_settings())
        print(f"SETTINGS ok {n}")
    except Exception as e:
        print(f"SETTINGS fail {type(e).__name__}: {str(e)[:90]}")
    if case == "behind":
        # The data that was in the database before the upgrade must still be
        # there afterwards. A migration that dropped and recreated a table
        # would reach head and lose the plant's history.
        import sqlalchemy as sa
        # Counted by identity, not by total: importing crud seeds a default
        # roster, so a bare "users > 0" would pass even if the pre-upgrade rows
        # had been wiped and replaced.
        with _engine().connect() as c:
            logs = c.execute(sa.text(
                "select count(*) from production_logs where operator_name='Boot Test'")).scalar()
            users = c.execute(sa.text(
                "select count(*) from users where username='boottest'")).scalar()
            lph = c.execute(sa.text(
                "select target_lph from plant_settings order by id limit 1")).scalar()
        print(f"KEPT logs={logs} users={users} target_lph={lph}")


def child(case):
    import _boot
    if case == "empty":
        _boot.boot(fresh=True, db_name=DB)
        import crud  # noqa: F401  - importing it runs init_db, same as the app
        _report(case)

    elif case == "prealembic_setup":
        # Build a database that looks like the old init_db() made it: the
        # app's tables, and no record of any revision.
        _boot.boot(fresh=True, db_name=DB)
        from alembic.config import Config
        from alembic import command
        import sqlalchemy as sa
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(cfg, "0001_baseline")
        with _engine().begin() as c:
            c.execute(sa.text("drop table if exists alembic_version"))
        print(f"REV {_revision()}")
        print(f"COL users.id {_has('users', 'id')}")

    elif case == "behind_setup":
        # An earlier release: stamped, a few revisions short, and with real
        # rows in it.
        _boot.boot(fresh=True, db_name=DB)
        from alembic.config import Config
        from alembic import command
        import sqlalchemy as sa
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(cfg, "0005_resin_colors")
        with _engine().begin() as c:
            c.execute(sa.text(
                "insert into users (username, email, pin, full_name, role, shift) "
                "values ('boottest', 'b@x.local', 'x', 'Boot Test', 'operator', 'Shift 1')"))
            c.execute(sa.text(
                "insert into production_logs (timestamp, log_type, operator_name, shift, "
                "pump_station, cartridge_type, resin_type, bottles_filled) "
                "values (now(), 'pouring', 'Boot Test', 'Shift 1', 'Pump 1', "
                "'V1 (1L Cartridge)', 'Grey V5', 42)"))
            c.execute(sa.text("insert into plant_settings (target_lph) values (417.0)"))
        print(f"REV {_revision()}")

    else:  # "prealembic" / "behind" - the boot being measured
        _boot.boot(fresh=False, db_name=DB)
        import crud  # noqa: F401
        _report(case)


# -------------------------------------------------------------- parent side --
def run(case):
    out = subprocess.run([sys.executable, __file__, "--child", case],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    lines = [l for l in out.stdout.splitlines() if l.split(" ")[0] in
             ("REV", "COL", "SETTINGS", "KEPT")]
    if not lines:
        print(out.stdout[-1500:])
        print(out.stderr[-1500:])
    return lines


FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def judge(case, lines):
    rev = next((l.split(" ", 1)[1] for l in lines if l.startswith("REV ")), None)
    check(rev == HEAD, f"{case}: reaches head (got {rev})")
    for t, col in LATE_COLUMNS:
        got = f"COL {t}.{col} True" in lines
        check(got, f"{case}: {t}.{col} exists after boot")
    ok = any(l.startswith("SETTINGS ok") for l in lines)
    check(ok, f"{case}: reading plant settings does not raise")
    return lines


def main():
    print("=" * 66)
    print("BOOT PATHS: what init_db() does with each state a database can be in")
    print("=" * 66)

    print("\n1. Empty database - a new install")
    judge("empty", run("empty"))

    print("\n2. Pre-Alembic database - tables present, no revision recorded")
    pre = run("prealembic_setup")
    check(any(l == "REV None" for l in pre), "setup: starts with no revision recorded")
    check("COL users.id True" in pre, "setup: but the app's tables are already there")
    judge("prealembic", run("prealembic"))

    print("\n3. Stamped but behind, with data in it")
    beh = run("behind_setup")
    check(any(l == "REV 0005_resin_colors" for l in beh), "setup: starts three revisions back")
    lines = judge("behind", run("behind"))
    kept = next((l for l in lines if l.startswith("KEPT ")), "")
    check("logs=1" in kept, f"behind: the production log survives the upgrade ({kept})")
    check("users=1" in kept, f"behind: the user survives the upgrade ({kept})")
    check("target_lph=417.0" in kept, f"behind: the plant setting is not reset ({kept})")

    print("\n" + "=" * 66)
    if FAILS:
        print(f"{len(FAILS)} of {CHECKS} BOOT PATH CHECKS FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"ALL {CHECKS} BOOT PATH ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        sys.exit(main())
