# Test suite

Scripts that exercise the app end to end against a **throwaway** Postgres —
never your production database. `_boot.py` refuses to run if the test URL
matches the `DB_URL` in `.env`.

Run the whole suite from the project root:

```
venv\Scripts\python.exe dev\run_tests.py
```

It works out a scratch database from your own `.env` (same server, same
account, a different database named `formlabs_test_scratch`), creates it if
it doesn't exist yet, and runs every `tests/test_*.py` in one pass - each in
its own process, sharing that one scratch database, in the order they expect
(`test_workflow.py` first, since a couple of later tests read the fixture it
builds; see the ordering note near the top of `dev/run_tests.py`).

To run just one:

```
venv\Scripts\python.exe dev\run_tests.py tests\test_fill_weight.py
```

## Getting a scratch database

**Windows / any machine with Postgres already installed** — `dev/run_tests.py`
handles this for you; it reads `.env`'s `DB_URL` and creates
`formlabs_test_scratch` on that same server the first time it's needed.

**Linux / macOS, nothing installed** — `pip install pgserver` and `tests/_boot.py`
starts its own private PostgreSQL under a temp folder instead. No install, no
admin rights.

Either way you also need the packages in `requirements.txt` installed (the
FastAPI app's own dependencies - `fastapi`, `uvicorn`, `sqlalchemy`,
`psycopg2-binary`, `pandas`, `bcrypt`, `python-dotenv`, `alembic`, and so on).

## What's covered

- **`test_workflow.py`** — migrations applied to an empty database, checked
  against `models.py` table by table, then a full floor simulation (an admin
  seeds stations/resins/people, a manager creates work orders, operators clear
  checklists and pour clean/mismatched/pulled/RPS logs, downtime and packing
  land) with every number the app shows recomputed from the raw rows and
  compared against hand-figured expectations.
- **`test_api_*.py`** — one file per FastAPI router (auth, checklist, pouring,
  packing, downtime, audit, analytics, admin, and the rest), using
  `starlette.testclient.TestClient` against the real app object - no browser
  needed, but the real routes, the real dependencies, the real database calls.
- Everything else — `test_fill_weight.py`, `test_batches_qc.py`,
  `test_bulk_pour.py`, `test_reactor_level.py`, `test_preflight.py`,
  `test_requirements.py`, `test_update_package.py`, and more - checks one
  module's business logic in isolation, the same way `test_workflow.py`'s own
  arithmetic is checked, without needing the database at all where it can be
  avoided.

## Note on `pyflakes`

Worth running alongside these - it catches real bugs (undefined names, unused
imports) with no database and no server needed:

```
python -m pyflakes *.py api/**/*.py
```
