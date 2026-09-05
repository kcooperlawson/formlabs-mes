"""The three things that only fail in a real browser, and only on a phone.

Every one of these looked correct in Python and was broken in the app, so none
of them can be checked by rendering the script. They need a browser, and two
of them need a phone-sized one - the desktop won the race that the phone lost,
which is the wrong way round for an application operators use on a handset.

  1. "Remember this device" wrote no cookie at all. extra_streamlit_components
     writes cookies by rendering a component; the browser has to receive that
     frame and run its JavaScript, and the st.rerun() on the next line threw
     the frame away first. Nothing failed - set() also updates its own
     in-memory copy, so the same run could read the value back. Every cookie
     in the application was written that way, so a chosen theme reset on the
     next visit too.
  2. The confirmation after submitting a log was an st.toast queued
     immediately before a rerun. On a desktop it usually painted; at 390x844
     it did not, so an operator at the pump got nothing back and had to open
     the last submission to check the entry existed.
  3. The button that opens the station QR checksheet sat above the logging
     tabs - below the checklist that asks whether the checksheet was filled
     in, and behind a st.stop() the operator cannot get past until they tick
     it. Configuring the address appeared to do nothing.

Needs the app running on localhost:8501.
"""
import asyncio
import os
import sys
from datetime import date

from playwright.async_api import async_playwright

sys.path.insert(0, "/root/mes")
BASE, PIN = "http://localhost:8501", "1234"
ADMIN, OPERATOR = "keagan", "aruiz"
QR_URL, QR_LABEL = "https://forms.example.com/station-qr", "Station QR checksheet"

FAILS, CHECKS = [], 0


def check(label, got, exp=True):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")
    else:
        print(f"  ok  {label}")


PHONE = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
DESKTOP = dict(viewport={"width": 1400, "height": 950})


async def sign_in(pg, user, remember=False):
    await pg.goto(BASE, wait_until="networkidle")
    await pg.wait_for_timeout(6000)
    if remember:
        await pg.get_by_text("Remember this device", exact=False).first.click()
    await pg.locator('input[type="text"]').first.fill(user)
    await pg.locator('input[type="password"]').first.fill(PIN)
    await pg.wait_for_timeout(300)
    await pg.get_by_text("INITIALIZE SESSION").first.click()
    await pg.wait_for_timeout(16000)


async def main():
    import crud
    import database as db
    from db_core import ScopedSession
    from models import DailyChecklist

    saved = db.get_plant_settings()
    db.update_plant_settings({"simple_mode": True,
                              "pump_form_url": QR_URL, "pump_form_label": QR_LABEL})
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

            # --- 1. the cookie is written, and survives reopening the page ---
            # Both profiles: the failure was total, not a race, so a phone-only
            # check would not have said which.
            for label, profile in (("phone", PHONE), ("desktop", DESKTOP)):
                ctx = await b.new_context(**profile)
                pg = await ctx.new_page()
                await sign_in(pg, ADMIN, remember=True)
                names = {c["name"] for c in await ctx.cookies()}
                check(f"{label}: remembering the device writes a token cookie",
                      "formlabs_mes_token" in names)
                check(f"{label}: and the theme cookie is written too",
                      "formlabs_mes_theme" in names)
                await pg.goto(BASE, wait_until="networkidle")
                await pg.wait_for_timeout(17000)
                body = await pg.inner_text("body")
                check(f"{label}: reopening the page does not ask for a sign-in again",
                      "SECURE SIGN IN" not in body)
                await ctx.close()

            # --- 2. submitting a log confirms itself, on a phone -------------
            users = crud.get_all_users_df()
            who = users[users["username"] == OPERATOR]
            op_name = str(who["full_name"].iloc[0])
            op_shift = str(who["shift"].iloc[0]) or "Shift 1"
            for station in crud.get_active_pumps():
                if not crud.has_completed_daily_checklist(op_name, op_shift, str(station)):
                    crud.submit_daily_checklist(op_name, op_shift, str(station))

            ctx = await b.new_context(**PHONE)
            pg = await ctx.new_page()
            await sign_in(pg, OPERATOR)
            body = await pg.inner_text("body")
            check("the operator reaches the log form", "Production Output" in body)

            field = pg.locator(
                'div[data-testid="stTextInput"]:has-text("bottom label")').locator("input").first
            if await field.count():
                await field.fill("L-2411A0742")
                await field.press("Enter")
                await pg.wait_for_timeout(8000)
            units = pg.locator(
                'div[data-testid="stNumberInput"]:has-text("Good Units")').locator("input").first
            await units.fill("7")
            await units.press("Tab")
            await pg.wait_for_timeout(3000)
            await pg.get_by_text("SUBMIT POURING LOG", exact=False).first.click()
            await pg.wait_for_timeout(12000)

            body = await pg.inner_text("body")
            check("the log confirms itself where the operator can see it",
                  "Recorded 7 units" in body)
            # The point of a banner over a toast: it is still there a moment
            # later, for somebody who looked at the pump and back.
            await pg.wait_for_timeout(7000)
            body = await pg.inner_text("body")
            check("and the confirmation is still there seconds later",
                  "Recorded 7 units" in body)
            await ctx.close()

            # --- 3. the QR button is on the screen that asks about it -------
            session = ScopedSession()
            session.query(DailyChecklist).filter(
                DailyChecklist.operator_name == op_name,
                DailyChecklist.date == date.today()).delete()
            session.commit()
            session.close()

            ctx = await b.new_context(**PHONE)
            pg = await ctx.new_page()
            await sign_in(pg, OPERATOR)
            body = await pg.inner_text("body")
            check("the terminal is locked on the startup checklist",
                  "TERMINAL LOCKED" in body)
            check("the checksheet button is on the checklist screen", QR_LABEL in body)
            check("beside the box that asks whether the checksheet was done",
                  "scanned the daily station QR Code" in body)
            hrefs = [h for h in await pg.eval_on_selector_all(
                "a", "els => els.map(e => e.getAttribute('href'))") if h]
            check("and it opens the address configured in IT Admin", QR_URL in hrefs)

            os.makedirs("/root/mes/tests/smoke_shots", exist_ok=True)
            await pg.screenshot(
                path="/root/mes/tests/smoke_shots/checklist_qr_button.png", full_page=True)
            await ctx.close()
            await b.close()
    finally:
        db.update_plant_settings({
            "simple_mode": saved.get("simple_mode", True),
            "pump_form_url": saved.get("pump_form_url", ""),
            "pump_form_label": saved.get("pump_form_label", "")})
        print("  settings restored")


asyncio.run(main())
print("\n" + "=" * 62)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} PERSISTENCE CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} PERSISTENCE CHECKS PASSED")
raise SystemExit(1 if FAILS else 0)
