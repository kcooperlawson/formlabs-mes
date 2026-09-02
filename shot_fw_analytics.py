"""Frame the Analytics fill-weight panel on its own.

The earlier attempt screenshotted the viewport, which happened to be showing
the downtime chart and the operator heatmap above it and cut the giveaway bar
chart off at the bottom. This scrolls the panel's heading to the top and clips
to the panel, so the figure is the thing the caption is about.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.expanduser("~/mes"))
OUT = os.path.expanduser("~/mes/figs_print")
BASE = "http://localhost:8501"
USER, PIN = "keagan", "1234"


async def main():
    import crud
    import database as db
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
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(5000)
            if await pg.locator('input[type="password"]').count():
                await pg.locator('input[type="text"]').first.fill(USER)
                await pg.locator('input[type="password"]').first.fill(PIN)
                await pg.wait_for_timeout(400)
                await pg.get_by_text("INITIALIZE SESSION").first.click()
                await pg.wait_for_timeout(11000)

            await pg.get_by_text("Analytics Hub", exact=False).first.click(timeout=8000)
            await pg.wait_for_timeout(14000)

            head = pg.get_by_text("Fill weight", exact=False).first
            await head.scroll_into_view_if_needed()
            await pg.wait_for_timeout(2500)
            # scroll_into_view lands the heading near the bottom of the
            # viewport; push it to the top so the panel below it is what fits.
            await pg.mouse.move(20, 20)
            await pg.mouse.wheel(0, 330)
            await pg.wait_for_timeout(2500)

            bb = await head.bounding_box()
            print("  heading at y =", bb["y"] if bb else None)
            await pg.screenshot(path=f"{OUT}/fw_analytics.png",
                                clip={"x": 288, "y": max(0, bb["y"] - 22),
                                      "width": 1200, "height": 660})
            print("  fw_analytics.png")
            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({"shift_1_start": saved["shift_1_start"],
                                  "shift_1_hours": saved["shift_1_hours"]})
        crud.update_user_theme(_uid, _prev_theme)
        print("  shift schedule and theme restored")


asyncio.run(main())
print("done")
