"""Render one of the documents in docs/ to a print-ready PDF.

    python dev/topdf.py                    the handbook
    python dev/topdf.py operator_guide     the operator guide
    python dev/topdf.py onepager           the one-page summary

Takes the document by name rather than by path, so the output file cannot end
up named after whatever was typed. Before this took an argument at all it
ignored one silently: asking it for the operator guide rebuilt the handbook and
said so on a line that is easy to skim past.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"

DOCUMENTS = {
    "handbook": ("handbook.html", "Formlabs_MES_Handbook.pdf"),
    "operator_guide": ("operator_guide.html", "Formlabs_MES_Operator_Guide.pdf"),
    "onepager": ("onepager.html", "Resin_Pouring_One_Page.pdf"),
}

# Accepts "operator_guide", "operator_guide.html" or "docs/operator_guide.html".
name = pathlib.Path(sys.argv[1]).stem if len(sys.argv) > 1 else "handbook"
if name not in DOCUMENTS:
    sys.exit(f"unknown document {name!r}; expected one of {', '.join(DOCUMENTS)}")

SRC = DOCS / DOCUMENTS[name][0]
OUT = DOCS / DOCUMENTS[name][1]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page()
        await pg.goto(SRC.as_uri(), wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        await pg.emulate_media(media="print")
        await pg.pdf(path=str(OUT), format="Letter", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                     prefer_css_page_size=True)
        await b.close()


asyncio.run(main())
print("written", OUT)

# A copy where the running app can serve it. Streamlit serves static/ and
# nothing else, and the help links inside the app point at these - so a
# rebuild that only wrote docs/ would leave the app handing people last
# month's document with no sign that it had.
_served = DOCS.parent / "static" / OUT.name
try:
    _served.write_bytes(OUT.read_bytes())
    print("served copy", _served)
except OSError as exc:
    print("could not write the served copy:", exc)
