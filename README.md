# Resin Pouring — Production Logging

An hourly production record for the resin pouring station, kept by the operators on the phones they already carry. A web application (FastAPI + React) over a PostgreSQL database, run from one PC on the plant network.

It installs as a **logging system**: operators log, a manager reads the record and runs the system, and nothing has to be entered by anyone else first. One setting in IT Admin turns it into an **execution system** — work orders dispatched to stations and tracked against targets, with administration separated from the manager role. Nothing is lost switching either way.

The handbook in `docs/` describes what it does. This file is about getting it running.

## What is in this folder

Only the top level runs. Everything else is tooling that never leaves the development PC.

| Path | What it is |
|---|---|
| `api/` | The backend: FastAPI app (`api/main.py`), one router per feature under `api/routers/`. |
| `frontend/` | The React app. `frontend/src` is the source; `frontend/dist` is the built site the backend serves — run `npm install && npm run build` from inside `frontend/` after changing anything under `src/`. |
| `crud.py`, `models.py`, `db_core.py`, `*.py` at the root | The business logic and database layer both the API and the Device Gateway import directly. |
| `migrations/` | Database schema, as numbered Alembic migrations. Applied automatically on start-up. |
| `VERSION` | The one place the running version is written — read by the update tooling and shown in the app's own sidebar. |
| `requirements.txt` | Python dependencies. `requirements-device-gateway.txt` is the optional machine-integration extras. |
| `.env` | This PC's configuration — the database login above all. Never committed; `.env.example` is the template. |
| `backups/` | Database dumps (`.sql`) taken by `Move_To_New_PC.bat` or from IT Admin. |
| `CHANGELOG.md` | What changed and why, newest first. IT Admin shows it in the sidebar. |
| `Setup_On_New_PC.bat` | First-time setup on a machine: virtual environment, dependencies, database, launch. |
| `run_mes_api.bat` | Day-to-day launch against this PC's own PostgreSQL install (`.env`'s `DB_URL`). |
| `run_mes_portable.bat` | Day-to-day launch with a bundled, embedded database — no PostgreSQL install needed on this PC at all. |
| `START_HERE.bat` | The one entry point on a work PC — a menu covering install, day-to-day launch (either of the above), diagnostics, packaging, updates and the HTTPS certificate. |
| `Check_This_PC.bat` | Is this PC ready to run the plant? Checks Python, the packages, Postgres, the schema, the backup tools, disk, the port and the firewall — takes a real backup to prove backups work — and prints the address to give the phones. Run it before carrying a machine to the floor and again after a move. |
| `Move_To_New_PC.bat` | Packages a clean copy of the application — no tests, tooling or document sources — as one zip, with a database backup and optionally the Python packages for an offline install. |
| `tests/` | The release checks. Not shipped. |
| `dev/` | Screenshot, figure, document-build and release-packaging scripts. Not shipped. |
| `docs/` | The three documents — the handbook (for management), the operator guide (for the floor) and the one-page summary — as HTML sources, figures and finished PDFs. Not shipped; print from here. |

## First-time setup on a work PC

The PC needs **Python 3.11 or newer** (tick *Add python.exe to PATH* during install) and, unless you're using the bundled-database option below, **PostgreSQL** (remember the password you give the `postgres` user). Both are ordinary installers from python.org and postgresql.org.

1. On the development PC, run `Move_To_New_PC.bat`. It takes a database backup, asks whether to include the Python packages for an offline install (say **Y** if the work PC may not reach the internet), and produces one zip file.
2. Copy the zip to the work PC and unzip it anywhere.
3. Open `.env` in Notepad and set `DB_URL` to that PC's Postgres login — the line looks like `postgresql://postgres:PASSWORD@localhost:5432/formlabs_mes`. (Skip this if you're going to use the bundled database — option 9 on the menu below ignores `DB_URL` entirely.)
4. Run `START_HERE.bat` and choose **1** (MES / Logger). It builds the virtual environment, installs dependencies, checks the Postgres tools are present, creates the database, and asks one question if a backup is included: **restore it, or start clean**.
5. From the same menu, choose **5** to diagnose the PC. One page saying whether this machine is ready, and if not, exactly what to type. It also prints the address to give the phones.

