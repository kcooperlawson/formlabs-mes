# Resin Pouring — Production Logging

An hourly production record for the resin pouring station, kept by the operators on the phones they already carry. A web application (Streamlit) over a PostgreSQL database, run from one PC on the plant network.

It installs as a **logging system**: operators log, a manager reads the record and runs the system, and nothing has to be entered by anyone else first. One setting in IT Admin turns it into an **execution system** — work orders dispatched to stations and tracked against targets, with administration separated from the manager role. Nothing is lost switching either way.

The handbook in `docs/` describes what it does. This file is about getting it running.

## What is in this folder

Only the top level runs. Everything else is tooling that never leaves the development PC.

| Path | What it is |
|---|---|
| `Home.py`, `pages/`, `*.py` | The application. `Home.py` is the entry point. |
| `migrations/` | Database schema, as numbered Alembic migrations. Applied automatically on start-up. |
| `assets/`, `.streamlit/` | The logo, and the Streamlit configuration every launcher picks up. |
| `requirements.txt` | Python dependencies. `requirements-device-gateway.txt` is the optional machine-integration extras. |
| `.env` | This PC's configuration — the database login above all. Never committed; `.env.example` is the template. |
| `backups/` | Database dumps (`.sql`) taken by `Move_To_New_PC.bat` or from IT Admin. |
| `CHANGELOG.md` | What changed and why, newest first. IT Admin shows it in the sidebar. |
| `Setup_On_New_PC.bat` | First-time setup on a machine: virtual environment, dependencies, database, launch. |
| `run_mes.bat` | Day-to-day launch on a machine that has been set up. |
| `Move_To_New_PC.bat` | Packages a clean copy of the application — no tests, tooling or document sources — as one zip, with a database backup and optionally the Python packages for an offline install. |
| `tests/` | The release checks. Not shipped. |
| `dev/` | Screenshot, figure and document build scripts. Not shipped. |
| `docs/` | The handbook, one-page summary and operator guide — HTML sources, figures, and the finished PDFs. Not shipped; print from here. |

## First-time setup on a work PC

The PC needs **Python 3.11 or newer** (tick *Add python.exe to PATH* during install) and **PostgreSQL** (remember the password you give the `postgres` user). Both are ordinary installers from python.org and postgresql.org.

1. On the development PC, run `Move_To_New_PC.bat`. It takes a database backup, asks whether to include the Python packages for an offline install (say **Y** if the work PC may not reach the internet), and produces one zip file.
2. Copy the zip to the work PC and unzip it anywhere.
3. Open `.env` in Notepad and set `DB_URL` to that PC's Postgres login — the line looks like `postgresql://postgres:PASSWORD@localhost:5432/formlabs_mes`.
4. Run `Setup_On_New_PC.bat`. It builds the virtual environment, installs dependencies, checks the Postgres tools are present, creates the database, and asks one question if a backup is included: **restore it, or start clean**.

**Starting clean** is the default and the right choice for a plant that has not used this before. The application builds its own schema and seeds one administrator account, three placeholder pump stations and the downtime reason list. Sign in as **manager** with PIN **admin**, then from IT Admin: change that PIN, replace the placeholder pumps with the real ones, and add the operators. That is the whole setup.

**Restoring the backup** brings across everything from the PC the backup was taken on — every log, account and setting. Choose it when moving an established database between machines, not for a first install.

## Day to day

`run_mes.bat` starts the application. It prints the address to open — `http://<this PC's name or IP>:8501` — which operators bookmark on their phones. Close the window to stop it.

The Streamlit configuration in `.streamlit/config.toml` is committed on purpose: it is how the application is meant to run, and every launcher picks it up.

## Checking a release

From the development PC, with the virtual environment active:

```
python tests\test_workflow.py
python tests\test_ui.py
python tests\test_pages.py
python tests\test_links.py
python tests\test_boot_paths.py
python tests\test_roles.py
```

Every test builds a throwaway database and refuses to run against the connection in `.env`, so a test run cannot touch production.

Three more drive a real browser and need the application running on `localhost:8501` first — start it with `run_mes.bat` in another window:

```
python tests\smoke_browser.py         an operator's shift, desktop and phone
python tests\smoke_simple_mode.py     the logger-only shape, and who can administer
python tests\smoke_persistence.py     staying signed in, submit confirmations, the checksheet button
```

The browser ones matter more than their number suggests. Several defects have reached the floor that every headless test passed cleanly, because they only happen once a real browser is involved — and two of those only happened at phone size, which is the machine operators actually use.

## Rebuilding the documents

The handbook, one-pager and operator guide are HTML in `docs/`, rendered to PDF with a headless browser:

```
python dev\topdf.py            docs\handbook.html        -> docs\Formlabs_MES_Handbook.pdf
python dev\build_opguide.py    generates docs\operator_guide.html from its script
```

Figures under `docs/figs_print` and `docs/figs_op` are screenshots of the running application, taken by the `dev\shot_*.py` and `dev\reshoot_*.py` scripts and then run through `dev\print_prep.py`, which lifts the black floor of a dark screenshot so it prints without soaking the page. Re-shoot a figure when the screen it shows changes; a printed document does not update itself.
