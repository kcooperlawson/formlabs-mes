"""Where an export goes, and whether the address will actually take it.

The plant's Google Sheet used to be one line in .env: a single webhook, set
once by whoever installed the application, changeable only by editing a file
on the server. That has three problems and this plant hit all of them. Nobody
but the installer can point it anywhere. There is exactly one destination, so
a second manager who wants their own sheet cannot have one. And when the line
is missing or the deployment behind it has been revoked, the page says
"webhook missing" and there is nothing anybody can do about it from inside the
application - which is where they are standing when they find out.

So a destination is a row somebody can add, and the awkward part is told
plainly rather than assumed away: **a Google Sheet link is not an address that
can receive anything.** A spreadsheet URL is a document. To send rows to it,
that sheet needs a small Apps Script published as a web app, and the address
of THAT is what goes in the box. Everybody pastes the spreadsheet link first -
it is the link they have - so classify_url exists to notice, say so in one
sentence, and hand over the script and the four steps rather than reporting a
validation failure and leaving them to work out why.

Pure functions and one constant. No Streamlit, no database, no requests: what
is worth testing here is the reasoning about addresses and date ranges, and
none of that needs a network or a browser to be wrong.
"""
from __future__ import annotations

from datetime import date, timedelta

# The two Google hosts that matter, and they mean opposite things.
SCRIPT_HOST = "script.google.com"
SHEET_HOST = "docs.google.com"

# How far back each choice reaches. None means everything on file.
HORIZONS = {
    "⚡ Live Today (Active Shift)": 0,
    "📆 Past 7 Days": 7,
    "📊 Past 30 Days": 30,
    "🌐 All Time History": None,
}


def classify_url(value) -> dict:
    """What somebody pasted, and what to tell them about it.

    kind is one of:
      webhook  - an Apps Script web app address; this is the one that works
      sheet    - a spreadsheet link, which cannot receive rows; needs setup
      script   - a script editor link, which is the project, not its address
      empty    - nothing typed
      unknown  - a URL we do not recognise, allowed with a warning

    An unrecognised address is a warning and not a refusal on purpose. A plant
    may point this at something that is not Google at all - a webhook on their
    own network, a logging endpoint - and an export tool that only permits one
    vendor's URLs is a smaller thing than it needs to be.
    """
    url = str(value or "").strip()
    if not url:
        return {"kind": "empty", "url": "", "ok": False,
                "message": "Paste the web app address for your sheet."}

    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    low = url.lower()

    if SCRIPT_HOST in low and "/macros/" in low:
        if not low.rstrip("/").endswith("/exec"):
            return {"kind": "script", "url": url, "ok": False,
                    "message": ("That is the deployment address but not the live one - "
                                "it has to end in /exec. A /dev address only works while "
                                "you have the editor open.")}
        return {"kind": "webhook", "url": url, "ok": True, "message": ""}

    if SCRIPT_HOST in low:
        return {"kind": "script", "url": url, "ok": False,
                "message": ("That is the link to the script editor, not to the deployed "
                            "web app. In the editor use Deploy > New deployment, then "
                            "copy the web app URL it gives you - it ends in /exec.")}

    if SHEET_HOST in low and "/spreadsheets/" in low:
        return {"kind": "sheet", "url": url, "ok": False,
                "message": ("That is the spreadsheet itself, which cannot receive rows - "
                            "a document has no inbox. Follow the four steps below to give "
                            "this sheet an address, then paste that instead.")}

    return {"kind": "unknown", "url": url, "ok": True,
            "message": ("This is not a Google Apps Script address. It will be used as "
                        "given - make sure whatever is there accepts a POST.")}


def horizon_days(label):
    """Days back for a time-horizon choice, or None for everything."""
    return HORIZONS.get(str(label or ""), None)


def horizon_start(label, today=None):
    """The earliest date a horizon includes, or None for everything.

    This exists because the control it serves did nothing at all. The page
    offered four time horizons, read the answer into a variable and then
    exported every log ever recorded regardless - so "Live Today" on a plant
    with two years of history sent two years of history, and the only sign
    was a row count nobody was checking. Same fault as the automation picker
    that was removed from this page for the same reason: a control that
    appears to configure something and does not is worse than no control.
    """
    days = horizon_days(label)
    if days is None:
        return None
    return (today or date.today()) - timedelta(days=days)