**No PostgreSQL install at all?** Choose **9** (Start the MES with a bundled database) instead of step 4/5 above. It runs a private, embedded PostgreSQL out of `pgdata\` next to the project — nothing system-wide, nothing that needs admin rights. First run creates the database and seeds the default admin account; every run after that just starts it back up.

**Starting clean** is the default and the right choice for a plant that has not used this before. The application builds its own schema and seeds one administrator account, three placeholder pump stations and the downtime reason list. Sign in as **manager** with PIN **admin123**, then from IT Admin: change that PIN, replace the placeholder pumps with the real ones, and add the operators. That is the whole setup.

**Restoring the backup** brings across everything from the PC the backup was taken on — every log, account and setting. Choose it when moving an established database between machines, not for a first install.

**Restoring is checked, not assumed.** Every backup carries a manifest of what was in the database when it was taken, and setup compares it against the restored database row by row before letting you go on. If anything came across short it stops and says so — the machine the backup came from still has the data, so nothing is lost as long as nothing new is written on the new PC first.

## Day to day

`START_HERE.bat` is the one thing to double-click. Choose **3** to start the MES against this PC's own PostgreSQL, or **9** for the bundled-database option — either way it prints the address to open, `https://<this PC's name or IP>:8000` (plain `http://` until a certificate is set up — see option 8), which operators bookmark on their phones. Close the window to stop it.

**Give the phones the machine name, not the IP address.** The launcher prints both. On a laptop the number changes when it rejoins the network, and every bookmark made from it stops working — which looks exactly like the application breaking. The name normally survives.

**If the phones cannot reach the PC at all**, it is almost always Windows Firewall blocking inbound port 8000. Nothing in the application can tell you this, because a blocked request never arrives. `Check_This_PC.bat` (or option 5 on the menu) looks for the rule and prints the one-line `netsh` command to add it from an Administrator prompt.

**On a laptop, set the power plan to never sleep on AC.** A closed lid stops the application, and with it the record. The main screen and the floor display will say so after about three hours during a shift, but not sleeping in the first place is better.

## Checking a release

From the development PC, with the virtual environment active, run the whole suite in one go:

```
venv\Scripts\python.exe dev\run_tests.py
```

It works out a scratch database from your own `.env` and runs every `tests\test_*.py` against it — never the real connection in `.env`, so a test run cannot touch production. See `tests/README.md` for what each group of tests covers and how to run just one.

## Rebuilding the frontend

After changing anything under `frontend/src`:

```
cd frontend
npm install
npm run build
```

`api/main.py` serves whatever is in `frontend/dist` — the backend won't pick up a source change until this is run.

## Rebuilding the documents

The handbook, one-pager, operator guide and update guide are HTML in `docs/`, rendered to PDF with a headless browser:

```
python dev\topdf.py                     docs\handbook.html       -> Formlabs_MES_Handbook.pdf
python dev\topdf.py operator_guide      docs\operator_guide.html -> Formlabs_MES_Operator_Guide.pdf
python dev\topdf.py onepager            docs\onepager.html       -> Resin_Pouring_One_Page.pdf
python dev\topdf.py update_guide        docs\update_guide.html   -> Formlabs_MES_Update_Guide.pdf
```

Copy the finished PDFs into `frontend/public/` afterward — that's what the app actually links to (the "?" on the operator form, the handbook line in the sidebar, the update guide in IT Admin); `npm run build` copies them into `frontend/dist` from there.

Figures under `docs/figs_print` and `docs/figs_op` are screenshots of the running application. **As of the FastAPI/React migration, `dev/shot_*.py` and `dev/reshoot_*.py` still drive the old Streamlit UI's selectors and port (8501)** and need rewriting against the new app before the figures can be regenerated — see the 4.00 entry in `CHANGELOG.md`. Once re-shot, they still go through `dev\print_prep.py`, which lifts the black floor of a dark screenshot so it prints without soaking the page.
