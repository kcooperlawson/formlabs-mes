"""Build the operator guide.

A different document from the capability handbook, for a different reader. That
one explains what the system is to somebody deciding about it. This one tells
an operator what to press, in the order they will press it, and is written so a
lead can hand it over and teach from it.

Rules it follows, because they are what make a floor document get used:
  - Second person, imperative. "Turn the cartridge over", not "the operator
    turns the cartridge over".
  - One idea per block, and every screen shown at the size it is held.
  - The things that go wrong get their own section, because that is the part
    people actually come back to.
  - No architecture, no capability list, no numbers about the system itself.
    What it can do gets one short page at the end and nothing more.
"""
import pathlib

# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
css_src = (DOCS / "handbook.html").read_text(encoding="utf-8")
BASE_CSS = css_src[css_src.index("<style>"):css_src.index("</style>") + len("</style>")]

# Larger type, more air, and a two-column step/figure rhythm. An operator guide
# read at a pump is not a document read at a desk.
GUIDE_CSS = """
<style>
  body{font-size:11pt; line-height:1.6;}
  .page{padding:0.62in 0.72in 0.5in;}
  h1,h2,h3,h4{color:var(--ink);}
  .cover-op{display:flex; flex-direction:column; justify-content:center; height:11in;
            padding:0 1.05in; text-align:left;}
  /* align-self, not width. The cover is a column flexbox, whose align-items
     defaults to `stretch` - which pulls the logo out to the full column
     width and flattens the mark. Nothing was setting a width at all. */
  .cover-op .logo{height:34pt; width:auto; align-self:flex-start;
                  margin-bottom:30pt;}
  .cover-op h1{font-family:var(--disp); font-size:34pt; font-weight:800; line-height:1.06;
               letter-spacing:-0.02em; margin:0;}
  .cover-op .sub{font-size:13.5pt; color:var(--muted); margin-top:12pt; max-width:5.1in;
                 line-height:1.5;}
  .cover-op .rule{height:2.5pt; width:1.5in; background:var(--accent); margin:22pt 0 20pt;}
  .cover-op .who{font-family:var(--mono); font-size:8.4pt; letter-spacing:.13em;
                 text-transform:uppercase; color:var(--faint); line-height:2;}

  .sec{border-bottom:1.4pt solid var(--ink); padding-bottom:7pt; margin-bottom:15pt;}
  .sec .num{font-family:var(--mono); font-size:8pt; letter-spacing:.16em; color:var(--accent);
            text-transform:uppercase; display:block; margin-bottom:3pt;}
  .sec h2{font-family:var(--disp); font-size:20pt; font-weight:800; margin:0;
          letter-spacing:-0.015em;}

  .row{display:grid; grid-template-columns:1fr 1.72in; gap:20pt; align-items:start;
       margin-bottom:15pt;}
  .row.wide{grid-template-columns:1fr 2.05in;}
  .row .shot img{width:100%; border:.7pt solid var(--line); border-radius:6pt;}
  .row .shot.tall img{max-height:2.55in; object-fit:cover; object-position:top center;}
  .row .shot .cap{font-size:8pt; color:var(--faint); text-align:center; margin-top:4pt;
                  line-height:1.35;}

  .stepbig{display:flex; gap:11pt; margin-bottom:12pt; align-items:flex-start;}
  .stepbig .n{flex:0 0 auto; width:23pt; height:23pt; border-radius:50%;
              background:var(--accent); color:#fff; font-family:var(--disp);
              font-weight:800; font-size:12pt; display:flex; align-items:center;
              justify-content:center; margin-top:1pt;}
  .stepbig h4{font-size:12pt; font-weight:800; margin:1pt 0 3pt;}
  .stepbig p{margin:0; font-size:10.6pt; line-height:1.55; color:var(--body);}
  .stepbig p + p{margin-top:5pt;}

  /* The bottom margin is spacing between a callout and whatever follows it.
     On a fixed-height page the last element on the sheet has nothing following
     it, and that margin is the difference between a page that fits and one
     that silently clips its last line - which is how page 7 lost the end of
     its own callout. */
  .callout{border-left:3.5pt solid var(--accent); background:var(--surface-2);
           padding:10pt 14pt; margin:0 0 13pt;}
  /* :last-of-type would match the last DIV on the page, and the folio is a
     div too, so it never matched the callout. nth-last-child(2) is the
     element with only the folio after it, which is what "last on the
     sheet" actually means here. */
  .page > .callout:nth-last-child(2){margin-bottom:0;}
  .callout .lab{font-family:var(--mono); font-size:7.6pt; letter-spacing:.13em;
                text-transform:uppercase; color:var(--accent); display:block; margin-bottom:4pt;}
  .callout p{margin:0; font-size:10.4pt; line-height:1.55;}
  .callout.stop{border-left-color:var(--bad);} .callout.stop .lab{color:var(--bad);}
  .callout.ok{border-left-color:var(--good);} .callout.ok .lab{color:var(--good);}

  .fix{border-top:.7pt solid var(--line-soft); padding:9pt 0 0; margin-bottom:9pt;}
  .fix h4{font-size:11pt; font-weight:800; margin:0 0 3pt;}
  .fix p{margin:0; font-size:10.2pt; line-height:1.55; color:var(--body);}

  .rule-list{margin:0; padding-left:0; list-style:none;}
  .rule-list li{font-size:11pt; line-height:1.5; margin-bottom:9pt; padding-left:18pt;
                position:relative; color:var(--ink);}
  .rule-list li::before{content:"—"; position:absolute; left:0; color:var(--accent);
                        font-weight:700;}
  .rule-list li span{color:var(--muted); font-size:10.2pt;}

  .later{display:grid; grid-template-columns:1fr 1fr; gap:9pt 16pt; margin-top:4pt;}
  .later div{font-size:10pt; line-height:1.5; color:var(--muted);}
  .later b{color:var(--ink); display:block; font-size:10.4pt;}
</style>
"""


