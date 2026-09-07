"""Capture the screens the operator guide walks through, at phone size.

Every figure in that guide has to be the screen the reader is holding, at the
dimensions they are holding it, or the guide is describing a different app.
Light theme because it is printed and pinned up at a station.

Each shot is framed on the element it is about rather than the viewport, so a
step's picture shows that step and not half of the next one.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "figs_op")
BASE, USER, PIN = "http://localhost:8501", "keagan", "1234"


async def frame(pg, path, anchor=None, height=760, block="start", pad=40, width=390):
    """Screenshot the phone viewport, positioned on `anchor` if given.

    Scrolls with the DOM's own scrollIntoView rather than Playwright's
    scroll_into_view_if_needed plus a wheel gesture. In a mobile context that
    pair quietly does nothing here - which is why an earlier run of this file
    produced three different steps all showing the top of the form.
    """
    if anchor is not None:
        try:
            await anchor.evaluate(
                "(el, opts) => el.scrollIntoView({block: opts.block, behavior: 'instant'})",
                {"block": block})
            await pg.wait_for_timeout(1200)
            if pad:
                await pg.evaluate("(p) => window.scrollBy(0, -p)", pad)
                await pg.wait_for_timeout(900)
            # Confirm it actually moved to where the caption will claim it is.
            bb = await anchor.bounding_box()
            if bb and not (-10 <= bb["y"] <= height - 40):
                print(f"  !! {os.path.basename(path)}: anchor at y={bb['y']:.0f}, "
                      f"outside the 0-{height} frame")
        except Exception as e:
            print(f"  !! frame {os.path.basename(path)}: {e}")
    await pg.mouse.move(5, 5)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=path, clip={"x": 0, "y": 0, "width": width, "height": height})
    print("  " + os.path.basename(path))


async def main():
    os.makedirs(OUT, exist_ok=True)
    import crud, database as db
    users = crud.get_all_users_df()
    uid = int(users[users["username"] == USER]["id"].iloc[0])
    prev = users[users["username"] == USER]["preferred_theme"].iloc[0]
    crud.update_user_theme(uid, "Paper White")
    saved = db.get_plant_settings()
    db.update_plant_settings({"shift_1_start": "00:00", "shift_1_hours": 12.0})

    runs = crud.get_assigned_runs_df()
    row = runs[runs["lot_number"].astype(str).str.strip() != ""].iloc[0]
    station, fmt, resin = str(row["pump_station"]), str(row["cartridge_type"]), str(row["resin_type"])
    lot = str(row["lot_number"])
    fmt_label = {"V1": "V1 (1L Cartridge)", "V2": "V2 (1L Cartridge)",
                 "RPS": "RPS (5L Bulk Jug)", "Pigment": "Pigment"}.get(fmt, fmt)
    print(f"  using {station} / {fmt} / {resin}, lot {lot}")

    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                      device_scale_factor=3, is_mobile=True, has_touch=True)
            pg = await ctx.new_page()

            # 1. the sign-in screen
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(5500)
            await frame(pg, f"{OUT}/01_signin.png")

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

            # 2. station and material, with the target weight underneath
            await frame(pg, f"{OUT}/02_material.png",
                        pg.get_by_text("Station & Material", exact=False).first, height=780)

            field = pg.locator(
                'div[data-testid="stTextInput"]:has-text("bottom label")').locator("input").first

            # 3. the lot check, before anything is typed
            await frame(pg, f"{OUT}/03_lot_blank.png",
                        pg.get_by_text("Lot Verification", exact=False).first, height=620)

            # 4. a wrong code -> the stop screen
            await field.fill("L-0000WRONG")
            await field.press("Enter")
            await pg.wait_for_timeout(7500)
            await frame(pg, f"{OUT}/04_lot_stop.png",
                        pg.get_by_text("DO NOT POUR", exact=False).first, height=700, pad=105)
            # 105 rather than 70: the floating logo sits over the top ~90px
            # of the viewport and was printing across the STOP banner.

            # 5. the right code
            await field.fill(f"L-{lot}")
            await field.press("Enter")
            await pg.wait_for_timeout(7500)
            await frame(pg, f"{OUT}/05_lot_ok.png",
                        pg.get_by_text("Lot matches", exact=False).first, height=470, block="center", pad=0)

            # 6. counts and submit
            await frame(pg, f"{OUT}/06_counts.png",
                        pg.get_by_text("3. Production Output", exact=False).first, height=800)

            # 7. the other tabs
            try:
                await pg.get_by_text("Downtime", exact=False).first.click(timeout=8000)
                await pg.wait_for_timeout(7000)
                await frame(pg, f"{OUT}/07_downtime.png",
                            pg.get_by_text("Station Downtime Event Logger", exact=False).first,
                            height=760)
            except Exception as e:
                print("  !! downtime:", e)

            try:
                await pg.get_by_text("Audit", exact=False).first.click(timeout=8000)
                await pg.wait_for_timeout(7000)
                await frame(pg, f"{OUT}/08_photo.png",
                            pg.get_by_text("Cleanliness, Changeover", exact=False).first, height=760)
            except Exception as e:
                print("  !! photo audit:", e)

            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({"shift_1_start": saved["shift_1_start"],
                                  "shift_1_hours": saved["shift_1_hours"]})
        crud.update_user_theme(uid, prev)
        print("  restored")


asyncio.run(main())
print("done")
