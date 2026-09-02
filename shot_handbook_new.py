"""Capture the figures the handbook needs for the 3.10 material.

Four shots: three light themes rendering the same Live SCADA screen the dark
theme figures already show, and the check-weight field on the real operator
form with a reading typed into it so the live verdict is visible.

The light themes are captured as-is. Every earlier figure had to have its
black floor lifted to be printable; these come out of the app already light,
which is the point the themes page is making.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

OUT = os.path.expanduser("~/mes/figs_print")
BASE = "http://localhost:8501"
USER, PIN = "keagan", "1234"

LIGHT = [("Paper White", "theme_paper_white.png"),
         ("Daylight", "theme_daylight.png"),
         ("High Contrast Light", "theme_hc_light.png")]


def set_theme(name):
    sys.path.insert(0, os.path.expanduser("~/mes"))
    import crud
    users = crud.get_all_users_df()
    uid = int(users[users["username"] == USER]["id"].iloc[0])
    crud.update_user_theme(uid, name)


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
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

        for theme, fname in LIGHT:
            set_theme(theme)
            ctx = await b.new_context(viewport={"width": 1500, "height": 950},
                                      device_scale_factor=2)
            pg = await ctx.new_page()
            await login(pg)
            try:
                await pg.get_by_text("Live SCADA", exact=False).first.click(timeout=8000)
                await pg.wait_for_timeout(9000)
            except Exception as e:
                print(f"  !! {theme}: {e}")
            await pg.screenshot(path=f"{OUT}/{fname}")
            print(f"  {fname}")
            await ctx.close()

        # (The check-weight figure is captured by shot_handbook_new3.py, which
        #  picks the resin properly and frames the section. Capturing it here too
        #  would silently overwrite that one every time the themes are re-shot.)

        set_theme("Formlabs Forge")
        await b.close()


asyncio.run(main())
print("done")
