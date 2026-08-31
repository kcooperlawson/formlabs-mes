# Test suite

Three scripts that exercise the app end to end against a **throwaway** Postgres —
never your production database. `_boot.py` refuses to run if the test URL matches
the `DB_URL` in `.env`.

Run them from the project root, in this order (the UI tests read the data the
workflow test creates):

```
python tests/test_workflow.py     # migrations + full floor simulation + all the numbers
python tests/test_ui.py           # renders Operator_Form.py headless and drives the lot gate
python tests/test_pages.py        # renders every page and reports which ones raise
```

## Getting a scratch database

**Windows / any machine with Postgres already installed** — make an empty database
and point the suite at it. It wipes the schema on each run, so use a scratch one:

```
createdb formlabs_test
set TEST_DB_URL=postgresql+psycopg2://postgres:PASSWORD@localhost:5432/formlabs_test
```

**Linux / macOS, nothing installed** — `pip install pgserver` and the suite starts
its own private PostgreSQL under `~/pgdata`. No install, no admin rights.

Either way you also need: `pip install streamlit pandas sqlalchemy psycopg2-binary bcrypt python-dotenv alembic pyflakes`

## What each one covers

**test_workflow.py** — 63 assertions. Applies all four migrations to an empty
database and checks the result matches `models.py` table by table. Then: an admin
seeds stations, resins and people; a manager creates three work orders; operators
clear per-station startup checklists; they pour clean logs, a fast-path log, a
mismatched cartridge, a pulled cartridge, an unassigned-run log and an RPS log;
downtime and packing land. Every number the UI shows — poured, scrap, yield, WIP,
per-operator totals, run progress, flag rate, reconciliation variance — is then
recomputed from the raw rows and compared against hand-figured expectations.

**test_ui.py** — 28 assertions using Streamlit's `AppTest`, which executes the page
script the way a browser session does. Checks the terminal locks for an operator
with no checklist, unlocks once it's cleared, that the gate blocks an untouched
form, that a wrong lot raises the stop screen and demands a reason, that the right
lot goes green (including a messy `l: 2411a0742` transcription), that the expected
lot is never printed anywhere on the page, and that RPS bypasses the gate entirely.

**test_pages.py** — renders all 18 pages under an admin session and reports any
that raise. `Tv_Dashboard.py` is skipped: it ends in a deliberate refresh loop and
never hands control back to a harness.

## Note on `pyflakes`

Worth running alongside these — it caught eight pages that would `NameError` the
first time anyone changed the theme from them:

```
python -m pyflakes *.py pages/*.py
```
