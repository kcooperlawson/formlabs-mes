import asyncio, os
from playwright.async_api import async_playwright
# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev", "_scratch_shots")
os.makedirs(OUT, exist_ok=True); BASE = "http://localhost:8501"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        # a common mid-size Android/iPhone viewport
        ctx=await b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2,
                                is_mobile=True, has_touch=True)
        pg=await ctx.new_page()
        await pg.goto(BASE, wait_until="networkidle"); await pg.wait_for_timeout(5000)
        await pg.screenshot(path=f"{OUT}/01_login.png"); print("login")
        await pg.locator('input[type="text"]').first.fill("jrivera")
        await pg.locator('input[type="password"]').first.fill("1234")
        await pg.wait_for_timeout(400)
        await pg.get_by_text("INITIALIZE SESSION").first.click(); await pg.wait_for_timeout(10000)
        await pg.screenshot(path=f"{OUT}/02_scada.png"); print("scada")
        # How much of the phone is the sidebar actually taking? Home.py used to
        # force it open, and a ~320px overlay on a 390px screen leaves the page
        # underneath unreadable - the operator's first action every hour was to
        # close something they never opened.
        sb = pg.locator('[data-testid="stSidebar"]').first
        if await sb.count():
            bb = await sb.bounding_box()
            print(f"sidebar: {bb['width']:.0f}px of 390 "
                  f"({bb['width']/390*100:.0f}%)" if bb else "sidebar collapsed (no box)")
        else:
            print("sidebar collapsed (no element)")
        try:
            await pg.get_by_text("Operator Form").first.click(timeout=8000)
        except Exception:
            await pg.get_by_text("Workstation").first.click(timeout=8000)
        await pg.wait_for_timeout(11000)
        await pg.screenshot(path=f"{OUT}/03_operator_top.png"); print("operator top")
        await pg.mouse.move(200,500)
        for _ in range(8):
            await pg.mouse.wheel(0,600); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f"{OUT}/04_operator_form.png"); print("operator form")
        await b.close()
asyncio.run(main())