def page(inner, folio=None):
    f = (f'<div class="folio"><span>Resin Pouring Production Logging &middot; Operator Guide</span>'
         f'<span>{folio}</span></div>') if folio else ""
    return f'<section class="page">{inner}{f}</section>'


def sec(num, title):
    return f'<div class="sec"><span class="num">{num}</span><h2>{title}</h2></div>'


def step(n, head, *paras):
    ps = "".join(f"<p>{p}</p>" for p in paras)
    return f'<div class="stepbig"><div class="n">{n}</div><div><h4>{head}</h4>{ps}</div></div>'


def shot(src, cap, cls=""):
    """A framed screenshot with a caption.

    cls is for pages that carry more than one figure: the phone captures are
    tall, and two of them at full width push whatever follows off the bottom
    of a fixed-height sheet. "tall" crops the figure to the part the caption
    is talking about rather than shrinking the whole page's type.
    """
    c = f" {cls}" if cls else ""
    return (f'<div class="shot{c}"><img src="{src}" alt="">'
            f'<div class="cap">{cap}</div></div>')


def callout(lab, text, kind=""):
    k = f" {kind}" if kind else ""
    return (f'<div class="callout{k}"><span class="lab">{lab}</span>'
            f'<p>{text}</p></div>')


def fix(q, a):
    return f'<div class="fix"><h4>{q}</h4><p>{a}</p></div>'


PAGES = []

# ------------------------------------------------------------------- cover --
PAGES.append(
    '<section class="page cover-op">'
    '<img class="logo" src="assets/formlabs_logo.png" alt="Formlabs">'
    '<h1>Logging your<br>pouring shift</h1>'
    '<div class="rule"></div>'
    '<div class="sub">Everything you need to use the pouring log on your phone &mdash; '
    'signing in, clearing your station, logging the hour, and what to do when '
    'something is not right.</div>'
    '<div class="who" style="margin-top:34pt;">'
    'For &mdash; pouring operators<br>'
    'Read once &middot; keep for reference<br>'
    'September 2026'
    '</div>'
    '</section>')

