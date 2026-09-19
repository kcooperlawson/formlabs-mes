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
| `run_mes_portable.bat` | The day-to-day launch: the app plus its own bundled database, no PostgreSQL install needed. `START_HERE.bat` option 3 calls this unless `.env` names a database of its own. |
| `Repair_Updater.bat` | Carried to a PC too old to accept an update (it stops on "the backup failed"). Signature-checked, replaces only the updater's own files. One-time, see the Updates section below. |
| `START_HERE.bat` | The one entry point on a work PC — a menu covering install, day-to-day launch (either against this PC's own PostgreSQL install or, via the file above, a bundled database), diagnostics, packaging, updates, the HTTPS certificate, and creating an admin login on either database. |
| `Check_This_PC.bat` | Is this PC ready to run the plant? Checks Python, the packages, Postgres, the schema, the backup tools, disk, the port and the firewall — takes a real backup to prove backups work — and prints the address to give the phones. Run it before carrying a machine to the floor and again after a move. |
| `Move_To_New_PC.bat` | Packages a clean copy of the application — no tests, tooling or document sources — as one zip, with a database backup and optionally the Python packages for an offline install. |
| `tests/` | The release checks. Not shipped. |
| `dev/` | Screenshot, figure, document-build and release-packaging scripts. Not shipped. |
| `docs/` | The three documents — the handbook (for management), the operator guide (for the floor) and the one-page summary — as HTML sources, figures and finished PDFs. Not shipped; print from here. |

## First-time setup on a work PC

The PC needs **Python 3.11 or newer** (tick *Add python.exe to PATH* during install). That is the whole list — the database comes with the application.

1. On the development PC, run `Move_To_New_PC.bat`. It takes a database backup, asks whether to include the Python packages for an offline install (say **Y** if the work PC may not reach the internet), and produces one zip file.
2. Copy the zip to the work PC and unzip it anywhere.
3. Run `START_HERE.bat` and choose **1** (Install the MES / Logger). It builds the virtual environment and installs the dependencies.
4. Choose **3** to start it. The first start creates the database in `pgdata\` next to the project, seeds three demo accounts, and asks right there on the console for a real admin login to replace the demo one.
5. From the same menu, choose **5** to diagnose the PC. One page saying whether this machine is ready, and if not, exactly what to type. It also prints the address to give the phones.

**The database is bundled** (`pgserver`, a real PostgreSQL whose binaries ship inside the Python package) and lives in `pgdata\` next to the project. Nothing system-wide, no installer, no admin rights, no password to invent, and nothing for IT to approve. Backups, restores, updates and the Device Gateway all work against it exactly as they do against an installed PostgreSQL.

**A PC that already has its own PostgreSQL** can still use it: option **14** installs against it, and `.env`'s `DB_URL` then points at it. Option **3** uses whichever of the two this PC has — a real `DB_URL` in `.env` wins, otherwise the bundled database — so the same menu works on both kinds of PC. Option **9** always uses the bundled one.

**A Device Gateway on another PC** needs to reach the database, and the bundled one is private to its PC by default. Option **15** gives it a fixed port and a password, and prints the firewall rule and the one `.env` line the gateway PC needs. See `README_DEVICE_GATEWAY.md`.

**Starting clean** is the default and the right choice for a plant that has not used this before. The application builds its own schema and seeds three demo accounts — an administrator (**manager** / PIN **admin123**) and two operators (**operator** / **sasha**, PIN **1234**) — plus three placeholder pump stations and the downtime reason list. Set up a real admin login before putting this on the floor: option **10** on `START_HERE.bat`'s menu (**11** for the bundled-database option) prompts for one and retires the demo admin once it exists. From there, sign in as that admin and, from IT Admin: replace the placeholder pumps with the real ones and add the operators. That is the whole setup.

**Restoring the backup** brings across everything from the PC the backup was taken on — every log, account and setting. Choose it when moving an established database between machines, not for a first install.

**Restoring is checked, not assumed.** Every backup carries a manifest of what was in the database when it was taken, and setup compares it against the restored database row by row before letting you go on. If anything came across short it stops and says so — the machine the backup came from still has the data, so nothing is lost as long as nothing new is written on the new PC first.

## Day to day

`START_HERE.bat` is the one thing to double-click. Choose **3** to start the MES — it uses the bundled database, or this PC's own PostgreSQL if `.env` names one. It prints the address to open, `https://<this PC's name or IP>:8000` (plain `http://` until a certificate is set up — see option 8), which operators bookmark on their phones. Close the window to stop it.

**Give the phones the machine name, not the IP address.** The launcher prints both. On a laptop the number changes when it rejoins the network, and every bookmark made from it stops working — which looks exactly like the application breaking. The name normally survives.

**If the phones cannot reach the PC at all**, it is almost always Windows Firewall blocking inbound port 8000. Nothing in the application can tell you this, because a blocked request never arrives. `Check_This_PC.bat` (or option 5 on the menu) looks for the rule and prints the one-line `netsh` command to add it from an Administrator prompt.

**On a laptop, set the power plan to never sleep on AC.** A closed lid stops the application, and with it the record. The main screen and the floor display will say so after about three hours during a shift, but not sleeping in the first place is better.

## Updating a plant PC

Build the release here first: `cd frontend && npm run build`, bump `VERSION`, then

```
venv\Scripts\python.exe dev\make_update.py --notes "what changed"
```

which writes `dist\mes_update_<version>.zip` — the whole application, signed, and it applies to **any** older version. Then pick whichever route suits the PC:

| Route | How | What you get |
|---|---|---|
| **By file** | Copy the zip into the PC's `updates\` folder → `START_HERE.bat` option **7** | Database backup first, proof it boots after, automatic rollback if not |
| **From your own server** | `START_HERE.bat` option **16** here; the plant PC points at it in IT Admin → Updates | Same, plus a list of every version it offers — install any of them, including going back |
| **From GitHub** | `dev\make_update.py --publish` | Same again; a private repo needs a read-only `GITHUB_RELEASE_TOKEN` on the plant PC |
| **Straight copy** | `dev\make_dropin.py` → extract `dist\mes_files_<version>.zip` over the folder | No backup, no rollback, no signature check — but nothing to go wrong either |

**Hosting it yourself** avoids GitHub entirely. On this PC, `START_HERE.bat` option **16** (it asks for a port and an optional password). It serves `dist\` read-only — a listing and the packages themselves, nothing else on this machine.

On the plant PC there is nothing to edit: **IT Admin → Updates → Update source**, type the address (`192.168.0.15`, or a full one if it isn't on the default port 8443) and the password if you set one, and Save. It writes to that PC's own `.env`, which no update overwrites.

The Updates tab then lists **every** version that server is offering, newest first — which one is running, what's in each, and when it was published. Newer ones install with one button; older ones are offered as *Go back to this*, for the day a release turns out to be wrong. Going back takes the files back, not the database: a schema change made by a newer version stays made, which is why it asks first and takes a backup either way.

For that to work from another network you need three things: the port forwarded on your router to this PC, an address that doesn't move (a dynamic-DNS name, since home IPs change), and the far end's firewall allowing outbound to that port — 443 is the one most likely to pass. If your ISP puts you behind CGNAT, port forwarding won't work at all and a tunnel (Tailscale, Cloudflare Tunnel) is the way round it.

The connection does not have to be trusted: the package is signed and every file checksummed, and a plant PC refuses anything that isn't signed by this project's key. A tampered copy fails on arrival — which is why plain HTTP is acceptable here, and why `--token` is about keeping strangers out rather than protecting the update.

**A PC on 4.07 or older** stops with "the backup failed" and won't update: its updater can't find the bundled database to back up. Carry `Repair_Updater.bat` over with the package, run it once, then apply the update normally. (Or use the straight-copy zip, which sidesteps it.)

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
