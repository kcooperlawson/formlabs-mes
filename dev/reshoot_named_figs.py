"""Re-take the handbook figures that still show a real person's name.

The demo account these were shot under used my own first name. That has no
business in a document that leaves the building: these are illustrations of
the system, not of me, and a reader who sees a real name reasonably wonders
whether they are looking at live production data. The seed and every shot
script now use a placeholder, so this re-takes the figures that predate that.

Only the ones that actually show the sidebar. Figures cropped to a table or a
form section carry no name and are left alone - re-shooting a figure that was
already correct is how a document ends up with two visual styles in it.

Two things worth knowing about how this navigates. It ticks "remember this
device" at sign-in, because without a cookie a full page navigation drops the
session and every goto lands back on the login screen. And it goes by URL
rather than by clicking through the interface: half these pages are reached
from links inside other pages, and a chain of clicks is a chain of things that
break silently the next time a label is reworded. This script exists because
exactly that happened to two of its neighbours.

Shot at 1500 CSS pixels with a device scale factor of 2, which is what the
figures re-taken this week use. The old set was 1700 wide at scale 1, so these
are sharper in print at the same page width. Each height is chosen to match
the aspect of the figure it replaces, so nothing on the page reflows.
"""
import asyncio
import os
import subprocess
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "figs_print")
PREP = os.path.join(ROOT, "dev", "print_prep.py")
BASE, PIN = "http://localhost:8501", "1234"

# name, URL path, height in CSS px, optional (anchor text, pixels to scroll up)
# Heights come from the aspect of the figure each one replaces.
SHOTS = [
    # name, URL path, height, optional (anchor text, scroll), text that proves
    # the right page is on screen.
    ("01_scada",        "/",                     950, None,                        "TIME HORIZON"),
    ("01b_scada_lower", "/",                     950, ("POURING OPERATIONS", -40),  "POURING OPERATIONS"),
    ("05_lotverify",    "/Mgr_Lot_Verification", 950, None,                        "Cartridge Lot Verification"),
    ("06_scrap",        "/Mgr_Scrap_Intel",      795, None,                        "Quality Ops Canvas"),
    ("08_historical",   "/Mgr_Historical",       788, None,                        "Historical Plant Analytics"),
    ("17_logmgmt",      "/Mgr_Log_Management",   950, None,                        "Log Management"),
]

# Work orders are hidden unless the plant dispatches them, so this one needs
# the mode switched for the length of the shot and switched back afterwards.
WORK_ORDER_SHOT = ("03_workorders", "/Mgr_Assigned_Runs", 950, None,
                   "Fleet Production Progress")


