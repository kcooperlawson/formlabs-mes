import asyncio, os, pathlib
from playwright.async_api import async_playwright
# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
SRC = DOCS / "handbook.html"
OUT = DOCS / "Formlabs_MES_Handbook.pdf"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page()
        await pg.goto(SRC.as_uri(), wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        await pg.emulate_media(media="print")
        await pg.pdf(path=str(OUT), format="Letter", print_background=True,
                     margin={"top":"0","bottom":"0","left":"0","right":"0"},
                     prefer_css_page_size=True)
        await b.close()
asyncio.run(main())
print("written", OUT)
