"""Run a test script against a scratch database on the Postgres already here.

tests/_boot.py wants one of two things. Either pgserver, which builds its own
private Postgres and only works on Linux and macOS, or TEST_DB_URL pointing at
an empty database it is allowed to wipe. On Windows it is the second one, and
nothing was setting it, so every test script died on "No module named
pgserver" before it ran a single check.

This works the address out of .env, so no password is typed anywhere and no
second copy of it exists to go stale. Same server, same account, different
database. It creates that database the first time and refuses point blank if
what it worked out matches the DB_URL the app runs on.

    venv\\Scripts\\python.exe dev\\run_tests.py tests\\test_reactor_level.py
    venv\\Scripts\\python.exe dev\\run_tests.py            (every test_*.py)

One thing to know. With TEST_DB_URL set, _boot ignores the separate database
name a script asks for, so every script shares this one. Each is run in its
own process, in order, which is how the scripts expect to be run anyway.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRATCH = "formlabs_test_scratch"


def production_url():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DB_URL="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No DB_URL in .env, so there is nothing to work from.")


def swap_database(url, name):
    head, _, _tail = url.rpartition("/")
    return "%s/%s" % (head, name)


def main():
    prod = production_url()
    test_url = swap_database(prod, SCRATCH)
    if test_url.strip() == prod.strip():
        raise SystemExit("REFUSING TO RUN: that is the database the app uses.")

    import sqlalchemy as sa
    admin = sa.create_engine(swap_database(prod, "postgres"),
                             isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        exists = c.execute(sa.text(
            "SELECT 1 FROM pg_database WHERE datname = :n"), {"n": SCRATCH}).first()
        if not exists:
            c.execute(sa.text('CREATE DATABASE "%s"' % SCRATCH))
            print("Created the scratch database %s." % SCRATCH)
    admin.dispose()

    env = dict(os.environ, TEST_DB_URL=test_url)

    targets = sys.argv[1:]
    if not targets:
        # .as_posix(), not str(): relative_to() returns OS-native separators,
        # and on Windows that's backslashes - the tail filter below compares
        # against forward-slash literals, so str() here silently never
        # matched and the reordering it names was never actually happening
        # on Windows (harmless while it only ever reordered test_ui.py/
        # test_pages.py to nowhere in particular; not harmless once
        # test_fill_weight.py's own ordering requirement depends on it).
        targets = sorted(p.relative_to(ROOT).as_posix()
                         for p in (ROOT / "tests").glob("test_*.py"))
        # test_fill_weight deliberately reuses the shift test_workflow
        # simulates, and with TEST_DB_URL set every script shares one scratch
        # database, so alphabetical order ("test_fill_weight" before
        # "test_workflow") would run it before that fixture exists. It then
        # fails on an empty table with an index error that says nothing
        # about ordering. Run it last, and workflow immediately before it.
        tail = [t for t in ("tests/test_workflow.py", "tests/test_fill_weight.py")
                if t in targets]
        targets = [t for t in targets if t not in tail] + tail

    failed = []
    for t in targets:
        print("\n" + "=" * 66 + "\n" + t + "\n" + "=" * 66)
        if subprocess.call([sys.executable, t], cwd=str(ROOT), env=env) != 0:
            failed.append(t)

    print("\n" + "=" * 66)
    if failed:
        print("FAILED: " + ", ".join(failed))
    else:
        print("All %d script(s) passed." % len(targets))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
