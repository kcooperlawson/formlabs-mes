"""Capture the pouring form on a phone, for the one-page summary.

The single most useful picture for a manager who suspects this is a large
system is the screen an operator actually touches: a phone, three pickers and
three numbers. Captured in a light theme because the page it goes on gets
printed, and at real phone dimensions rather than a desktop window narrowed to
look like one.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/root/mes")
OUT = os.path.expanduser("~/mes/figs_print")
BASE, USER, PIN = "http://localhost:8501", "keagan", "1234"


async def main():
    import crud, database as db
    users = crud.get_all_users_df()
    uid = int(users[users["username"] == USER]["id"].iloc[0])
    prev = users[users["username"] == USER]["preferred_theme"].iloc[0]
    crud.update_user_theme(uid, "Paper White")
    saved = db.get_plant_settings()
    db.update_plant_settings({"shift_1_start": "00:00", "shift_1_hours": 12.0})
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                      device_scale_factor=3, is_mobile=True,
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

            # The sidebar is collapsed on a phone, so the nav row in the body
            # is how you move - tap through to the pouring form.
            for label in ("Operator", "Workstation"):
                try:
                    await pg.get_by_text(label, exact=False).first.click(timeout=7000)
                    await pg.wait_for_timeout(12000)
                    break
                except Exception:
                    continue

            # Point the form at a run that actually exists, so the figure
            # shows the ordinary case rather than the "no run matched" notice -
            # which is correct behaviour but reads as an error to somebody
            # seeing the screen for the first time.
            runs = crud.get_assigned_runs_df()
            row = runs[runs["lot_number"].astype(str).str.strip() != ""].iloc[0]
            station, fmt, resin = str(row["pump_station"]), str(row["cartridge_type"]), str(row["resin_type"])
            fmt_label = {"V1": "V1 (1L Cartridge)", "V2": "V2 (1L Cartridge)",
                         "RPS": "RPS (5L Bulk Jug)", "Pigment": "Pigment"}.get(fmt, fmt)
            print(f"  against {station} / {fmt} / {resin}")

            async def pick(label, value):
                combo = pg.locator(
                    f'div[data-testid="stSelectbox"]:has-text("{label}")').locator("input").first
                await combo.click(); await pg.wait_for_timeout(600)
                await combo.fill(""); await combo.type(value, delay=45)
                await pg.wait_for_timeout(900); await combo.press("Enter")
                await pg.wait_for_timeout(6000)

            for lab, val in (("Pump Station", station), ("Container Format", fmt_label),
                             ("Resin Formulation", resin)):
                try:
                    await pick(lab, val)
                except Exception as e:
                    print(f"  !! {lab}: {e}")

            field = pg.locator(
                'div[data-testid="stTextInput"]:has-text("bottom label")').locator("input").first
            if await field.count():
                await field.fill("L-" + str(row["lot_number"]))
                await field.press("Enter")
                await pg.wait_for_timeout(7000)

            body = await pg.inner_text("body")
            print("  gate clean:", "Lot matches this run" in body)
            print("  no run warning:", "No active run matched" in body)

            # Frame the counts: the part that answers "how much work is this?"
            out = pg.get_by_text("3. Production Output", exact=False).first
            await out.scroll_into_view_if_needed()
            await pg.wait_for_timeout(2500)
            bb = await out.bounding_box()
            await pg.mouse.wheel(0, bb["y"] - 60)
            await pg.wait_for_timeout(2000)
            await pg.screenshot(path=f"{OUT}/phone_form_counts.png")
            print("  phone_form_counts.png")

            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({"shift_1_start": saved["shift_1_start"],
                                  "shift_1_hours": saved["shift_1_hours"]})
        crud.update_user_theme(uid, prev)
        print("  restored")


asyncio.run(main())
print("done")