# ----------------------------------------------------------- what this is ---
PAGES.append(page(
    sec("Before you start", "What this is, in one page")
    + '<p style="font-size:11.6pt; line-height:1.6;">Once an hour, at your pump, you write down '
      'what you poured. That is the whole job. It takes under a minute and it happens on '
      '<b>your own phone</b> &mdash; there is nothing to install and no extra device to carry.</p>'
    + '<p style="margin-top:9pt;">Until now none of this was written down anywhere. That means '
      'nobody could answer simple questions later: how many we poured on a given day, how much '
      'was scrapped, how long a pump was down, or which resin lot went into which containers. '
      'What you log is where those answers come from.</p>'
    + callout("The one rule",
              "<b>Log it when it happens.</b> An hour written up at the end of a shift is a "
              "guess, and every number that comes out of this later is built on what you typed.")
    + '<h3 style="font-size:13pt; margin:16pt 0 8pt;">Your shift, start to finish</h3>'
    + '<ul class="rule-list">'
      '<li>Sign in on your phone. <span>Once a day, or once ever if it is your own phone.</span></li>'
      '<li>Clear the startup checklist for your pump. <span>The rest of the app stays locked until you do.</span></li>'
      '<li>Every hour: set your station and resin, check the lot, enter your counts, submit.</li>'
      '<li>Log downtime when the line stops, and photos at changeovers and spills.</li>'
      '<li>That is it. Nothing to close out at the end of the shift.</li>'
      '</ul>'
    + callout("If you are not sure",
              "Nothing here can break anything. The worst you can do is enter a wrong number, "
              "and there is a button to take that back. Ask your lead rather than guessing at a "
              "lot code.")
, 2))

# --------------------------------------------------------------- signing in --
PAGES.append(page(
    sec("Step 1", "Signing in")
    + '<div class="row">'
    + '<div>'
    + step(1, "Open the plant address in your phone's browser",
           "Your lead will give you the address. Add it to your home screen the first time and "
           "it becomes one tap after that &mdash; there is no app to download.")
    + step(2, "Enter your operator ID and PIN",
           "Both come from your lead. If you have never signed in, ask them to set you up.")
    + step(3, "Tick <em>Remember this device</em>",
           "On a phone only you carry, this is the right thing to do &mdash; it keeps you signed "
           "in for 30 days so you are not typing a PIN every hour. Do not tick it on a phone "
           "somebody else uses.")
    + '</div>'
    + shot("figs_op/01_signin.png", "The sign-in screen.")
    + '</div>'
    + callout("Five wrong PINs locks you out for fifteen minutes",
              "It unlocks on its own, but you do not have to wait &mdash; any manager can reset "
              "your PIN straight away. Ask rather than guessing at it.", "stop")
    + callout("Everything you log is attached to your name",
              "That is the point of signing in: your hours are yours, and nobody can quietly "
              "change them. It also means you should not hand your phone to someone else to log "
              "their hour on your account.")
, 3))

# ---------------------------------------------------------------- checklist --
PAGES.append(page(
    sec("Step 2", "Clearing your station")
    + '<p class="lead">The first time you open the app each shift it is locked, and it stays '
      'locked until you have certified the pump you are standing at. This is deliberate: the '
      'checklist is about <em>this station</em>, not about you.</p>'
    + step(1, "Pick the pump you are starting at",
           "Choose it at the top of the lock screen. Whatever you pick here carries through to "
           "your logging screen, so you only answer this once.")
    + step(2, "Submit the start-of-shift cleanliness photo",
           "Take it on the phone. Add a note if there is anything worth saying about the state "
           "of the station; otherwise the default note is fine.")
    + step(3, "Confirm the two checks",
           "That you have scanned the daily station QR code and submitted that checksheet, and "
           "that your bins of empty cartridges and your receiving carts are staged for the run. "
           "If your plant has set one up, the button that opens the checksheet is right there on "
           "this screen, above the boxes &mdash; it opens in a new tab and this page waits for "
           "you.")
    + step(4, "Press <em>Submit Validation &amp; Unlock Terminal</em>",
           "The logging screens open up. You will not see this again today unless you move "
           "stations.")
    + callout("Moved to a different pump later?",
              "The checklist comes back for the new station. That is not a mistake &mdash; it "
              "certifies the pump you are standing at, and you are now standing at a different "
              "one.")
, 4))

