"""See the stopped-record warnings, by actually stopping the record.

The alarm cannot be checked by looking at a healthy plant, and nobody is
going to stop production for three hours to produce one. So this pushes the
newest log's timestamp back far enough to trigger each state, takes the
picture, and puts the timestamp back exactly as it was.

It edits the demo database only - _boot's refusal to touch the .env
connection does not apply here because this is a figure script rather than a
test, so it is written to restore what it changed whatever happens.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = "/tmp"
BASE, PIN = "http://localhost:8501", "1234"


async def sign_in(b, user="jrivera"):
    ctx = await b.new_context(viewport={"width": 1500, "height": 950}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.goto(BASE, wait_until="networkidle")
    await pg.wait_for_timeout(5000)
    await pg.locator('input[type="text"]').first.fill(user)
    await pg.locator('input[type="password"]').first.fill(PIN)
    await pg.wait_for_timeout(400)
    await pg.get_by_text("INITIALIZE SESSION").first.click()
    await pg.wait_for_timeout(13000)
    return ctx, pg


async def main():
    from datetime import datetime, timedelta
    from shift_clock import PLANT_TZ
    from db_core import ScopedSession
    from models import ProductionLog

    # Plain values, not an ORM row: ScopedSession hands the same session to
    # everything on this thread, so a row held across another call that closes
    # it comes back detached.
    session = ScopedSession()
    row_id, original = (session.query(ProductionLog.id, ProductionLog.timestamp)
                        .order_by(ProductionLog.timestamp.desc()).first())
    session.close()
    print(f"  newest log ({row_id}) was {original}")

    async def shoot(name, push_back_hours, minutes_back=0, tv=False):
        s = ScopedSession()
        row = s.query(ProductionLog).filter(ProductionLog.id == row_id).first()
        # Relative to now rather than to the log's own time, so the picture
        # does not depend on how stale the demo data happens to be today.
        row.timestamp = (datetime.utcnow()
                         - timedelta(hours=push_back_hours, minutes=minutes_back))
        s.commit(); s.close()
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            ctx, pg = await sign_in(b)
            if tv:
                await pg.get_by_text("Launch TV Mode", exact=False).first.click()
                await pg.wait_for_timeout(16000)
            await pg.mouse.move(4, 4)
            await pg.screenshot(path=f"{OUT}/{name}.png", clip={"x": 0, "y": 0,
                                                                "width": 1500, "height": 620})
            print(f"  {name}.png")
            await ctx.close()
            await b.close()

    # The alarm only fires during a running shift, which is the point of it -
    # so the demo plant is put on shift for the duration of the picture.
    import database as db
    saved = db.get_plant_settings()
    was = {k: saved.get(k) for k in ("shift_1_start", "shift_1_hours")}
    now_plant = datetime.now(PLANT_TZ)
    on_shift = (now_plant - timedelta(hours=6)).strftime("%H:%M")
    db.update_plant_settings({"shift_1_start": on_shift, "shift_1_hours": 12.0})
    print(f"  shift 1 temporarily {on_shift} +12h")

    try:
        await shoot("health_stalled", 5)
        await shoot("health_quiet", 0, minutes_back=120)
        await shoot("health_tv", 5, tv=True)
    finally:
        db.update_plant_settings(was)
        print(f"  shift 1 restored to {was}")
        s = ScopedSession()
        row = s.query(ProductionLog).filter(ProductionLog.id == row_id).first()
        row.timestamp = original
        s.commit(); s.close()
        print(f"  restored to {original}")


asyncio.run(main())
