"""Screenshot every page and report what changed since last time.

The gap this closes. `test_pages.py` proves every page renders without
raising, and it has caught real crashes - but a page can render perfectly
and still be wrong: a card that lost its border, a chart that came back
empty, a nav bar that wrapped onto two lines, a theme where the text went
the same colour as its background. None of that raises. It gets noticed
when somebody happens to look, which for the wall display might be days.

So: drive a real browser through every page, save a picture, and compare
against the last approved set. A CSS change that quietly breaks the TV
dashboard then shows up as a diff rather than as a surprise.

    python tests/visual_regression.py --approve     # accept current as the baseline
    python tests/visual_regression.py               # compare against it
    python tests/visual_regression.py --theme "Daylight"

Not run as part of the normal suite: it needs a browser, a seeded database
and a running server, and it takes a couple of minutes. It is the thing you
run before shipping a change to the look of the app.

The baseline is deliberately NOT committed. It is a set of photographs of one
particular database on one particular machine, so a baseline captured
elsewhere would report every page as changed on yours for reasons that have
nothing to do with the code. Run --approve once on your own install and the
comparison is meaningful from then on.

Comparison is a per-pixel difference with a tolerance, not an exact match.
Antialiasing and font hinting differ by a pixel or two between runs on the
same machine, and a check that cries wolf on that gets switched off within a
week - so a page has to change by more than a threshold fraction of its
pixels before it is reported.
"""
import argparse
import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "visual_baseline"
OUT = ROOT / "tests" / "visual_current"
DIFFS = ROOT / "tests" / "visual_diffs"

# Fraction of pixels allowed to differ before a page counts as changed.
# Loose enough to absorb antialiasing, tight enough that a missing border or
# a colour change lands well above it.
TOLERANCE = 0.004

BASE = os.environ.get("MES_URL", "http://localhost:8501")
USER = os.environ.get("MES_USER", "keagan")
PIN = os.environ.get("MES_PIN", "1234")

# Reached by clicking the sidebar, because a direct URL starts a fresh
# Streamlit session with no login - the same reason the screenshot scripts
# used during development had to navigate by clicking.
# Several links carry a different label depending on which page you are
# standing on - the operator page is "Workstation" from one screen and
# "Operator Form" from another - so each entry lists the labels to try.
PAGES = [
    ("live_scada", ["Live SCADA"]),
    ("workstation", ["Operator Form", "Workstation"]),
    ("reactors", ["Live Reactors"]),
    ("cockpit", ["Manager Cockpit"]),
    ("analytics", ["Analytics Hub"]),
    ("admin", ["IT Admin"]),
]


def compare(a_path, b_path, diff_path):
    """Fraction of pixels that differ, writing a visual diff if any do."""
    from PIL import Image, ImageChops
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return 1.0, f"size changed {a.size} -> {b.size}"
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    if bbox is None:
        return 0.0, ""
    # Count pixels that differ by more than a hair, so antialiasing does not
    # register as a change.
    # getdata() is deprecated in Pillow 14; the histogram is both supported
    # and far faster than walking several million tuples in Python.
    channel_hist = diff.convert("L").histogram()
    changed = sum(count for level, count in enumerate(channel_hist) if level > 8)
    frac = changed / float(a.size[0] * a.size[1])
    if frac > TOLERANCE:
        DIFFS.mkdir(parents=True, exist_ok=True)
        # Amplify the difference so a subtle change is actually visible.
        ImageChops.multiply(diff, diff).save(diff_path)
    return frac, ""


async def capture(theme=None):
    from playwright.async_api import async_playwright
    OUT.mkdir(parents=True, exist_ok=True)

    if theme:
        sys.path.insert(0, str(ROOT))
        import crud
        users = crud.get_all_users_df()
        uid = int(users[users["username"] == USER]["id"].iloc[0])
        crud.update_user_theme(uid, theme)

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await browser.new_context(viewport={"width": 1500, "height": 1000})
        pg = await ctx.new_page()
        await pg.goto(BASE, wait_until="networkidle")
        await pg.wait_for_timeout(4500)
        if await pg.locator('input[type="password"]').count():
            await pg.locator('input[type="text"]').first.fill(USER)
            await pg.locator('input[type="password"]').first.fill(PIN)
            await pg.wait_for_timeout(400)
            await pg.get_by_text("INITIALIZE SESSION").first.click()
            await pg.wait_for_timeout(9000)

        captured = []
        for slug, labels in PAGES:
            opened = False
            for label in labels:
                try:
                    target = pg.get_by_text(label, exact=False).first
                    await target.click(timeout=6000)
                    await pg.wait_for_timeout(8000)
                    opened = True
                    break
                except Exception:
                    continue
            if not opened:
                print(f"  SKIPPED {slug}: no link matched {labels}")
                continue
            await pg.screenshot(path=str(OUT / f"{slug}.png"))
            captured.append(slug)
            print(f"  captured {slug}")
        await browser.close()
        return captured


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", action="store_true",
                    help="accept the current screenshots as the new baseline")
    ap.add_argument("--theme", default=None, help="set this theme before capturing")
    args = ap.parse_args()

    captured = asyncio.run(capture(args.theme))
    if not captured:
        print("\nNothing captured - is the app running at " + BASE + "?")
        return 1

    if args.approve:
        SHOTS.mkdir(parents=True, exist_ok=True)
        for slug in captured:
            (SHOTS / f"{slug}.png").write_bytes((OUT / f"{slug}.png").read_bytes())
        print(f"\nBaseline updated: {len(captured)} pages.")
        return 0

    if not SHOTS.exists():
        print("\nNo baseline yet. Run with --approve once you are happy with how "
              "the app looks, and this becomes a regression check from then on.")
        return 0

    print()
    changed, missing = [], []
    for slug in captured:
        base = SHOTS / f"{slug}.png"
        if not base.exists():
            missing.append(slug)
            print(f"  NEW      {slug} (no baseline)")
            continue
        frac, note = compare(base, OUT / f"{slug}.png", DIFFS / f"{slug}.png")
        if frac > TOLERANCE:
            changed.append(slug)
            print(f"  CHANGED  {slug}  {frac * 100:.2f}% of pixels{' - ' + note if note else ''}")
        else:
            print(f"  same     {slug}  {frac * 100:.2f}%")

    print()
    if changed:
        print(f"{len(changed)} page(s) changed. Diffs written to {DIFFS}.")
        print("Look at them: if the change was intended, re-run with --approve.")
        return 1
    if missing:
        print(f"{len(missing)} new page(s) with no baseline. Re-run with --approve to add them.")
    print("No visual regressions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