# ------------------------------------------------------- logging: material ---
PAGES.append(page(
    sec("Step 3", "Logging the hour &mdash; set up")
    + '<div class="row wide">'
    + '<div>'
    + step(1, "Pump station",
           "Already set from your checklist. Change it only if you have actually moved.")
    + step(2, "Container format",
           "V2 or V1 cartridge, RPS bulk jug, or Pigment. Pick what you are physically filling.")
    + step(3, "Resin formulation",
           "The resin you are running. Its colour tag appears underneath so you can check it "
           "against the master sheet at a glance.")
    + '<p style="margin-top:11pt; font-size:10.6pt;">Under the resin you will see its '
      '<b>target fill weight and the acceptable range</b>. Worth a glance against your scale.</p>'
    + '</div>'
    + shot("figs_op/02_material.png", "Station and material, with the target weight underneath.")
    + '</div>'
    + callout("If the screen never mentions a run",
              "That is normal, and nothing is missing. Most plants use this as a log: you pick "
              "the station and material, read the lot, enter the counts, and that is the whole "
              "job. If yours does assign work to stations and you see a note saying no open run "
              "matches, keep going anyway &mdash; your log still records and still counts &mdash; "
              "and mention it to your lead afterwards.")
, 5))

# ------------------------------------------------------------ logging: lot ---
PAGES.append(page(
    sec("Step 4", "Logging the hour &mdash; check the lot")
    + '<div class="row wide">'
    + '<div>'
    + '<p class="lead" style="font-size:11.4pt;">This is the one part of the log that is a check '
      'rather than a record, and it is the reason the whole thing is worth doing.</p>'
    + step(1, "Turn the container over",
           "Cartridge or bulk jug &mdash; both carry the same lot label on the bottom.")
    + step(2, "Type the code you can see",
           "Exactly as printed. Spacing, capitals and the <span class=\"mono\">L-</span> prefix "
           "do not matter &mdash; type it however it comes out.")
    + '</div>'
    + shot("figs_op/03_lot_blank.png", "The lot check, before you type.")
    + '</div>'
    + callout("If a lot is expected, it is hidden on purpose",
              "Where the screen has something to check yours against, you will see dots instead "
              "of a number. That is not a fault. If it showed you the answer, the check would be "
              "checking nothing &mdash; <b>read the container, not the screen.</b>")
, 6))

# ------------------------------------------------------------ lot outcomes ---
PAGES.append(page(
    sec("Step 4", "What the lot check tells you")
    + '<div class="row wide">'
    + '<div>'
    + '<h3 style="font-size:12.6pt; margin:0 0 6pt;">Green &mdash; it matches</h3>'
    + '<p style="font-size:10.6pt;">Carry on and enter your counts. Nothing else to do.</p>'
    + '<p style="font-size:10.6pt; margin-top:7pt;">Next time, at the same station on the same '
      'resin and lot, it becomes a single tap to confirm the container still reads the same code. '
      'The full check returns on any change, after four hours, and every tenth log.</p>'
    + '</div>'
    + shot("figs_op/05_lot_ok.png", "A clean check.", "tall")
    + '</div>'
    + '<div class="row wide">'
    + '<div>'
    + '<h3 style="font-size:12.6pt; margin:0 0 6pt; color:var(--bad);">Red &mdash; STOP, do not pour</h3>'
    + '<p style="font-size:10.6pt;">This container is not from the lot your run expects. '
      '<b>Set it aside and get your lead.</b></p>'
    + '<p style="font-size:10.6pt; margin-top:7pt;">If you pull it, press <em>Wrong cartridge '
      '&mdash; pulled it, nothing poured</em>. That records the catch: it is the system working.</p>'
    + '<p style="font-size:10.6pt; margin-top:7pt;">If your lead decides it goes ahead anyway, '
      'choose a reason, add the detail, and photograph the label. The log saves with a flag on it '
      'for review.</p>'
    + '</div>'
    + shot("figs_op/04_lot_stop.png", "A mismatch.", "tall")
    + '</div>'
    + '<h3 style="font-size:12.6pt; margin:7pt 0 5pt;">Blue &mdash; recorded</h3>'
    + '<p style="font-size:10.6pt;">If your plant does not assign work to stations there is '
      'nothing to compare yours against, so the screen reads your code back and saves it with the '
      'log. Nothing has gone wrong &mdash; <b>read and type it exactly the same way.</b></p>'
    + callout("A mismatch never stops you working",
              "It asks for an explanation, and it never blocks you from pulling the container "
              "&mdash; the safe thing to do is always the quickest thing to do.", "stop")
, 7))

