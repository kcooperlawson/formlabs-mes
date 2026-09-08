"""Re-take the three handbook figures that no longer show what the page says.

  20_activeruns  The page it sits on is "The operator terminal", marked in
                 service - and the figure was of the assigned-runs block,
                 which is the optional feature. A reader who looks at the
                 pictures rather than the prose came away with the opposite
                 of what the section says. Replaced by the log itself.
  02_cockpit     Shows a heading that no longer exists: the manager page was
                 titled "Plant Manager Operations & Work Order Dispatch" and
                 is now "Plant Manager - Production Records".
  22_packing     Carries two strings that were deleted - a run-cards heading
                 over an empty space, and a notice telling the operator to go
                 and find their plant manager.
  11_export      Its page is "Reporting out", and the figure was of the shift
                 handover, which has been removed. Replaced by the export
                 screen that page is now about.

Shot at the same viewport, scale and aspect as the figures they replace, so
the page layouts do not move. print_prep afterwards, to the same black floor
as the rest of the printed figures - and only on files this script has just
taken, because running it twice on one file washes it out.
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
PREP = os.path.join(ROOT, "dev", "print_prep.py")
BASE, PIN = "http://localhost:8501", "1234"


async def main():
    import crud, database as db
    saved = db.get_plant_settings()
    was_simple = bool(saved.get("simple_mode", True))
    was_pack = bool(saved.get("enable_packing", True))

    # The terminal is locked until the startup checklist is in for this
    # operator, this shift and the station the picker happens to land on -
    # which is the point of the checklist, and not a thing a screenshot
    # script should be clicking through. Cleared for every active pump so
    # the shot does not depend on which one the picker defaults to.
    users = crud.get_all_users_df()
    who = users[users["username"] == "aruiz"]
    op_name = str(who["full_name"].iloc[0])
    op_shift = str(who["shift"].iloc[0]) or "Shift 1"
    pumps = crud.get_active_pumps()
    for station in pumps:
        station = str(station)
        if not crud.has_completed_daily_checklist(op_name, op_shift, station):
            crud.submit_daily_checklist(op_name, op_shift, station)
    print(f"  checklist cleared for {op_name} at {len(pumps)} station(s)")

    admin = users[users["username"] == "jrivera"]
    admin_id = int(admin["id"].iloc[0])
    admin_theme = str(admin["preferred_theme"].iloc[0])
    crud.update_user_theme(admin_id, "Default Dark")

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

        written = []

        async def session(user, viewport=(1500, 950)):
            ctx = await b.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                      device_scale_factor=2)
            pg = await ctx.new_page()
            await pg.goto(BASE, wait_until="networkidle")
            await pg.wait_for_timeout(5000)
            await pg.locator('input[type="text"]').first.fill(user)
            await pg.locator('input[type="password"]').first.fill(PIN)
            await pg.wait_for_timeout(400)
            await pg.get_by_text("INITIALIZE SESSION").first.click()
            await pg.wait_for_timeout(13000)
            return ctx, pg

        async def frame(pg, name, anchor, up, height, width=1500):
            el = pg.get_by_text(anchor, exact=False).first
            await el.evaluate("(e) => e.scrollIntoView({block:'start', behavior:'instant'})")
            await pg.wait_for_timeout(1500)
            await pg.evaluate("(u) => window.scrollBy(0, u)", up)
            await pg.wait_for_timeout(1300)
            await pg.mouse.move(4, 4)
            await pg.wait_for_timeout(400)
            await pg.screenshot(path=f"{OUT}/{name}.png",
                                clip={"x": 0, "y": 0, "width": width, "height": height})
            written.append(name)
            print(f"  {name}.png")

        # --- 1. the operator terminal, as a plant that only logs sees it -----
        db.update_plant_settings({"simple_mode": True})
        ctx, pg = await session("aruiz")
        for label in ("Workstation", "Operator"):
            try:
                await pg.get_by_text(label, exact=False).first.click(timeout=8000)
                await pg.wait_for_timeout(12000)
                break
            except Exception:
                continue
        # 1.58:1 to match the figure it replaces, so the page does not reflow.
        await frame(pg, "20_terminal", "1. Station & Material", -55, 950)
        await ctx.close()

        # --- 2. the manager cockpit, with its current heading ---------------
        ctx, pg = await session("jrivera")
        await pg.get_by_text("Manager", exact=False).first.click()
        await pg.wait_for_timeout(14000)
        await frame(pg, "02_cockpit", "Plant Manager", -150, 804)
        await ctx.close()

        # --- 3. the packing tab, which is what that figure is captioned as ---
        # Shot as an admin: the tab is built for packer, manager and admin,
        # and an operator's tab strip does not carry it at all.
        db.update_plant_settings({"enable_packing": True})
        ctx, pg = await session("jrivera")
        for label in ("Workstation", "Operator"):
            try:
                await pg.get_by_text(label, exact=False).first.click(timeout=8000)
                await pg.wait_for_timeout(12000)
                break
            except Exception:
                continue
        try:
            await pg.get_by_text("Packing", exact=False).first.click(timeout=9000)
            await pg.wait_for_timeout(8000)
            await frame(pg, "22_packing", "Packing Details", -120, 759)
        except Exception as e:
            print("  !! packing:", str(e)[:90])
        await ctx.close()

        # --- 4. what reporting out actually is, now the handover is gone -----
        ctx, pg = await session("jrivera")
        await pg.get_by_text("Manager", exact=False).first.click()
        await pg.wait_for_timeout(14000)
        try:
            await pg.get_by_text("Google Cloud Sheets Sync", exact=False).first.click(timeout=9000)
            await pg.wait_for_timeout(12000)
            await frame(pg, "11_export", "External Reporting", -120, 700)
        except Exception as e:
            print("  !! export:", str(e)[:90])
        await ctx.close()

        await b.close()

    db.update_plant_settings({"simple_mode": was_simple, "enable_packing": was_pack})
    crud.update_user_theme(admin_id, admin_theme)
    print(f"  restored simple_mode={was_simple} enable_packing={was_pack} "
          f"theme={admin_theme}")
    return written


NAMES = asyncio.run(main())

# Only the files just taken. print_prep is not exactly idempotent, and a second
# pass over an already-lifted figure leaves it visibly paler than its
# neighbours on the sheet - which is what happened to this very set the first
# time this script ran and one of its three shots failed.
if NAMES:
    os.system(f"python {PREP} "
              + " ".join(f"{OUT}/{n}.png" for n in NAMES))
