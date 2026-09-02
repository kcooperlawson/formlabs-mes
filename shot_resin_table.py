"""Re-shoot the master resin table.

The figure in the handbook predates the resin colour work: it shows raw
database column names (`actual_spec_g`, `min_weight_g`) and plain white text
for every formulation. That table now renders each resin name in the colour it
carries on the plant's own master sheet, with proper headers - which is a
headline feature the handbook describes in two places and illustrates nowhere.

In Paper White, because this one is printed and a light capture needs no black
floor lifted out of it.
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
    users = crud.get_all_users_df()
    uid = int(users[users["username"] == USER]["id"].iloc[0])
    prev = users[users["username"] == USER]["preferred_theme"].iloc[0]
    crud.update_user_theme(uid, "Paper White")
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

            await pg.get_by_text("Manager Cockpit", exact=False).first.click(timeout=8000)
            await pg.wait_for_timeout(9000)
            await pg.get_by_text("Resin", exact=False).first.click(timeout=8000)
            await pg.wait_for_timeout(10000)

            # Anchor on the table's own header row, not the page title: the
            # figure is capped at 1.95in tall in the handbook, so every pixel
            # spent on the filter buttons is a row of resins not shown. A wide,
            # short crop fills that box with table.
            head = pg.get_by_text("RESIN NAME", exact=False).first
            await head.scroll_into_view_if_needed()
            await pg.mouse.move(20, 20)
            await pg.wait_for_timeout(2000)
            bb = await head.bounding_box()
            print("  header row y =", bb["y"] if bb else None)
            await pg.screenshot(path=f"{OUT}/18_resins.png",
                                clip={"x": 322, "y": max(0, bb["y"] - 26),
                                      "width": 1175, "height": 360})
            print("  18_resins.png")
            await ctx.close()
            await b.close()
    finally:
        crud.update_user_theme(uid, prev)
        print("  theme restored")


asyncio.run(main())
print("done")