# --------------------------------------------------------- logging: counts ---
PAGES.append(page(
    sec("Step 5", "Logging the hour &mdash; your counts")
    + '<div class="row wide">'
    + '<div>'
    + step(1, "Good units filled",
           "The containers you actually filled this hour.")
    + step(2, "Scrap empty and scrap filled, kept separate",
           "They mean different things: an empty scrapped is a handling problem, a filled one is "
           "lost resin as well. Keeping them apart is what makes the difference visible.")
    + step(3, "Check weight &mdash; optional, every time",
           "If you have the scale to hand, weigh one and type the number. It tells you straight "
           "away whether that container is inside its window and how far off target it is. "
           "<b>Leaving it blank never blocks anything</b> &mdash; a blank is honest, a guess is "
           "worse than nothing.")
    + step(4, "Anything worth noting, then submit",
           "A green line appears at the top of the screen naming what was recorded, and it stays "
           "there until you do something else &mdash; so you can look at the pump and back and "
           "still see it. If it says the entry did not save, nothing was recorded: submit again.")
    + '</div>'
    + shot("figs_op/06_counts.png", "Counts and submit.")
    + '</div>'
    + callout("Typed the wrong number? Take it back.",
              "For two minutes after you submit, an <em>Undo last</em> button sits just above the "
              "counts. Use it &mdash; a 2500 that should have been 250 is much easier to fix now "
              "than to explain later.", "ok")
, 8))

# ------------------------------------------------------------- other things --
PAGES.append(page(
    sec("Step 6", "Downtime, photos and messages")
    + '<div class="row wide">'
    + '<div>'
    + '<h3 style="font-size:12.6pt; margin:0 0 5pt;">When the line stops</h3>'
    + '<p style="font-size:10.6pt;">Use the <em>Log Station Downtime</em> tab: the reason, how '
      'many minutes, and what was done about it.</p>'
    + '<p style="font-size:10.6pt; margin-top:7pt;">Log it as it happens rather than reconstructing '
      'it later. Downtime nobody records does not disappear &mdash; it turns up as bad yield '
      'instead, which makes it look like the pouring was the problem.</p>'
    + '</div>'
    + shot("figs_op/07_downtime.png", "The downtime tab.")
    + '</div>'
    + '<h3 style="font-size:12.6pt; margin:14pt 0 5pt;">Photo audits</h3>'
    + '<p style="font-size:10.6pt;">The <em>Cleanliness &amp; Photo Audit</em> tab covers start of '
      'shift, end of shift, moving a line onto a different resin, and spills. There is a tick box '
      'to mark a photo as an active spill or leak, which flags it for attention rather than '
      'filing it as routine.</p>'
    + '<h3 style="font-size:12.6pt; margin:14pt 0 5pt;">Talking to your lead</h3>'
    + '<p style="font-size:10.6pt;">The <em>Manager Comms</em> tab is a direct thread with the '
      'plant lead, inside the app. Use it for anything that should stay attached to the record '
      'rather than living in a text message.</p>'
    + '<h3 style="font-size:12.6pt; margin:14pt 0 5pt;">Your own numbers</h3>'
    + '<p style="font-size:10.6pt;">Units poured, scrap and quality yield sit at the top of your '
      'screen and update as you log. It is the same figure management sees &mdash; there is no '
      'separate scoring going on behind it.</p>'
, 9))

