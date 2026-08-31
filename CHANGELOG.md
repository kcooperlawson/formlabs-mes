# Formlabs MES — Changelog

Running log of what's changed in the app, newest first. One entry per day I worked on it. These were long days (6-8 hours each), so the bullets below go a level deeper than a headline — most of these "one-liners" were really a handful of related fixes/decisions that belong together.

---

## 3.8 — Monday, August 31, 2026
**Cartridge lot verification, per-station checklists, a test suite, and structural hardening**

- Closed the hole behind the lot mix-ups on the floor. The pouring form used to auto-fill the run's lot number into an editable box, which meant the form answered its own question — an operator could log a full hour without ever turning a cartridge over. The expected lot is now masked and the operator types what's actually stamped on the bottom (`L-` lot and `E-` expiry), so the check can't be satisfied from what's on screen. Comparison is normalized, so typing the stamp verbatim (`L-2411A0742`) matches a run whose lot the manager entered bare (`2411A0742`), and near-misses still fail.
- A mismatch never dead-ends the operator: it throws a full-width STOP, then requires a cause and details before the log will submit. The log saves flagged, carries the lot that was *physically* in the cartridge rather than the one the run expected, and gets an auto-prepended note explaining the discrepancy. Deliberately let the run's progress bar not move in that case — a mismatch that still produces a correct-looking count is a mismatch nobody notices. Also added a "wrong cartridge — pulled it, nothing poured" button, because a catch is data worth having and there was previously nowhere to put it.
- Photo of the stamp is required on every full check (camera or upload), filed under `uploads/lot_labels/` and shown next to each flag in the manager view. It's evidence, not the gate — the typed comparison is what blocks, so a bad photo can never stop a station.
- Built a fast path so a per-log check doesn't decay into a reflex tap: full check on the first log of a shift, on any change of run/lot/resin/station, after 4 hours, and on every 10th log regardless; a one-tap confirm otherwise. A mismatch clears the fast path so the next log starts over.
- RPS is exempt end to end — bulk jugs are poured without lot labels, so the gate never renders on that format. Packing is untouched.
- Deliberately did NOT ask the operator to type the `E-` expiry printed under the lot. One field is all of their time this check is worth, and a second one every hour is exactly how a gate decays into a reflex tap. The expiry is in the photo either way, so the tolerant parser and the `entered_expiry` / `expiry_status` columns are already written and tested — the offline OCR pass fills them in later without costing a keystroke at the station.
- Corrected the stamp format after confirming it on an actual cartridge: the base reads `L-<lot>` and `E-<date>`, not `L:` / `E:`. No functional impact — `normalize_lot()` already stripped `:`, `-` or `#` as the prefix separator, so every correctly-typed lot would have matched either way — but every on-screen label, caption and flag note said the wrong thing, which is exactly the kind of detail that makes an operator distrust the rest of the screen. Labels, captions, the fast-path confirmation, the mismatch note and the blocker text all now show `L-`. Both forms stay accepted and are covered by the test suite, since the colon form has been seen printed too.
- New `lot_verifications` table (Alembic `0003`) records every check, pass or fail, with the photo and both codes; `production_logs.verify_status` is denormalized alongside it so dashboards can filter without a join. New manager page (`Mgr_Lot_Verification.py`) with the flagged feed, per-operator full-vs-one-tap coverage, an expiry watch, and CSV export.
- Made the startup checklist per-station instead of once per day per shift. A checklist certifies the condition of the pump you're standing at — bins staged, station clean — so an operator who gets moved to a different pump has certified nothing about it and now gets asked again. The lock screen grew a "which pump are you starting at?" picker that writes to the same `h_pump` session key the pouring tab uses, so the station is answered exactly once and follows through to logging. The Step 1 cleanliness cookie and its in-session flag are both keyed by station too, so switching pumps mid-checklist can't carry the previous station's photo over.
- `daily_checklists` gained `pump_station` / `pump_station_id` (Alembic `0004`), both nullable. Rows written before the column existed count for any station on the date they were made — deliberately, so shipping this didn't re-lock every operator who'd already done their checklist that morning. From the next day on every row carries a station and the per-pump rule applies in full.
- Built a real test suite under `tests/` and pointed it at a throwaway Postgres (never `.env`'s — `_boot.py` refuses if the URLs match). Three scripts: `test_workflow.py` applies all four migrations to an empty database, checks the result against `models.py` table by table, then simulates a shift — manager creates three work orders, operators clear per-station checklists, pour clean logs, a fast-path log, a mismatched cartridge, a pulled cartridge, an unassigned-run log and an RPS log, plus downtime and packing — and recomputes every number the UI displays from the raw rows (63 assertions, all passing). `test_ui.py` drives the actual operator page headless with Streamlit's `AppTest`: terminal locks with no checklist, unlocks when cleared, gate blocks an untouched form, wrong lot raises the stop screen and demands a reason, right lot goes green including a messy `l: 2411a0742` transcription, RPS bypasses (28 assertions). `test_pages.py` renders all 18 pages and reports any that raise.
- **Found and fixed: the run card was printing the lot the gate was hiding.** The active-run panel sits directly above the verification section and showed `Lot: 2411A0742` in plain text, so an operator could read the answer off the screen without ever touching the cartridge — the entire gate was decorative. Only caught because the UI test asserts the expected lot appears nowhere on the rendered page. Now masked to `•••••••••` for operators and packers; managers and admins still see the real value, since they're the ones comparing it to what got typed.
- **Found and fixed: eight pages would `NameError` on a theme change.** `Mgr_Cleanliness`, `Mgr_Floor_Comms`, `Mgr_Google_Sync`, `Mgr_Resin_Canvas`, `Mgr_Roster`, `Mgr_Scrap_Intel` never imported `datetime`/`timedelta`, and `Mgr_Assigned_Runs` / `Mgr_Historical` each imported only half of what they use — but the only call site is `cookie_manager.set(expires_at=datetime.now() + timedelta(days=365))` inside the theme-change branch, so it only blew up when someone actually switched theme from one of those pages. Pre-existing; `pyflakes` found all eight in one pass.
- **Found and fixed: `Mgr_Log_Management` crashed whenever 1–9 records matched.** Both row-count inputs used `value=min(100, len(matches))` against `min_value=10`, so a narrow filter (or a quiet day) made the value illegal and took the page down. Now floored at 10.
- **Found and fixed: the TV dashboard was a hot loop.** `Tv_Dashboard.py` ended with a bare `st.rerun()` under a comment promising a 10-second wait that wasn't there — so it re-executed as fast as the machine allowed, several full-table queries per pass, continuously, on a screen that's up all shift. Added the `time.sleep(10)` its own comment describes.
- **Found and fixed: a CDN fetch could take down the operator terminal.** `Operator_Form.py` called `requests.get()` for the run-complete Lottie animation at page-script level with no timeout and no try/except, on every single rerun. A slow CDN, a proxy, or a floor PC that lost its internet would hang the terminal and then raise before one widget rendered. Now guarded, given a 3s timeout, and fetched once per session instead of on every keystroke.
- **Closed the cross-site scripting hole in the raw-HTML blocks.** The app renders a lot of its cards with `unsafe_allow_html=True` and f-strings, which drops database values straight into markup — and most of those values are typed by people on the floor: operator names, note fields, chat messages, lot codes, audit types. Added an `esc()` helper (`html.escape`) in `utils.py` and applied it to 28 interpolation points across 10 files. Scoped it with an AST pass rather than a find-and-replace, so only expressions genuinely inside an `unsafe_allow_html` call were touched — Streamlit escapes ordinary `st.markdown` and `st.caption` itself, and escaping there would have shown entity codes to the user. Worth noting the non-security half of this: a note containing a `<` was already breaking the card it rendered in, so this fixes a live layout bug too.
- **Added read caching, and put it in the right layer.** There was almost none — four cached calls in `Home.py` and zero in `crud.py` — so every keystroke in a number box re-ran the whole script and re-queried Postgres for the resin list, pump list, operator list and plant settings. Cached the seven reference reads, deliberately leaving production logs, runs and lot verifications uncached since those have to be correct the instant after a write. Put the whole layer in `database.py` rather than `crud.py`, so the data layer stays free of any Streamlit import and the headless gateway process can keep importing it unchanged. The sixteen configuration writers are wrapped to clear the caches they invalidate, so an equipment or settings change shows up immediately instead of after a TTL — the TTL is only a backstop for edits made in another browser session.
- **Extracted the page shell — 1,335 duplicated lines gone.** Eleven manager pages each carried their own copy of the same ~131-line navigation bar, sidebar router and account popover. That duplication was the direct cause of today's theme-change crash: the block had been pasted eight times and half the copies were missing a `datetime` import, so the bug existed eight times over. Now one `ui_shell.py` with a `render_shell()` call, and each page's 131 lines is four. Deliberately a straight lift rather than a rewrite — same widgets, same keys, same cookie-manager key, same order — and generated from the canonical block programmatically instead of retyped, so there was no chance of transcription drift. Verified by element count: every one of the 18 pages renders exactly the number of elements it rendered before. The one page that never had the account popover (`Mgr_Log_Management`) keeps not having it via a flag, including the sidebar spacer that sat underneath it, so the refactor changes nothing visible anywhere. Drop that argument whenever you want that page to match the rest.
- **The shell extraction nearly introduced a regression, and static analysis caught it.** `Mgr_Floor_Comms` used `get_avatar_path`, which the deleted block had been importing on its behalf. The page-render sweep still reported it clean, because that line only executes when chat messages exist and the test database had none — it would have thrown a `NameError` for the first manager to open a conversation with an operator. `pyflakes` found it in seconds. Worth remembering as a habit: after moving code, an undefined-name sweep catches what rendering cannot, because rendering only exercises the branches your test data happens to reach.
- **Removed the stamp photo from the lot check.** On a bad network segment in the building the upload was taking 20-30 seconds, on every full check. That is the wrong trade: the photo was never the gate — the typed comparison is what blocks a wrong cartridge — so the check itself is exactly as strong without it, while half a minute of standing still per check is precisely the friction that teaches operators to resent a control and look for ways around it. What is lost is the evidence trail for a disputed flag and the planned OCR cross-check, which needed stored images. The `photo_filename` column stays on the table and the manager feed still renders a photo where a historic check has one, so nothing already captured is lost.
- **Brought the photo back on the mismatch branch only.** Evidence is worth thirty seconds exactly once: on a flagged pour, which is the check somebody reviews later and the operator may have to defend — and by then they are already stopped, talking to their lead, so the upload costs nothing the situation was not costing anyway. A clean check stays a single field and a single tap. Deliberately NOT required to pull a cartridge and log the catch: the safe action must never be slower than the risky one, or the design quietly argues for pouring. Covered both ways in the test suite — a clean check is asserted never to ask for a photo, a mismatch is asserted to demand one.
- Left the OCR cross-check for later: `ocr_lot` / `ocr_conflict` columns are already in the schema, so a local offline OCR pass over the stored photos can start flagging entries that don't match their own picture without another migration.

## 3.7 — Sunday, August 30, 2026
**Machine integration, operator fixes, log cleanup**

- Started building a real Device Gateway — a protocol-agnostic backend for wiring pump/filling controllers, bench scales, and eventually label printers straight into the app. Didn't want to hardcode a protocol, so each machine gets a row in a `devices` table and the actual polling logic lives in a small adapter behind one shared interface (`connect()` / `poll()` / `close()`). Shipped with six adapters out of the gate — Modbus TCP, Modbus RTU, OPC-UA, MQTT, Serial ASCII, HTTP/REST — so it can pick up whatever the ULINE scales or the pump HMI actually speak once I test against them. Readings write through the same `add_hourly_log()` path an operator's manual entry uses (tagged `"Automated Gateway"`), so none of the existing business logic in Analytics or the run-progress tracking needed to change, plus a raw `device_readings` table for full telemetry (fault codes, uptime, weight curves) separate from what hits production logs. Also wrote the auto-discovery piece so the gateway process can run on a different floor PC than Postgres and still find the database over the local network without hand-editing a config file.
- New admin page (`Device_Registry.py`) for finding, registering, test-connecting, and tag-mapping that equipment — including a live probe for testing a regex against raw serial output before committing a tag map.
- Fixed auto-scroll on the operator logging page — it had stopped working.
- Fixed a bug where an operator's logged bottle counts weren't updating their assigned run's progress.
- Fixed the progress bar so it actually fills up as production gets logged — the underlying numbers were already right, the bar itself just wasn't reflecting them.
- Pulled the leftover default Streamlit sidebar (`stSidebarNav`) so only the custom-built one shows — had to hide it with CSS on every single page, not just once.
- Reworked station assignment so multiple operators can log against the same reactor/run without a manager creating a duplicate assignment per person. Deliberately decoupled "which run shows on your screen" from `AssignedRun.assigned_operator` — it now follows whichever pump station you've selected, so any number of operators pointed at the same station see and log against the exact same run automatically.
- Fixed a bug where manually adjusting a run's progress could silently get reverted on the next page refresh.
- Closed a hole where an admin testing the app as an operator could accidentally downgrade their own account's permissions in the process.
- Fixed the live shift-status indicator — it was sometimes showing a shift as active for hours after it had actually ended.
- Cleaned up the live shift-progress card and made it only render when it's actually relevant.
- Added a Log Management page so managers can find and delete bad or test log entries, downtime entries, and completed work orders — including a bulk-cleanup mode that's disabled until you literally type "DELETE" into a confirmation box, so nobody clears real data with a stray click.

---

## 3.6 — Saturday, August 29, 2026
**Reliability, security, profile pictures**

- Overhauled how the app handles database migrations (Alembic, with a proper baseline schema instead of hand-run SQL) — safer going forward, way less risk of an upgrade silently breaking a table.
- Fixed a bug in Analytics where renaming an operator could split their production history across two records. Root cause was that logs only ever stored the operator's name as a plain string — renamed them and every old log became orphaned from every new one. Fixed by adding real `operator_id` foreign keys alongside the legacy name columns (kept those for backward compatibility and for system-generated rows with no matching user), so history stays attached to the person, not the string.
- Fixed scheduled backups occasionally targeting the wrong database.
- Added actual error logging (`app_logger.py`) — rotating log file plus console output, with a guard so Streamlit's constant reruns don't stack duplicate log handlers every time a page re-executes. Before this, a bunch of broad `except` blocks across the app just swallowed failures silently; now they still fail safe for whoever's on the floor, but I can actually see what happened.
- Added account lockouts after 5 failed login attempts (15-minute lock), with a way for IT to unlock an account instantly instead of waiting it out.
- Migrated PINs to salted bcrypt hashes app-wide, including a compatibility path for legacy accounts that predate bcrypt so they get a clear "needs an IT admin reset" message instead of a confusing failed login.
- Fixed profile pictures not showing up in the sidebar, chat messages, and the feedback inbox. Turned out to be a few different join paths (some resolving avatars by name, some pre-dating the FK backfill entirely) that all needed to agree — old rows without a matching user now just render with no avatar instead of breaking.
- Reorganized the codebase for easier long-term maintenance. No visible change, just less painful to work in.

---

## 3.5 — Friday, August 28, 2026
**Login and session stability**

- Added a theme picker on the login screen itself, before you're even authenticated — the selector writes to session state and the CSS applies immediately, then gets replaced by your saved preference once you actually log in.
- Fixed a bug where some users could get stuck in a loop of being logged out and back in unexpectedly.
- Made the nav menu and account settings consistent across every page — they'd drifted since the last few pages were added at different times.
- Gave IT Administrators the same equipment-management permissions as plant managers, so they're not blocked from fixing floor equipment issues.

---

## 3.4 — Thursday, August 27, 2026
**Admin tools and navigation rebuild**

- Rebuilt page-to-page navigation to actually branch on role — admin gets a 6-link top bar (adds IT Admin), manager gets 5, operator gets a stripped-down set, instead of one nav trying to serve everyone and just hiding links that didn't apply.
- Added a full IT Admin console for creating accounts, managing equipment, and recovering from problems without needing database access directly.
- Made login sessions more resilient — fewer random logouts.
- Standardized account settings, text sizing, avatar upload, and the feedback tool so they behave the same on every page instead of each page having its own slightly-different version.
- Fixed sidebar visibility issues in Analytics and made the charts adapt better to different screen sizes.

---

## 3.3 — Wednesday, August 26, 2026
**Security and confidentiality**

- Locked down every page with an actual auth/role guard at the top (`if not authenticated or role not allowed: stop()`), so a page can't be reached just by guessing or typing its URL directly — before this, the nav hid links but the pages themselves weren't checking who was asking.
- Made account settings and menus usable on tablets and phones on the floor.
- Cleaned up what gets exported to outside systems — the Google Sheets sync now builds its own payload and explicitly strips internal-only columns before anything leaves the app, instead of exporting the raw dataframe.
- Moved the database connection string and other sensitive settings out of the code entirely and into environment config (`.env` / `os.getenv`) — nothing sensitive sits in a file that could get shared or committed by accident anymore.
- Moved confidential resin recipes (spec weights, min/max tolerances, multipliers) out of the code and into their own secured table, with a dedicated manager page (Resin Canvas) to edit them directly instead of touching source.

---

## 3.2 — Tuesday, August 25, 2026
**Compliance and reconciliation**

- Added required pre-shift safety/compliance checklists — the operator page now hard-stops rendering (`st.stop()`) until every manual verification item is checked, so there's no way to skip past it.
- Improved tank/reactor volume tracking with a real reconciliation flow — a manager or operator enters a visual fill percentage against a reactor, and it's checked against what's already been logged for that resin rather than just overwriting a number.
- Added a "Mid-Shift Role & Station Transfer" tool so managers/operators can reassign role and shift on the fly, with the UI updating immediately on submit instead of needing a refresh.
- Added one-click database backups (`.sql` dumps to a dedicated backup folder) so plant data can be restored if something breaks.

---

## 3.1 — Monday, August 24, 2026
**Analytics, design, communication**

- Launched the Analytics Hub — dashboard for downtime trends, operator performance, and live shift progress.
- Reworked the app's look — multi-theme, smoother visuals and interactions.
- Added automatic PDF shift-handover reports (generated with FPDF) that get emailed out automatically to whoever's on the distribution list.
- Added a live chat feature (`floor_messages` table) so plant leadership and floor staff can message each other directly, with manager replies flagged separately from operator messages.

---

## 3.0 — Sunday, August 23, 2026
**The foundation**

- Rebuilt core data storage to use a real Postgres database instead of ad hoc files — laid out the core schema (production logs, downtime, assigned runs, reactors, resin specs, pump stations, cleanliness audits) that everything since has built on top of.
- Set up the basic navigation between the operator, manager, and live-tracking sections.
- Added secure photo storage for cleanliness checks and incident reports, saved server-side instead of floating around as email attachments or phone photos.
