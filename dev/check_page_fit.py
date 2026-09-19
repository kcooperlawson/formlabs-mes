"""Find document pages whose content runs off the bottom.

    python dev/check_page_fit.py                 all three documents
    python dev/check_page_fit.py operator_guide  just that one

Every page in docs/ is a fixed 8.5 x 11 inch box with overflow hidden, so
anything that does not fit is not pushed to the next page. It is painted over
the footer and then cut. The result reads as a paragraph that stops
mid-sentence, which is exactly the kind of thing nobody notices in the browser
and everybody notices in the printed copy they were handed.

That has happened twice. The first time it took the end off a callout on page 7
of the operator guide. The second time a page in the handbook was cutting its
own last note in half before anybody had touched that page - it went out like
that, and the only reason it was found was somebody looking at the PDF one page
at a time.

So this measures instead of looking: it opens each document in the same browser
that renders the PDF and asks every page whether its content is taller than the
page is. Run it after editing any document and before rebuilding the PDFs.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
DOCUMENTS = ("handbook", "operator_guide", "onepager", "update_guide", "history")

# A page is called over only when it is over by more than this. Sub-pixel
# rounding in the layout engine puts a page a fraction over all the time, and a
# checker that cries about a third of a pixel is a checker people switch off.
SLACK_PX = 4

MEASURE = """
() => Array.from(document.querySelectorAll('.page')).map((p, i) => ({
    page: i + 1,
    over: p.scrollHeight - p.clientHeight,
    // The last thing on the page, so the report says WHAT is being cut rather
    // than only that something is.
    last: (p.lastElementChild && p.lastElementChild.previousElementSibling
           ? p.lastElementChild.previousElementSibling.innerText : '')
          .replace(/\\s+/g, ' ').trim().slice(-90),
}))
"""


async def main():
    wanted = [sys.argv[1]] if len(sys.argv) > 1 else list(DOCUMENTS)
    for name in wanted:
        if name not in DOCUMENTS:
            sys.exit(f"unknown document {name!r}; expected one of {', '.join(DOCUMENTS)}")

    bad = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        for name in wanted:
            src = DOCS / f"{name}.html"
            await pg.goto(src.as_uri(), wait_until="networkidle")
            await pg.wait_for_timeout(1500)
            # Measured under print media, because that is what the PDF is
            # rendered with and the two do not always lay out identically.
            await pg.emulate_media(media="print")
            await pg.wait_for_timeout(400)
            pages = await pg.evaluate(MEASURE)
            over = [r for r in pages if r["over"] > SLACK_PX]
            print(f"\n{name}.html  -  {len(pages)} pages")
            for r in over:
                bad += 1
                print(f"  ! page {r['page']:>2}  over by {r['over']:>4}px"
                      f"  ends: ...{r['last']}")
            if not over:
                print("  every page fits")
        await b.close()

    print()
    print("=" * 66)
    print("ALL PAGES FIT" if not bad else f"{bad} PAGE(S) CLIPPED - fix before rebuilding the PDFs")
    return 1 if bad else 0


raise SystemExit(asyncio.run(main()))