# --------------------------------------------------------- when things go wrong
PAGES.append(page(
    sec("Reference", "When something is not right")
    + fix("The app is locked and will not let me log",
          "You have not cleared the startup checklist for the pump you picked. Do that and the "
          "logging tabs open. If you have moved stations, it will ask again for the new one.")
    + fix("I am locked out after mistyping my PIN",
          "Five wrong attempts locks the account for fifteen minutes. It clears on its own, but "
          "any manager can reset it immediately &mdash; that is faster than waiting.")
    + fix("The lot does not match and my lead is not around",
          "Do not pour. Set the container aside and press <em>Wrong cartridge &mdash; pulled it, "
          "nothing poured</em>. That is a complete, correct outcome on its own; nothing is left "
          "hanging by choosing it.")
    + fix("It says no open run matches my station",
          "Log the hour anyway &mdash; it records and it counts. Read the code off the container "
          "as normal; it is stored against your log either way. If your plant assigns work to "
          "stations, tell your lead afterwards so it can be set up. If it does not, this is "
          "simply how the screen looks and there is nothing to report.")
    + fix("I typed the wrong number and already submitted",
          "Press <em>Undo last</em> within two minutes. After that, ask your lead &mdash; they can "
          "correct it from their side, and it is better fixed than left.")
    + fix("The screen says my log was not saved",
          "Then it was not, and nothing was recorded. Submit again. This is the app being honest "
          "rather than pretending &mdash; the network drops in parts of the building.")
    + fix("I cannot read the screen properly",
          "Under <em>Account &amp; Preferences</em> there is a <b>Display</b> section: "
          "<em>Glove mode</em> makes every button and box bigger for gloved hands, and there are "
          "light themes for working under bright shop lighting. Both are remembered.")
    + fix("I keep losing my place while pouring",
          "If there is a <em>Focus mode</em> toggle at the top of the logging tab, turn it on: it "
          "strips the screen down to the four things you need mid-run &mdash; resin, lot, count "
          "so far, how many left &mdash; big enough to read from across the station. It only "
          "appears in plants that assign work to stations, because those four numbers come off "
          "the assignment.")
, 10))

# ------------------------------------------------------------- what else -----
PAGES.append(page(
    sec("Last page", "What else it does")
    + '<p class="lead" style="font-size:11.4pt;">None of this is your job, and none of it needs '
      'anything from you beyond the hourly log. It is here so you know what happens to what you '
      'type, and who is looking at it.</p>'
    + '<div class="later" style="margin-top:14pt;">'
      '<div><b>Work orders</b>Optional, and off unless a plant turns it on. When it is on, a '
      'manager dispatches runs to a pump; that is where an expected lot comes from, and how your '
      'units count towards a target.</div>'
      '<div><b>Who runs it</b>In most plants, your manager &mdash; accounts, PIN resets, pumps and '
      'settings are all theirs. There is no separate IT person to wait for.</div>'
      '<div><b>The floor display</b>A screen showing the shift&rsquo;s pace, built from the same '
      'logs. No extra entry &mdash; it is your hourly figures, shown large.</div>'
      '<div><b>Trends and reports</b>Yield, scrap and downtime over weeks, and exports for anyone '
      'who needs the numbers elsewhere. All of it is the same rows you entered.</div>'
      '<div><b>Fill weights</b>The optional check weights add up into how much resin is going out '
      'above target &mdash; which is money, and invisible without them.</div>'
      '<div><b>Lot traceability</b>Which lot went into which containers, at which pump, by whom '
      'and when. That is the question a customer complaint asks.</div>'
      '<div><b>Reactors and stock</b>How much is left in each supply vessel, worked out from '
      'what has actually been poured out of it. The lot you read off the container is what '
      'tells it a vessel has been refilled &mdash; one more reason that field is worth '
      'getting right.</div>'
      '</div>'
    + callout("If something about the app is wrong or annoying, say so",
              "There is a feedback box under <em>Account &amp; Preferences</em>, and it goes "
              "straight to whoever maintains this. Small annoyances at a pump are the ones worth "
              "reporting &mdash; they are the ones nobody else can see.")
    + '<div style="margin-top:20pt; padding-top:11pt; border-top:.7pt solid var(--line);'
      'font-size:9.6pt; color:var(--faint);">'
      'A fuller description of the system, for whoever runs it, is in the '
      '<em>Resin Pouring &mdash; Production Logging Operations Handbook</em>.</div>'
, 11))

html = ("<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Formlabs MES — Operator Guide</title>"
        + BASE_CSS + GUIDE_CSS + "</head><body>" + "\n".join(PAGES) + "</body></html>")

out = DOCS / "operator_guide.html"
out.write_text(html, encoding="utf-8")
print(f"operator_guide.html written: {len(PAGES)} pages, {len(html):,} chars")
