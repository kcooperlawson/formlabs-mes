"""Load the operator terminal in a real browser with work orders switched off.

The headless AppTest run in test_ui.py asserts the same behaviour, but it
renders the script rather than the page: it cannot see a heading that is
present but empty, a card that collapsed to a grey box, or a layout that lost
a column. This is the screen a manager would be shown on day one, so it is
worth looking at with a browser.

The one that matters most is the last: the demo database has open runs in it,
and a plant that has switched work orders off must not have a pour stopped by
a run its operators have no way to see.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/root/mes")
BASE, USER, PIN = "http://localhost:8501", "keagan", "1234"
# A real manager account, to check the half of the rule that is a refusal.
MANAGER = "mvega"

FAILS, CHECKS = [], 0


def check(label, got, exp=True):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")
    else:
        print(f"  ok  {label}")


async def main():
    import crud, database as db
    saved = bool(db.get_plant_settings().get("simple_mode", True))
    db.update_plant_settings({"simple_mode": True})

    open_runs = 0
    runs = crud.get_assigned_runs_df()
    if not runs.empty:
        open_runs = int(runs["status"].isin(["Active", "Pouring", "Queued"]).sum())
    print(f"  {open_runs} open run(s) in the database, all of them hidden")

    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                      device_scale_factor=2, is_mobile=True,
                                      has_touch=True)
            pg = await ctx.new_page()
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(5000)
            if await pg.locator('input[type="password"]').count():
                await pg.locator('input[type="text"]').first.fill(USER)
                await pg.locator('input[type="password"]').first.fill(PIN)
                await pg.wait_for_timeout(400)
                await pg.get_by_text("INITIALIZE SESSION").first.click()
                await pg.wait_for_timeout(13000)

            for label in ("Operator", "Workstation"):
                try:
                    await pg.get_by_text(label, exact=False).first.click(timeout=7000)
                    await pg.wait_for_timeout(12000)
                    break
                except Exception:
                    continue

            body = await pg.inner_text("body")
            check("the operator terminal loaded", "Log Hourly Pouring" in body)
            check("no run cards headed by a manager's name",
                  "Active Assigned Production Runs" in body, False)
            check("no leftover 'No production runs in database'",
                  "No production runs" in body, False)
            check("nothing sends the operator to find a manager",
                  "Plant Manager" in body, False)
            check("focus mode is not offered", "Focus mode" in body, False)
            check("the log itself is still the page",
                  "Station & Material" in body or "Pump Station" in body)

            # Point it at the station, resin and format of a real open run -
            # the exact combination that WOULD raise a stop screen if the page
            # could still see runs it is not allowed to show.
            row = runs[runs["lot_number"].astype(str).str.strip() != ""].iloc[0]
            station = str(row["pump_station"])
            fmt, resin = str(row["cartridge_type"]), str(row["resin_type"])
            fmt_label = {"V1": "V1 (1L Cartridge)", "V2": "V2 (1L Cartridge)",
                         "RPS": "RPS (5L Bulk Jug)", "Pigment": "Pigment"}.get(fmt, fmt)

            async def pick(label, value):
                combo = pg.locator(
                    f'div[data-testid="stSelectbox"]:has-text("{label}")').locator("input").first
                await combo.click(); await pg.wait_for_timeout(600)
                await combo.fill(""); await combo.type(value, delay=40)
                await pg.wait_for_timeout(900); await combo.press("Enter")
                await pg.wait_for_timeout(6000)

            for lab, val in (("Pump Station", station), ("Container Format", fmt_label),
                             ("Resin Formulation", resin)):
                try:
                    await pick(lab, val)
                except Exception as e:
                    print(f"  !! {lab}: {e}")

            body = await pg.inner_text("body")
            check("the lot is still asked for", "lot on the" in body)
            check("and still points at the label on the bottom",
                  "lot label on the bottom" in body)
            check("no notice about a run that did not match",
                  "No open run matches" in body, False)

            field = pg.locator(
                'div[data-testid="stTextInput"]:has-text("bottom label")').locator("input").first
            await field.fill("L-0000WRONG")
            await field.press("Enter")
            await pg.wait_for_timeout(8000)
            body = await pg.inner_text("body")
            check("a hidden run cannot stop a pour it was never shown for",
                  "DO NOT POUR" in body, False)
            check("and the code is simply recorded",
                  "ecorded" in body)

            os.makedirs("/root/mes/tests/smoke_shots", exist_ok=True)
            await pg.screenshot(path="/root/mes/tests/smoke_shots/simple_mode_form.png",
                                full_page=True)

            # The floor display is the other screen that used to announce the
            # absence of work orders, all shift, to a room.
            await pg.goto(BASE + "/Tv_Dashboard", wait_until="networkidle")
            await pg.wait_for_timeout(12000)
            tv = await pg.inner_text("body")
            check("the floor display says nothing about work orders",
                  "Work Orders" in tv, False)
            await pg.screenshot(path="/root/mes/tests/smoke_shots/simple_mode_tv.png",
                                full_page=True)
            await ctx.close()

            # --- the manager IS the administrator, in this mode --------------
            # A plant running this as a record has one person in charge of it.
            # Both halves are checked in a browser rather than only against
            # crud.can_administer, because the rule is applied at eleven call
            # sites and it is the page gate, not the predicate, that decides
            # whether somebody actually gets in.
            mctx = await b.new_context(viewport={"width": 1440, "height": 950})
            mpg = await mctx.new_page()
            await mpg.goto(BASE, wait_until="networkidle")
            await mpg.wait_for_timeout(5000)
            await mpg.locator('input[type="text"]').first.fill(MANAGER)
            await mpg.locator('input[type="password"]').first.fill(PIN)
            await mpg.wait_for_timeout(400)
            await mpg.get_by_text("INITIALIZE SESSION").first.click()
            await mpg.wait_for_timeout(13000)

            body = await mpg.inner_text("body")
            check("a manager is offered the console in logging mode",
                  "IT Admin" in body)

            await mpg.get_by_text("IT Admin", exact=False).first.click()
            await mpg.wait_for_timeout(14000)
            body = await mpg.inner_text("body")
            check("and is let in", "IT Administrator Console" in body)
            check("not refused", "Access Denied" in body, False)
            check("and is told why they have it",
                  "no separate IT role" in body)
            check("the console offers what a plant with no IT person needs",
                  "System Access & User Roster" in body)
            await mpg.screenshot(path="/root/mes/tests/smoke_shots/simple_mode_manager_admin.png",
                                 full_page=True)

            await mctx.close()

            # --- and is refused the moment the plant becomes an execution one -
            # The wait is the settings cache, not padding. database.py caches
            # plant settings for 60 seconds and clears that cache after its own
            # writes - but this test writes from a different process, so the
            # server keeps serving the old mode until its copy expires. Acting
            # sooner would be testing the cache and passing for the wrong
            # reason. In the application this does not arise: the write happens
            # inside the server that holds the cache.
            #
            # A fresh sign-in rather than a reload of the console: reloading a
            # Streamlit page mid-session races the cookie round trip, and a
            # bounce to the sign-in screen is indistinguishable from a refusal
            # in the page text. Signing in again is also what the manager would
            # actually do next.
            db.update_plant_settings({"simple_mode": False})
            await asyncio.sleep(63)

            xctx = await b.new_context(viewport={"width": 1440, "height": 950})
            xpg = await xctx.new_page()
            await xpg.goto(BASE, wait_until="networkidle")
            await xpg.wait_for_timeout(6000)
            body = await xpg.inner_text("body")
            check("the sign-in screen follows the mode", "SCADA" in body)
            check("and drops the logging wording", "POURING" in body, False)

            await xpg.locator('input[type="text"]').first.fill(MANAGER)
            await xpg.locator('input[type="password"]').first.fill(PIN)
            await xpg.wait_for_timeout(400)
            await xpg.get_by_text("INITIALIZE SESSION").first.click()
            await xpg.wait_for_timeout(14000)
            body = await xpg.inner_text("body")
            check("the same manager is not offered the console in execution mode",
                  "IT Admin" in body, False)

            # And is refused it by the page itself, not only by the missing
            # link - a URL typed into the address bar has to hit the same rule.
            await xpg.goto(BASE + "/Admin_Panel", wait_until="networkidle")
            await xpg.wait_for_timeout(14000)
            body = await xpg.inner_text("body")
            check("nor let in by typing the address",
                  "Save Operational Parameters" in body, False)
            check("and the roster is not rendered behind the refusal",
                  "System Access & User Roster" in body, False)
            await xpg.screenshot(path="/root/mes/tests/smoke_shots/execution_mode_refusal.png",
                                 full_page=True)
            await xctx.close()

            db.update_plant_settings({"simple_mode": True})
            await b.close()
    finally:
        db.update_plant_settings({"simple_mode": saved})
        print(f"  restored simple_mode={saved}")


asyncio.run(main())
print("\n" + "=" * 62)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} SIMPLE MODE CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} SIMPLE MODE BROWSER CHECKS PASSED")
raise SystemExit(1 if FAILS else 0)