def filter_by_horizon(df, label, today=None):
    """The rows a horizon includes. Returns the frame unchanged for All Time."""
    start = horizon_start(label, today)
    if start is None or df is None or getattr(df, "empty", True):
        return df
    if "date" not in df.columns:
        return df
    import pandas as pd
    # format="mixed" rather than letting pandas infer: the column holds real
    # dates on a live database and whatever a test or a restored dump put
    # there otherwise, and inferring a format off the first value then
    # failing on the rest is how an export quietly loses a day.
    dates = pd.to_datetime(df["date"], errors="coerce", format="mixed").dt.date
    return df[dates.notna() & (dates >= start)]


def visible_targets(rows, user_id, is_admin=False):
    """The destinations this person may use.

    Their own, plus any a colleague marked shared, plus everything if they
    administer the system. A manager's private sheet stays private by default
    because it is theirs - the point of letting people add their own is that
    they do not have to negotiate for one.
    """
    out = []
    for row in rows or []:
        owner = row.get("owner_user_id")
        if is_admin or bool(row.get("is_shared")) or (owner is not None and owner == user_id):
            out.append(row)
    return out


def target_label(row) -> str:
    """How a destination reads in a picker."""
    name = str(row.get("name") or "Unnamed sheet").strip()
    owner = str(row.get("owner_name") or "").strip()
    if row.get("is_shared"):
        return f"{name} — shared by {owner}" if owner else f"{name} — shared"
    return f"{name} — {owner}" if owner else name


def last_sync_text(last_at, last_status, now=None) -> str:
    """One line on how this destination last behaved.

    A destination that has stopped working looks exactly like one that has
    never been used, right up until somebody needs the numbers. Saying when it
    last worked, and what happened if it did not, is the difference between
    noticing that in the application and noticing it in a meeting.
    """
    if not last_at:
        return "Never used."
    now = now or _utcnow()
    mins = max(0.0, (now - last_at).total_seconds() / 60.0)
    if mins < 90:
        when = f"{int(mins)} min ago"
    elif mins < 60 * 48:
        when = f"{int(mins // 60)} h ago"
    else:
        when = f"{int(mins // 1440)} days ago"

    status = str(last_status or "").strip()
    if status and status.lower() != "ok":
        return f"Last attempt {when} — failed: {status}"
    return f"Last sent {when}."


def _utcnow():
    from datetime import datetime
    return datetime.utcnow()


# The script that gives a spreadsheet an address. Shown in the page so nobody
# has to be sent somewhere else to find it, and kept here rather than inline in
# the page so there is one copy of it to correct.
#
# doGet is in it for the sake of the Test button: testing by POSTing real rows
# would mean the only way to check a destination is to write to it, and a test
# that changes the thing it is testing is not a test.
APPS_SCRIPT = '''/**
 * Formlabs MES -> this spreadsheet.
 * Paste into Extensions > Apps Script and save. Then Deploy > New deployment >
 * Web app, Execute as "Me", Access "Anyone". Copy the /exec URL it gives you.
 *
 * If you EDIT this script later you must also publish the change:
 * Deploy > Manage deployments > pencil icon > Version: New version > Deploy.
 * Saving the editor alone does not update the live address.
 */
function doPost(e) {
  var body = JSON.parse(e.postData.contents);

  // The MES checking the address. Answered before anything touches the
  // spreadsheet, so a connection test never changes what it is testing.
  if (body.ping) {
    return ContentService.createTextOutput('formlabs-mes-ok');
  }

  var rows = body.data || [];
  if (!rows.length) {
    return ContentService.createTextOutput('formlabs-mes-ok: 0 rows');
  }

  var tab = body.sheet_name || 'MES Export';
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var sh  = ss.getSheetByName(tab) || ss.insertSheet(tab);
  sh.clear();

  var headers = Object.keys(rows[0]);
  var out = [headers];
  rows.forEach(function (r) {
    out.push(headers.map(function (h) { return r[h]; }));
  });

  sh.getRange(1, 1, out.length, headers.length).setValues(out);
  sh.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold').setBackground('#0B1220').setFontColor('#FFFFFF');
  sh.setFrozenRows(1);
  sh.autoResizeColumns(1, headers.length);

  return ContentService.createTextOutput('formlabs-mes-ok: ' + rows.length + ' rows');
}

/** Lets the MES check the address without writing anything to the sheet. */
function doGet() {
  return ContentService.createTextOutput('formlabs-mes-ok');
}
'''

