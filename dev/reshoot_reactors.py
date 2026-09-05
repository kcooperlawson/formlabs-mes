"""Re-take the two figures on the vessel-levels page, in the mode it now sits in.

The tank card used to carry the operator name off the work order assigned to
that tank - which was only ever there because the work order was also, quietly,
supplying the lot and the container format the level was calculated from. The
level is now derived from the logs themselves, so the second line on the card
is the lot in the tank: the thing somebody standing at the vessel can check
against the container in front of them.

Both figures sit in Part One now, so both have to be shot the way Part One runs
- logging mode, no work orders anywhere. The wall display was shot with work
orders on, so it carried an "Active Reactor Work Orders" card on a page that
tells the reader none of this needs them.

Each is clipped to its content rather than to the viewport. The handbook crops
figures from the bottom to fit a maximum height, and the bottom is where the
numbers are, so a figure with dead space above it loses the part worth
printing. print_prep afterwards, on these files only: a second pass over an
already-lifted figure leaves it paler than its neighbours on the sheet.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "figs_print")
PREP = os.path.join(ROOT, "dev", "print_prep.py")
BASE, PIN = "http://localhost:8501", "1234"
NAMES = ("07_reactors", "15_tv")


async def sign_in(b):
    ctx = await b.new_context(viewport={"width": 1500, "height": 950},
                              device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.goto(BASE, wait_until="networkidle")
    await pg.wait_for_timeout(5000)
    await pg.locator('input[type="text"]').first.fill("keagan")
    await pg.locator('input[type="password"]').first.fill(PIN)
    await pg.wait_for_timeout(400)
    await pg.get_by_text("INITIALIZE SESSION").first.click()
    await pg.wait_for_timeout(13000)
    return ctx, pg


async def frame(pg, name, anchor, up, y, height):
    el = pg.get_by_text(anchor, exact=False).first
    await el.evaluate("(e) => e.scrollIntoView({block:'start', behavior:'instant'})")
    await pg.wait_for_timeout(1500)
    await pg.evaluate("(u) => window.scrollBy(0, u)", up)
    await pg.wait_for_timeout(1300)
    await pg.mouse.move(4, 4)
    await pg.wait_for_timeout(400)
    await pg.screenshot(path=f"{OUT}/{name}.png",
                        clip={"x": 0, "y": y, "width": 1500, "height": height})
    print(f"  {name}.png")


async def main():
    import crud
    import database as db

    # Both screens are shot in Default Dark, which is what the other handbook
    # figures use. The wall display in particular is white text on a dark
    # ground: rendered in a light theme and then lifted for print, its heading
    # disappears into the page.
    users = crud.get_all_users_df()
    admin = users[users["username"] == "keagan"]
    admin_id = int(admin["id"].iloc[0])
    admin_theme = str(admin["preferred_theme"].iloc[0])
    crud.update_user_theme(admin_id, "Default Dark")

    saved = db.get_plant_settings()
    was_simple = bool(saved.get("simple_mode", True))
    was_pack = bool(saved.get("enable_packing", True))
    # Part One is the plant as proposed: logging only, and pack-out is in
    # Appendix D. A figure on a Part One page must not carry a work-order card
    # or a pack-out card, or the picture argues with the text beside it.
    db.update_plant_settings({"simple_mode": True, "enable_packing": False})

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

        # --- the tanks, cropped to the cards under them ---------------------
        ctx, pg = await sign_in(b)
        await pg.get_by_text("Reactors", exact=False).first.click()
        await pg.wait_for_timeout(14000)
        await frame(pg, "07_reactors", "REAL-TIME REACTOR FLEET", -120, 190, 610)
        await ctx.close()

        # --- the wall display, with no work-order card on it -----------------
        # Reached by the sidebar button, not by its URL: navigating straight to
        # a page URL starts a new Streamlit session, which is not signed in.
        ctx, pg = await sign_in(b)
        await pg.get_by_text("Launch TV Mode", exact=False).first.click()
        await pg.wait_for_timeout(16000)
        # The whole plant day rather than the hours elapsed in the current
        # shift, so the figure shows a display with a day on it.
        await pg.get_by_text("Full Plant Daily Total", exact=False).first.click()
        await pg.wait_for_timeout(14000)
        await frame(pg, "15_tv", "LIVE PLANT COMMAND", 0, 285, 400)
        await ctx.close()

        await b.close()

    db.update_plant_settings({"simple_mode": was_simple, "enable_packing": was_pack})
    crud.update_user_theme(admin_id, admin_theme)
    print(f"  restored simple_mode={was_simple} enable_packing={was_pack} "
          f"theme={admin_theme}")


asyncio.run(main())
os.system(f"python {PREP} " + " ".join(f"{OUT}/{n}.png" for n in NAMES))