async def main():
    import crud, database as db

    saved = db.get_plant_settings()
    was_simple = bool(saved.get("simple_mode", True))

    users = crud.get_all_users_df()
    admin = users[users["username"] == "jrivera"]
    admin_id = int(admin["id"].iloc[0])
    admin_theme = str(admin["preferred_theme"].iloc[0])
    crud.update_user_theme(admin_id, "Default Dark")

    written = []

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(viewport={"width": 1500, "height": 1000},
                                  device_scale_factor=2)
        pg = await ctx.new_page()

        await pg.goto(BASE, wait_until="networkidle")
        await pg.wait_for_timeout(6000)
        await pg.locator('input[type="text"]').first.fill("jrivera")
        await pg.locator('input[type="password"]').first.fill(PIN)
        # Without this the cookie is never written and every goto below lands
        # back on the sign-in screen.
        try:
            await pg.get_by_text("Remember this device", exact=False).first.click()
        except Exception:
            pass
        await pg.wait_for_timeout(600)
        await pg.get_by_text("INITIALIZE SESSION").first.click()
        await pg.wait_for_timeout(15000)

        async def shot(name, path, height, anchor, expect):
            # A page reached by URL can render before the "remember this
            # device" cookie has made it back, so the role check runs against
            # a session that is not restored yet and the page answers Access
            # Denied. It is not a permissions problem and it fixes itself on
            # the next render, so this reloads once and looks again. The first
            # version of this script did not, and quietly wrote five
            # screenshots of a denial message into the handbook.
            for attempt in range(3):
                await pg.goto(BASE + path, wait_until="networkidle")
                # Wait for the thing that proves the page is up, rather than
                # sleeping a fixed number of seconds and hoping. The two
                # heaviest screens took longer than the guess and were being
                # written off as refusals.
                try:
                    await pg.get_by_text(expect, exact=False).first.wait_for(
                        state="attached", timeout=45000)
                    await pg.wait_for_timeout(3500)
                except Exception:
                    pass
                body = await pg.inner_text("body")
                if expect in body:
                    break
                why = ("refused" if "Access Denied" in body else
                       "sent to the sign-in screen" if "INITIALIZE SESSION" in body else
                       "showing some other page")
                print(f"  . {name}: {why}, retrying")
            else:
                print(f"  ! {name}: never reached {expect!r}, NOT written")
                return
            if anchor:
                text, up = anchor
                try:
                    el = pg.get_by_text(text, exact=False).first
                    await el.evaluate(
                        "(e) => e.scrollIntoView({block:'start', behavior:'instant'})")
                    await pg.wait_for_timeout(1500)
                    await pg.evaluate("(u) => window.scrollBy(0, u)", up)
                    await pg.wait_for_timeout(1200)
                except Exception as exc:
                    print(f"  ! {name}: anchor {text!r} not found ({type(exc).__name__})")
                    return
            # Off any control, so nothing is caught mid-hover.
            await pg.mouse.move(4, 4)
            await pg.wait_for_timeout(500)
            # Checked again after the scroll, because the anchor step can
            # itself trigger a re-render. Nothing is written unless the real
            # page is on screen.
            body = await pg.inner_text("body")
            if expect not in body:
                print(f"  ! {name}: {expect!r} gone at capture time, NOT written")
                return
            await pg.screenshot(path=f"{OUT}/{name}.png",
                                clip={"x": 0, "y": 0, "width": 1500, "height": height})
            written.append(name)
            print(f"  {name}.png")

        for entry in SHOTS:
            await shot(*entry)

        # Analytics Hub and IT Admin render as an empty shell when they are
        # opened by URL - see the note at the top of this file. Reached by the
        # sidebar link, the way a person reaches them, they are fine.
        async def click_shot(name, link, height, expect, up=None):
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(9000)
            await pg.get_by_text(link, exact=False).first.click()
            try:
                await pg.get_by_text(expect, exact=False).first.wait_for(
                    state="attached", timeout=45000)
                await pg.wait_for_timeout(3500)
            except Exception:
                pass
            if expect not in await pg.inner_text("body"):
                print(f"  ! {name}: never reached {expect!r}, NOT written")
                return
            if up is not None:
                # The console's own content starts below a full screen of
                # navigation, so a crop from the top of the page is a picture
                # of the sidebar. Scroll to the heading first.
                el = pg.get_by_text(expect, exact=False).first
                await el.evaluate(
                    "(e) => e.scrollIntoView({block:'start', behavior:'instant'})")
                await pg.wait_for_timeout(1500)
                await pg.evaluate("(u) => window.scrollBy(0, u)", up)
                await pg.wait_for_timeout(1200)
            await pg.mouse.move(4, 4)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{OUT}/{name}.png",
                                clip={"x": 0, "y": 0, "width": 1500, "height": height})
            written.append(name)
            print(f"  {name}.png")

        await click_shot("04_analytics", "Analytics Hub", 950, "NEXUS ANALYTICS")
        await click_shot("09_admin", "IT Admin", 925, "IT Admin Console", up=-90)

        db.update_plant_settings({"simple_mode": False})
        await shot(*WORK_ORDER_SHOT)
        db.update_plant_settings({"simple_mode": was_simple})

        await ctx.close()
        await b.close()

    crud.update_user_theme(admin_id, admin_theme)
    print(f"  restored simple_mode={was_simple} theme={admin_theme}")

    # Every one of these is a dark screen, and the handbook gets printed. The
    # black floor is lifted so a page is not a solid block of toner.
    for name in written:
        subprocess.run([sys.executable, PREP, f"{OUT}/{name}.png"], check=False)


asyncio.run(main())