# What the script answers with. Every reply carries it, so a response that does
# not is a response from something other than this script - which is the whole
# point: a 200 from Google is not evidence that the export worked.
OK_TOKEN = "formlabs-mes-ok"


def diagnose_response(status, text, url="") -> dict:
    """What a reply from a destination actually means.

    Google answers a great many things with 200, and only one of them is
    success. A web app whose access is not set to "Anyone" answers an
    unauthenticated request with a sign-in PAGE and status 200 - so a check
    that only looks at the status code reports a healthy destination, and an
    export that only looks at the status code reports that it dispatched
    records into a sign-in form. Both were true here until this existed.

    Returns {ok, level, message}. level is a short slug for the tests.
    """
    body = str(text or "")
    low = body.lower()

    if OK_TOKEN in body:
        return {"ok": True, "level": "ok", "message": ""}

    if int(status or 0) != 200:
        return {"ok": False, "level": "http",
                "message": (f"The address answered {status}. If it is 401, 403 or a "
                            "redirect to a sign-in page, the deployment's access is not "
                            "set to Anyone. Deploy > Manage deployments > pencil icon, "
                            "set Who has access to Anyone, and Deploy again.")}

    # A sign-in page. This is the common one and it looks like success.
    if any(k in low for k in ("accounts.google.com", "servicelogin", "signin/v2",
                              "sign in to continue", "choose an account")):
        return {"ok": False, "level": "signin",
                "message": ("Google answered with a sign-in page, which means this web "
                            "app is not published for anyone to reach. Deploy > Manage "
                            "deployments > pencil icon, set **Who has access** to "
                            "**Anyone** (not 'Anyone with Google account'), and Deploy.")}

    if any(k in low for k in ("access denied", "you need permission",
                              "request access", "permission denied")):
        return {"ok": False, "level": "denied",
                "message": ("Google refused the request. Set **Execute as: Me** and "
                            "**Who has access: Anyone** on the deployment, redeploy, and "
                            "approve the permissions prompt when it appears.")}

    if "script function not found" in low or "requested entity was not found" in low:
        return {"ok": False, "level": "missing",
                "message": ("Google could not find the function to run. Paste the script "
                            "below into the editor, save, then Deploy > Manage "
                            "deployments > pencil icon > Version: **New version**.")}

    # Answered, in this script's own voice or not, but without the token. Far
    # and away the most likely cause is a deployment still serving the code
    # from before the script was pasted - saving the editor does not publish.
    snippet = " ".join(body.split())[:120]
    return {"ok": False, "level": "stale",
            "message": ("Something answered, but not with this script's reply. Nearly "
                        "always this means the deployment is still serving the older "
                        "code: **saving the editor does not publish it.** Go to Deploy > "
                        "Manage deployments, click the pencil, set Version to "
                        "**New version**, and Deploy. Then test again."
                        + (f"\n\nWhat came back: `{snippet}`" if snippet else ""))}


SETUP_STEPS = (
    "Open your Google Sheet and choose **Extensions → Apps Script**.",
    "Delete whatever is in the editor, paste the script below, and save.",
    "Choose **Deploy → New deployment → Web app**. Set *Execute as* to **Me** "
    "and *Who has access* to **Anyone**, then Deploy and approve the permissions.",
    "Copy the **Web app URL** it shows you — it ends in `/exec` — and paste it in the box below.",
)
