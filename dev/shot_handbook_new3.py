"""Third pass at the fill-weight figure: correct resin, correct reading, correct crop.

Pass two picked the resin by clicking text that the dropdown never rendered, so
the form stayed on whatever was selected by default and 1114 g came out as
44 g OVER - the opposite of the point being made. And the crop was hardcoded
pixel coordinates against a page captured at 2x, which framed the lot field.

Both fixed by asking rather than assuming: the reading is computed from the
resin's own target in the database, and the crop is the bounding box of the
section element rather than a guess.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "figs_print")
BASE = "http://localhost:8501"
USER, PIN = "jrivera", "1234"
RESIN = "Grey V5"


async def login(pg):
    await pg.goto(BASE, wait_until="networkidle")
    await pg.wait_for_timeout(5000)
    if await pg.locator('input[type="password"]').count():
        await pg.locator('input[type="text"]').first.fill(USER)
        await pg.locator('input[type="password"]').first.fill(PIN)
        await pg.wait_for_timeout(400)
        await pg.get_by_text("INITIALIZE SESSION").first.click()
        await pg.wait_for_timeout(11000)


async def main():
    import crud
    import database as db

    specs = crud.get_all_resin_specs_df("ALL")
    row = specs[specs["resin_name"] == RESIN].iloc[0]
    target = float(row["actual_spec_g"])
    hi = float(row["max_weight_g"])
    # Four grams over target, and inside the window - a cartridge that passes
    # every check and still gives resin away. Clamped so it stays in band even
    # if somebody tightens the spec later.
    reading = min(target + 4.0, hi - 0.5)
    print(f"  {RESIN}: target {target:.0f}, window up to {hi:.0f} -> reading {reading:.0f}")

    # Captured in a light theme on purpose. These two figures are printed, and
    # a dark screenshot has to have its black floor lifted to be printable -
    # which washes out exactly the dim widget labels this figure is about. The
    # app now has six light themes, so the honest and legible option is the
    # same one: shoot it as it looks on Paper White.
    users = crud.get_all_users_df()
    _uid = int(users[users["username"] == USER]["id"].iloc[0])
    _prev_theme = users[users["username"] == USER]["preferred_theme"].iloc[0]
    crud.update_user_theme(_uid, "Paper White")

    saved = db.get_plant_settings()
    db.update_plant_settings({"shift_1_start": "00:00", "shift_1_hours": 12.0})
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx = await b.new_context(viewport={"width": 1500, "height": 1050},
                                      device_scale_factor=2)
            pg = await ctx.new_page()
            await login(pg)
            await pg.get_by_text("Workstation", exact=False).first.click(timeout=8000)
            await pg.wait_for_timeout(11000)

            # Drive the select the way Streamlit actually exposes it: type into
            # the combobox and press Enter, rather than hunting for an option
            # element that is only rendered while the menu is open.
            combo = pg.locator('div[data-testid="stSelectbox"]:has-text("Resin Formulation")').locator("input").first
            await combo.click()
            await pg.wait_for_timeout(600)
            await combo.type(RESIN, delay=60)
            await pg.wait_for_timeout(1200)
            await combo.press("Enter")
            await pg.wait_for_timeout(8000)

            box = pg.locator('div[data-testid="stNumberInput"]:has-text("Check weight")').locator("input").first
            await box.scroll_into_view_if_needed()
            await box.fill(str(int(reading)))
            await box.press("Enter")
            await pg.wait_for_timeout(7000)

            # Confirm the page is showing what the figure claims before saving it.
            body = await pg.inner_text("body")
            assert RESIN in body, f"{RESIN} never got selected"
            print("  verdict on page:",
                  [l for l in body.splitlines() if "target" in l.lower() and "g" in l][:2])

            await box.scroll_into_view_if_needed()
            # Park the pointer off the form first: a stepper button under the
            # cursor renders in its hover state and prints as a red control the
            # reader will assume means something.
            await pg.mouse.move(20, 20)
            await pg.wait_for_timeout(1500)
            bb = await box.bounding_box()
            # Frame from the section heading down past the verdict line.
            clip = {"x": 380, "y": max(0, bb["y"] - 275),
                    "width": 1110, "height": 385}
            await pg.screenshot(path=f"{OUT}/fw_weight.png", clip=clip)
            print("  fw_weight.png", clip)

            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({"shift_1_start": saved["shift_1_start"],
                                  "shift_1_hours": saved["shift_1_hours"]})
        crud.update_user_theme(_uid, _prev_theme)
        print("  shift schedule and theme restored")


asyncio.run(main())
print("done")
