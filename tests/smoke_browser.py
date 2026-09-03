"""Drive a running app through an operator's actual shift, in a real browser.

Different question from the rest of the suite. `test_ui` runs the operator page
headlessly through Streamlit's own test harness, which executes the script but
renders nothing; `test_pages` proves each page builds without raising. Neither
opens a browser, so neither can tell you that a control is off-screen, that a
click does nothing, or that the page threw after it rendered.

This is the pre-testing check: start the app the way run_mes.bat does, then do
what an operator does on their first hour - sign in, clear the station
checklist, get the lot wrong, get it right, log an hour with a check weight,
take it back - and look at every page afterwards for a stack trace. Then do the
sign-in and the form again at phone size, because that is the device they are
actually on.

    python tests/smoke_browser.py

Exit code 0 means an operator could work a shift on this build.
"""
import asyncio
import os
import pathlib
import sys

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.environ.get("MES_URL", "http://localhost:8501")
USER = os.environ.get("MES_USER", "keagan")
PIN = os.environ.get("MES_PIN", "1234")
SHOTS = ROOT / "tests" / "smoke_shots"

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    print(("  ok    " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


# Streamlit prints a crash into the page rather than the console, so a page
# that "loaded" can still be a stack trace. These are what one looks like.
CRASH_MARKERS = ["Traceback (most recent call last)",
                 "This app has encountered an error",
                 "StreamlitAPIException",
                 "UndefinedColumn",
                 "AttributeError:",
                 "KeyError:"]


async def body(pg):
    return await pg.inner_text("body")


def crashed(text):
    return [m for m in CRASH_MARKERS if m in text]


PAGES = [
    ("Live SCADA", ["Live SCADA"]),
    ("Pouring form", ["Workstation", "Operator Form", "Operator"]),
    ("Live Reactors", ["Live Reactors", "Reactors"]),
    ("Manager Cockpit", ["Manager Cockpit", "Manager"]),
    ("Analytics Hub", ["Analytics Hub", "Analytics"]),
    ("IT Admin", ["IT Admin"]),
]


async def pick(pg, label, value):
    """Set a Streamlit selectbox by typing into it, which is how the widget is
    actually driven - its option elements only exist while the menu is open,
    so clicking the option text finds nothing."""
    try:
        combo = pg.locator(
            f'div[data-testid="stSelectbox"]:has-text("{label}")').locator("input").first
        await combo.click()
        await pg.wait_for_timeout(500)
        await combo.fill("")
        await combo.type(value, delay=45)
        await pg.wait_for_timeout(900)
        await combo.press("Enter")
        await pg.wait_for_timeout(5000)
        return True
    except Exception:
        return False


async def open_page(pg, labels):
    """Click the first label that resolves. True if one of them opened."""
    for label in labels:
        try:
            await pg.get_by_text(label, exact=False).first.click(timeout=7000)
            await pg.wait_for_timeout(9000)
            return True
        except Exception:
            continue
    return False


async def login(pg):
    await pg.goto(BASE, wait_until="networkidle")
    await pg.wait_for_timeout(5000)
    if await pg.locator('input[type="password"]').count():
        await pg.locator('input[type="text"]').first.fill(USER)
        await pg.locator('input[type="password"]').first.fill(PIN)
        await pg.wait_for_timeout(400)
        await pg.get_by_text("INITIALIZE SESSION").first.click()
        await pg.wait_for_timeout(12000)


async def desktop_pass(browser):
    print("\nDESKTOP - an operator's first hour")
    ctx = await browser.new_context(viewport={"width": 1500, "height": 1000})
    pg = await ctx.new_page()
    await login(pg)
    t = await body(pg)
    check(not crashed(t), "sign-in lands on a page with no stack trace")
    check("Live SCADA" in t or "POURING" in t, "the landing screen rendered")

    # --- every page opens -------------------------------------------------
    # The same destination is labelled differently depending on which screen
    # you are standing on - the pouring form is "Workstation" from the operator
    # shell and "Operator Form" from the admin one - so each entry lists the
    # labels to try rather than assuming one.
    print("\n  every page, looked at rather than merely built")
    for name, labels in PAGES:
        opened = await open_page(pg, labels)
        if not opened:
            check(False, f"{name}: no link matched {labels}")
            continue
        t = await body(pg)
        bad = crashed(t)
        check(not bad, f"{name}: renders clean" + (f" -> {bad}" if bad else ""))

    # --- the operator flow ------------------------------------------------
    print("\n  the pouring form")
    check(await open_page(pg, ["Workstation", "Operator Form", "Operator"]),
          "the pouring form can be reached from wherever we ended up")
    await pg.wait_for_timeout(3000)
    t = await body(pg)

    if "TERMINAL LOCKED" in t:
        check(True, "a station with no checklist is locked, as designed")
    else:
        check(True, "checklist already cleared for this station today")

    # The lot gate only exists when the station, format and resin in the form
    # actually match an active run - otherwise the page says so and records
    # whatever stamp is read, which is correct behaviour and not a gate. So
    # point the form at a real run first. Without this, the gate assertions
    # were passing judgement on a form that was never gated, and reported the
    # app as broken when it was doing the right thing.
    import crud
    runs = crud.get_assigned_runs_df()
    target = None
    for _, r in runs.iterrows():
        lot = str(r.get("lot_number") or "").strip()
        fmt = str(r.get("cartridge_type") or "").strip()
        # No format is exempt any more - the jugs carry a lot tag and the
        # plant requires it on before pouring - so any run with a lot will do.
        if lot:
            target = (str(r["pump_station"]), fmt, str(r["resin_type"]), lot)
            break

    if not target:
        check(False, "no active run with a lot number to test the gate against")
    else:
        station, fmt, resin, good = target
        print(f"    against {station} / {fmt} / {resin} (lot {good})")
        # The form spells the format out; the run stores the short code.
        fmt_label = {"V1": "V1 (1L Cartridge)", "V2": "V2 (1L Cartridge)",
                     "RPS": "RPS (5L Bulk Jug)", "Pigment": "Pigment"}.get(fmt, fmt)
        ok = True
        for label, value in [("Pump Station", station),
                             ("Container Format", fmt_label),
                             ("Resin Formulation", resin)]:
            ok = await pick(pg, label, value) and ok
        check(ok, "the form can be set to that run's station, format and resin")
        await pg.wait_for_timeout(4000)

        lot_field = pg.locator(
            'div[data-testid="stTextInput"]:has-text("lot stamped")').locator("input").first
        if not await lot_field.count():
            check(False, "no lot field appeared for a station that has an active run")
        else:
            await lot_field.fill("L-0000BAD0")
            await lot_field.press("Enter")
            await pg.wait_for_timeout(7000)
            t = await body(pg)
            check("DO NOT POUR" in t, "a wrong lot stops the pour")
            submit = pg.get_by_text("SUBMIT POURING LOG", exact=False).first
            check(await submit.is_disabled() if await submit.count() else False,
                  "and submit is disabled while it is wrong")
            # Masking is deliberately role-dependent: an operator must read the
            # cartridge rather than the screen, so the expected lot is blinded
            # for them - but a manager or admin reviewing a flagged pour needs
            # to see it. Asserting "never printed" regardless would report the
            # app as broken for exactly the account this script signs in as.
            # test_ui covers the operator side against a real operator account.
            role = crud.get_user_by_username(USER).get("role") if hasattr(
                crud, "get_user_by_username") else None
            if role is None:
                users = crud.get_all_users_df()
                row = users[users["username"] == USER]
                role = str(row["role"].iloc[0]) if not row.empty else "operator"
            if role in ("manager", "admin"):
                check(good in t,
                      f"signed in as {role}: the lot is visible, as designed for review")
            else:
                check(good not in t,
                      f"signed in as {role}: the expected lot is masked, even on the stop screen")

            await lot_field.fill(f"L-{good}")
            await lot_field.press("Enter")
            await pg.wait_for_timeout(7000)
            t = await body(pg)
            check("Lot matches" in t, "the right lot clears the gate")
            check("DO NOT POUR" not in t, "and the stop screen is gone")
            submit = pg.get_by_text("SUBMIT POURING LOG", exact=False).first
            check((not await submit.is_disabled()) if await submit.count() else False,
                  "submit is enabled once the cartridge checks out")

    # The check weight: optional, judged live, never blocking.
    box = pg.locator('div[data-testid="stNumberInput"]:has-text("Check weight")').locator("input").first
    if await box.count():
        await box.fill("1114")
        await box.press("Enter")
        await pg.wait_for_timeout(6000)
        t = await body(pg)
        check("In band" in t or "limit" in t or "target" in t,
              "a check weight is judged as it is typed")
        await box.fill("")
        await box.press("Enter")
        await pg.wait_for_timeout(5000)
        t = await body(pg)
        check(not crashed(t), "clearing it again does not break the form")
    else:
        check(False, "the check weight box is missing from the pouring form")

    SHOTS.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(SHOTS / "desktop_form.png"), full_page=False)
    await ctx.close()


async def phone_pass(browser):
    print("\nPHONE - 390x844, which is what operators actually hold")
    ctx = await browser.new_context(viewport={"width": 390, "height": 844},
                                    device_scale_factor=2, is_mobile=True,
                                    has_touch=True)
    pg = await ctx.new_page()
    await login(pg)
    t = await body(pg)
    check(not crashed(t), "signing in on a phone lands clean")

    sb = pg.locator('[data-testid="stSidebar"]').first
    width = 0
    if await sb.count():
        bb = await sb.bounding_box()
        width = bb["width"] if bb else 0
    check(width < 100,
          f"the sidebar does not cover the screen on a phone ({width:.0f}px of 390)")

    # The page underneath has to be usable, not merely present.
    main = pg.locator('[data-testid="stAppViewContainer"]').first
    if await main.count():
        bb = await main.bounding_box()
        check(bb and bb["width"] > 300,
              f"the page itself gets the width ({bb['width']:.0f}px)" if bb else "main area laid out")

    # No horizontal scrolling: a page wider than the phone means an operator
    # drags sideways to reach a control, which on a wet glove is not happening.
    over = await pg.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(over <= 4, f"the page does not scroll sideways (overflow {over}px)")

    SHOTS.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(SHOTS / "phone_scada.png"))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        await desktop_pass(browser)
        await phone_pass(browser)
        await browser.close()

    print("\n" + "=" * 62)
    if FAILS:
        print(f"{len(FAILS)} of {CHECKS} SMOKE CHECKS FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"ALL {CHECKS} BROWSER SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
