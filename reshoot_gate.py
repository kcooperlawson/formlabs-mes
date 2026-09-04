"""Re-take the two lot-gate figures in the capability handbook.

They were shot when the form still called the label a stamp - "the bottom is
stamped L-", "lot stamped on the cartridge bottom". The application stopped
saying that (cartridges and jugs carry the same lot label, on the bottom, and
calling it two things is how an instruction stops being read), but a printed
handbook does not update itself: the page text described a label while the
picture beside it said stamp.

Shot at the same viewport and scale as their neighbours on that page, then run
through print_prep so the black floor matches the rest of the printed figures.
Work orders are switched on for the duration, because a masked expected lot and
a mismatch screen only exist in a plant that dispatches runs - which is what
that page is describing.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/root/mes")
OUT = "/root/mes/figs_print"
BASE, USER, PIN = "http://localhost:8501", "aruiz", "1234"


async def main():
    import crud, database as db
    was_simple = bool(db.get_plant_settings().get("simple_mode", True))
    db.update_plant_settings({"simple_mode": False})

    runs = crud.get_assigned_runs_df()
    row = runs[(runs["cartridge_type"] == "V1")
               & (runs["lot_number"].astype(str).str.strip() != "")].iloc[0]
    lot = str(row["lot_number"])
    station, resin = str(row["pump_station"]), str(row["resin_type"])
    print(f"  against {station} / V1 / {resin}, lot {lot}")

    # The terminal is locked until the startup checklist is in for this
    # operator, this shift and this station - which is the point of it, and a
    # thing a screenshot script has no business clicking through by hand.
    users = crud.get_all_users_df()
    who = users[users["username"] == USER]
    full_name = str(who["full_name"].iloc[0])
    shift = str(who["shift"].iloc[0]) or "Shift 1"
    if not crud.has_completed_daily_checklist(full_name, shift, station):
        crud.submit_daily_checklist(full_name, shift, station)
        print(f"  checklist cleared for {full_name} at {station}")

    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx = await b.new_context(viewport={"width": 1500, "height": 950},
                                      device_scale_factor=2)
            pg = await ctx.new_page()
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(5000)
            await pg.locator('input[type="text"]').first.fill(USER)
            await pg.locator('input[type="password"]').first.fill(PIN)
            await pg.wait_for_timeout(400)
            await pg.get_by_text("INITIALIZE SESSION").first.click()
            await pg.wait_for_timeout(12000)

            for label in ("Workstation", "Operator"):
                try:
                    await pg.get_by_text(label, exact=False).first.click(timeout=8000)
                    await pg.wait_for_timeout(12000)
                    break
                except Exception:
                    continue

            async def pick(label, value):
                combo = pg.locator(
                    f'div[data-testid="stSelectbox"]:has-text("{label}")').locator("input").first
                await combo.click(); await pg.wait_for_timeout(500)
                await combo.fill(""); await combo.type(value, delay=35)
                await pg.wait_for_timeout(800); await combo.press("Enter")
                await pg.wait_for_timeout(6000)

            for lab, val in (("Pump Station", station),
                             ("Container Format", "V1 (1L Cartridge)"),
                             ("Resin Formulation", resin)):
                try:
                    await pick(lab, val)
                except Exception as e:
                    print(f"  !! {lab}: {str(e)[:70]}")

            async def frame(name, anchor, up, height):
                el = pg.get_by_text(anchor, exact=False).first
                await el.evaluate(
                    "(e) => e.scrollIntoView({block:'start', behavior:'instant'})")
                await pg.wait_for_timeout(1600)
                await pg.evaluate("(u) => window.scrollBy(0, u)", up)
                await pg.wait_for_timeout(1400)
                bb = await el.bounding_box()
                if bb and not (-10 <= bb["y"] <= height):
                    print(f"  !! {name}: anchor at y={bb['y']:.0f}, outside 0-{height}")
                await pg.mouse.move(4, 4)
                await pg.wait_for_timeout(400)
                await pg.screenshot(path=f"{OUT}/{name}.png",
                                    clip={"x": 0, "y": 0, "width": 1500, "height": height})
                print(f"  {name}.png")

            # The check, before anything is typed: masked expected lot, the
            # instruction, and the empty field.
            await frame("13_gate", "Lot Verification", 95, 275)

            field = pg.locator(
                'div[data-testid="stTextInput"]:has-text("bottom label")').locator("input").first
            await field.fill("L-0000WRONG")
            await field.press("Enter")
            await pg.wait_for_timeout(8000)
            await frame("14_gate_stop", "DO NOT POUR", -100, 320)

            # The clean check, for the operator-guide section. Framed on the
            # check itself rather than on the whole form: the caption beside it
            # is about the green line, and a taller frame gets cropped from the
            # bottom by the figure's max-height - which is how the previous
            # version of this figure ended up illustrating "green means it
            # matches" with the green cut off.
            await field.fill(f"L-{lot}")
            await field.press("Enter")
            await pg.wait_for_timeout(8000)
            await frame("21_gate_pass", "Lot Verification", 95, 345)

            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({"simple_mode": was_simple})
        print(f"  restored simple_mode={was_simple}")


asyncio.run(main())

# Same black-floor lift the rest of the printed figures got. Without it these
# would be visibly darker than everything around them on the sheet, which reads
# as a printing fault rather than as three screenshots.
#
# Only ever run this on figures this script has just taken. print_prep is close
# to idempotent but not exactly so, and pointing it at an already-lifted file
# washes it out - which is how a stale figure on page 19 got visibly paler than
# its neighbours before it was re-shot.
os.system(f"cd /root/mes && python print_prep.py "
          f"{OUT}/13_gate.png {OUT}/14_gate_stop.png {OUT}/21_gate_pass.png")
