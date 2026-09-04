"""Rebuild handbook.html as two parts: what is in service, and what is available.

The handbook described eighteen screens at one weight, in the order they were
built. Read by somebody deciding whether to allow this, that is a list of
things they would be taking on. Almost none of it is: the log is the system,
and everything else is a setting that answers a question somebody has to ask
first.

So the same material is re-ordered rather than rewritten. Part One is what
runs and what comes out of it. Part Two is what a plant can switch on, each
page headed with what it costs to do so. The role guides, the readability
work, the test record and the unfinished experiments become appendices,
because none of them is part of the decision.

Three other things change with it:

  - The cover said "Manufacturing Execution System". That is accurate and it
    is also a term that costs six figures elsewhere, which invites a question
    about authorisation before anyone has read a page. It now says what it
    does.
  - Two pages of theme gallery became one page about reading a screen on the
    floor. Glove mode, light themes under shop lighting and a measured
    contrast floor are the floor's problems; thirty-four of anything is the
    author's.
  - Every section header carries its status, so the distinction survives
    somebody reading one page out of the middle.

Run once. It reads handbook.html and writes handbook.html, so keep the
result under version control and edit that from here on - this script exists
as the record of what moved where, not as a build step.
"""
import re
import pathlib

# Lives in dev/, so the project root is one level up. Every path below is
# relative to that, never to wherever this happens to be run from.
SRC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "handbook.html"

FOLIO_LABEL = "Resin Pouring Production Logging &middot; Operations Handbook"

# --------------------------------------------------------------- new styles --
EXTRA_CSS = """
/* Part banding and section status. The distinction between what runs and what
   is merely available has to survive somebody opening the document in the
   middle, so it lives on every section header rather than only in the
   contents. */
.partband{font-family:var(--mono); font-size:6.4pt; letter-spacing:.18em;
          text-transform:uppercase; color:var(--ground); background:var(--ink);
          display:inline-block; padding:2.5pt 7pt; border-radius:2pt; margin-bottom:7pt;}
.sec-head .hrow{display:flex; justify-content:space-between; align-items:baseline;
                gap:10pt; margin-bottom:5pt;}
.sec-head .hrow .eyebrow{display:inline; margin-bottom:0;}
.status{font-family:var(--mono); font-size:6.4pt; letter-spacing:.13em; text-transform:uppercase;
        padding:2pt 6pt; border-radius:2pt; border:.5pt solid var(--line);
        color:var(--muted); background:var(--surface-2); white-space:nowrap; flex:none;}
.status.in{color:#166534; border-color:#BBF7D0; background:#F0FDF4;}
.status.opt{color:#92400E; border-color:var(--accent-dim); background:#FFFBEB;}
.status.no{color:var(--faint); border-color:var(--line); background:var(--surface-2);}
/* The contents now carries three part bands and a scope note as well as its
   rows, so the rows themselves give up a point of leading each. */
.toc .row{padding:4.2pt 0;}
"""

# ------------------------------------------------------------- the new order --
# (source page number, part band or None, eyebrow, status, replacement h2 or None)
P1 = "Part One &mdash; In service"
P2 = "Part Two &mdash; Available if wanted"
PA = "Appendices"

ORDER = [
    # ---- Part One: the log, and what comes out of it
    (3,  P1,   "01 &nbsp;/&nbsp; What it records",            "in",  "A production record for resin pouring"),
    (4,  None, "02 &nbsp;/&nbsp; How it fits together",       "in",  None),
    (6,  None, "03 &nbsp;/&nbsp; The operator terminal",      "in",  None),
    (7,  None, "04 &nbsp;/&nbsp; Lot traceability",           "in",  None),
    (8,  None, "05 &nbsp;/&nbsp; What comes out of it",       "in",  None),
    (13, None, "05 &nbsp;/&nbsp; What comes out of it",       "in",  None),
    (14, None, "05 &nbsp;/&nbsp; What comes out of it",       "in",  None),
    (11, None, "06 &nbsp;/&nbsp; The floor as it is now",     "in",  None),
    (17, None, "07 &nbsp;/&nbsp; Who can do what",            "in",  None),
    (15, None, "08 &nbsp;/&nbsp; Running it",                 "in",  None),
    (16, None, "08 &nbsp;/&nbsp; Running it",                 "in",  None),
    # ---- Part Two: switches, not requirements
    (5,  P2,   "09 &nbsp;/&nbsp; Assigning work to stations", "opt", "Work orders"),
    (9,  None, "10 &nbsp;/&nbsp; Fill weight and giveaway",   "opt", None),
    (10, None, "10 &nbsp;/&nbsp; Fill weight and giveaway",   "opt", None),
    (12, None, "11 &nbsp;/&nbsp; Reactors and the floor display", "opt", None),
    # ---- Appendices
    (18, PA,   "Appendix A &nbsp;/&nbsp; Guide &mdash; Operator",      None, None),
    (19, None, "Appendix A &nbsp;/&nbsp; Guide &mdash; Operator",      None, None),
    (20, None, "Appendix A &nbsp;/&nbsp; Guide &mdash; Operator",      None, None),
    (21, None, "Appendix A &nbsp;/&nbsp; Guide &mdash; Manager",       "opt", None),
    (22, None, "Appendix A &nbsp;/&nbsp; Guide &mdash; Manager",       None, None),
    (23, None, "Appendix A &nbsp;/&nbsp; Guide &mdash; Administrator", None, None),
    ("APPENDIX_B", None, None, None, None),
    (26, None, "Appendix C &nbsp;/&nbsp; How it is tested",   None, None),
    (27, None, "Appendix D &nbsp;/&nbsp; Built, not in service", "no", None),
]


def split_sections(html):
    return re.findall(r'<section class="page[^"]*">.*?</section>', html, re.S)


def h2_of(sec):
    m = re.search(r"<h2>(.*?)</h2>", sec, re.S)
    return m.group(1).strip() if m else ""


def rewrite_head(sec, band, eyebrow, status, new_h2):
    """Replace a page's section header with the banded, status-marked form."""
    old = re.search(r'<div class="sec-head">.*?</div>\s*(?=<)', sec, re.S)
    if not old:
        return sec
    h2 = new_h2 if new_h2 is not None else h2_of(sec)
    parts = ['<div class="sec-head">']
    if band:
        parts.append(f'<div class="partband">{band}</div>')
    parts.append('<div class="hrow">')
    parts.append(f'<span class="eyebrow">{eyebrow}</span>')
    if status:
        label = {"in": "In service", "opt": "Optional",
                 "no": "Not in service"}[status]
        parts.append(f'<span class="status {status}">{label}</span>')
    parts.append("</div>")
    parts.append(f"<h2>{h2}</h2></div>\n  ")
    return sec[:old.start()] + "".join(parts) + sec[old.end():]


def rewrite_folio(sec, page_no):
    return re.sub(
        r'<div class="folio">.*?</div>',
        f'<div class="folio"><span>{FOLIO_LABEL}</span><span>{page_no}</span></div>',
        sec, flags=re.S)


# ------------------------------------------------------------------ new pages --
def cover():
    return f"""<section class="page cover">
  <img class="logo" src="assets/formlabs_logo.png" alt="Formlabs">
  <h1>Resin Pouring &mdash; Production Logging</h1>
  <div class="sub">Operations Handbook</div>
  <div class="rule"></div>
  <div class="blurb">An hourly production record for the pouring station, kept by the operators on
  the phones they already carry. Part One is what runs today and what comes out of it. Part Two is
  what the same record can be asked to do, each of which is a setting rather than a requirement.</div>
  <div class="meta">
    <div>Release<b>Version 3.11</b></div>
    <div>Platform<b>Streamlit &middot; PostgreSQL</b></div>
    <div>Scope<b>Resin Pouring</b></div>
    <div>Issued<b>September 2026</b></div>
  </div>
</section>"""


def contents(rows):
    """rows: list of (kind, num, title, desc, page)."""
    out = ['<section class="page">',
           '  <div class="sec-head"><span class="eyebrow">Contents</span>'
           '<h2>What is in this handbook</h2></div>',
           '  <p class="lead" style="margin-bottom:12pt;">Part One is the system as it runs: one '
           'screen an operator uses, and everything read back out of what they enter. '
           '<strong>Nothing in it requires an entry from anyone but the operator.</strong> Part Two '
           'is what the same record supports if it is wanted, each one a setting that is switched '
           'off until somebody switches it on.</p>',
           '  <div class="toc">']
    last_band = None
    for kind, num, title, desc, page in rows:
        if kind != last_band:
            out.append(f'    <div class="toc-band">{kind}</div>')
            last_band = kind
        out.append(f'    <div class="row"><span class="num">{num}</span>'
                   f'<span class="t">{title}</span><span class="d">{desc}</span>'
                   f'<span class="pg">{page}</span></div>')
    out.append("  </div>")
    # Said once, plainly, rather than left for a reader to infer from the
    # length of the document. A handbook that describes more than is being
    # proposed has to say which is which, or the whole of it reads as the ask.
    out.append('  <div class="note" style="margin-top:14pt;">'
               '<span class="eyebrow">On scope</span>'
               '<p>This system was built on the floor alongside the job, and it covers more ground '
               'than the plant needs today. The marker on each section says which is which: '
               '<b>In service</b> runs now; <b>Optional</b> is finished and switched off until '
               'somebody wants it; <b>Not in service</b> was built to find out whether an approach '
               'works, with nothing depending on it. <b>Part One is what is being proposed</b> '
               '&mdash; the rest is here so the capability is known, not because it is being asked '
               'for.</p></div>')
    out.append(f'  <div class="folio"><span>{FOLIO_LABEL}</span><span>2</span></div>')
    out.append("</section>")
    return "\n".join(out)


APPENDIX_B = """<section class="page">
  <div class="sec-head"><div class="hrow"><span class="eyebrow">Appendix B &nbsp;/&nbsp; Reading the screen on the floor</span></div><h2>Readability where the work happens</h2></div>
  <p class="lead" style="margin-bottom:12pt;">A phone held in a gloved hand at arm's length, in a
  room lit for pouring resin, is a different reading problem from an office monitor. These are the
  settings that address it. All of them are per-user and remembered; none of them changes what is
  recorded.</p>

  <div class="grid2" style="margin-bottom:12pt;">
    <div class="card"><span class="tag">Gloves</span><h4>Glove mode</h4>
      <p>Nitrile still registers on a touchscreen, but precision drops, and the pouring form asks for
      number steppers and a lot field. One toggle pushes every target past the accessibility touch
      size and scales the type. It is remembered against the <em>terminal</em>, not the account
      &mdash; being gloved is a property of where you are standing, not of who you are.</p></div>
    <div class="card"><span class="tag">Lighting</span><h4>Light and dark</h4>
      <p>A dark screen is unreadable under bright shop lighting and a light one is glare on a wall
      display at night, so both exist and the operator picks. The choice follows the account, so a
      shared terminal does not undo it.</p></div>
    <div class="card"><span class="tag">Contrast</span><h4>Measured, not assumed</h4>
      <p>Text is checked against the accessibility floor of 4.5:1 rather than eyeballed. The check
      found real failures in themes already in use &mdash; card labels in the default, and again
      across the sidebar, widget labels and popovers, where the worst measured 1.01:1. All fixed, and
      an audit screen re-runs the measurement on demand, so it is something you can see rather than
      something that was checked once.</p></div>
    <div class="card"><span class="tag">Nights</span><h4>Automatic dimming</h4>
      <p>Derived from the plant's own configured shift times rather than a fixed hour, because
      &ldquo;night&rdquo; here means &ldquo;not the day shift&rdquo;. A gentle brightness and warmth
      reduction rather than a different set of colours. Photographs are exempt, so a lot label under
      review keeps its true colour.</p></div>
  </div>

  <h3>Resin colour, and why colour alone was not enough</h3>
  <p>Wherever a resin is named it carries the colour from the plant's own master sheet, so screen and
  sheet read as one document; a new formulation takes its family's colour from its name. But five
  pairs in that palette are the same colour to the eye, and a Clear/Rigid mix-up is exactly what the
  lot check exists to catch &mdash; so each chip also carries a <strong>texture</strong> from the
  resin family: Clear V4 and Clear V4.1 match, Clear and Rigid cannot. Texture survives greyscale
  printing and colour blindness, which a colour alone does not.</p>

  <figure style="margin-top:10pt;"><img class="sml" src="figs_print/theme_paper_white.png"
       alt="The same screen in a light theme"
       style="max-height:1.2in; object-position:center 38%;">
    <figcaption><b>The same screen, light.</b> Themes change presentation only &mdash; every figure,
    filter and control is identical, so a handbook page describes one screen regardless of how the
    reader has theirs set.</figcaption></figure>

  <div class="folio"><span>__FOLIO__</span><span>__PAGE__</span></div>
</section>"""


# ---------------------------------------------------------- per-page rewrites --
# Applied after re-ordering, keyed by source page number.
EDITS = {
    3: [
        # The overview led with an architecture sentence and six figures, two
        # of which - screens and themes - measured the author's effort rather
        # than the plant's benefit.
        ("""  <div class="grid3" style="margin:16pt 0 14pt;">
    <div class="stat"><span class="n">18</span><span class="l">screens, from the operator terminal to the IT console</span></div>
    <div class="stat"><span class="n">3</span><span class="l">roles, each seeing only what its job needs</span></div>
    <div class="stat"><span class="n">18</span><span class="l">database tables of production, quality and configuration</span></div>
  </div>
  <div class="grid3" style="margin-bottom:16pt;">
    <div class="stat"><span class="n">2</span><span class="l">shifts, a plant setting rather than an assumption in the code</span></div>
    <div class="stat"><span class="n">34</span><span class="l">interface themes, six of them light, for readability in different conditions</span></div>
    <div class="stat"><span class="n">880</span><span class="l">automated checks run before a release, including a browser driven through a shift</span></div>
  </div>""",
         """  <div class="grid3" style="margin:16pt 0 14pt;">
    <div class="stat"><span class="n">1</span><span class="l">screen an operator uses, on the phone already in their pocket</span></div>
    <div class="stat"><span class="n">0</span><span class="l">entries required from a manager for the record to be kept</span></div>
    <div class="stat"><span class="n">3</span><span class="l">roles, each seeing only what its job needs</span></div>
  </div>
  <div class="grid3" style="margin-bottom:16pt;">
    <div class="stat"><span class="n">2</span><span class="l">shifts, a plant setting rather than an assumption in the code</span></div>
    <div class="stat"><span class="n">18</span><span class="l">database tables of production, quality and configuration</span></div>
    <div class="stat"><span class="n">923</span><span class="l">automated checks run before a release, including a browser driven through a shift</span></div>
  </div>"""),
    ],
    7: [
        ('<img src="figs_print/13b_gate_rps.png" alt="The same check on an RPS jug"\n'
         '       style="max-height:1.15in;">',
         '<img src="figs_print/13b_gate_rps.png" alt="The same check on an RPS jug"\n'
         '       style="max-height:0.98in;">'),
        ("A mismatch does not stop the line; it requires an explanation, because a control that halts\n"
         "    production is one people learn to work around. Every flag and every pulled container reaches the\n"
         "    manager's review page.",
         "A mismatch does not stop the line; it asks for an explanation, because a control that halts\n"
         "    production is one people learn to work around. Every flag and every pulled container reaches\n"
         "    the manager's review page."),
    ],
    # NOTE: this key appeared twice while this file was being written, and a
    # duplicate key in a dict literal keeps only the last one - which silently
    # dropped the stats rewrite and shipped a page still boasting "34 interface
    # themes" in a document whose whole point was not to. Both sets of edits
    # for a page belong in one list.
    3: [
        ("Every capability described in this\n  handbook past section 3 works the same way",
         "Everything in Part Two of this\n  handbook works the same way"),
        ("both are described in section 14 rather than here",
         "both are described in Appendix D rather than here"),
    ],
    5: [
        ("the operator\n  terminal on the next page is complete without it",
         "the operator\n  terminal in Part One is complete without it"),
    ],
    6: [
        # The figure on this page was of the assigned-runs block - the optional
        # feature - on the page that describes the screen in service. Anybody
        # reading the pictures got the opposite of what the section says.
        ('<figure><img class="med" src="figs_print/20_activeruns.png" alt="Active runs on the operator terminal">\n'
         '    <figcaption><b>Active runs at this station.</b> Reactor, container format, dispatching manager and live\n'
         '    progress. The lot is masked for operators &mdash; see section 4.</figcaption></figure>',
         '<figure><img class="med" src="figs_print/20_terminal.png" alt="The pouring log on the operator terminal">\n'
         '    <figcaption><b>The hourly log.</b> Station and material, the lot read off the container, then the\n'
         '    counts. This is the screen in full &mdash; there is nothing above it and nothing after the submit\n'
         '    button.</figcaption></figure>'),
    ],
    18: [
        # This told an operator to go and find their lead whenever no run was
        # listed, which in a plant that does not dispatch runs is every hour
        # of every shift.
        ('<h4>Check the run you have been assigned</h4>\n'
         '    <p>Runs assigned to your station appear at the top with reactor, container format and live progress. If\n'
         '    nothing is listed, tell your lead before pouring &mdash; your units will still be recorded, but they\n'
         '    will not count toward a work order.</p>',
         '<h4>Check the run, if your plant assigns them</h4>\n'
         '    <p>Work orders are optional and off unless the plant turns them on. Where they are in use, a run\n'
         '    assigned to your station appears at the top with reactor, container format and live progress, and\n'
         '    if nothing is listed you can mention it to your lead afterwards &mdash; your units are recorded\n'
         '    either way. Where they are not in use the screen never mentions runs, and there is nothing here\n'
         '    to check.</p>'),
    ],
    21: [
        # Every step on this page presumes work orders are in use. Marked and
        # said, so a manager in a plant that only logs does not read it as a
        # list of things they are expected to be doing.
        ('<h2>Dispatching the day</h2></div>',
         '<h2>Dispatching the day</h2></div>\n'
         '  <p class="lead" style="margin-bottom:11pt;">This page applies only where work orders are '
         'switched on. Where they are not, a manager enters nothing at all &mdash; the next page, '
         'reading the floor and closing the day, is the whole of the role.</p>'),
    ],
    10: [
        ("The machine-integration gateway described in section 14 already carries a serial adapter written",
         "The machine-integration gateway described in Appendix D already carries a serial adapter written"),
    ],
    27: [
        # The registry screen is real, complete and deliberately unreachable.
        # Saying only "a gateway exists" left a 15KB page unaccounted for, and
        # a reader who found it by URL would reasonably wonder what else the
        # document had left out.
        ("Readings would write through the same logging path the operator screen uses, so analytics and run\n"
         "      tracking would need no changes.",
         "Readings would write through the same logging path the operator screen uses, so analytics and\n"
         "run tracking would need no changes. A registry screen for it is written &mdash; add a machine, "
         "point it at the pump station it sits on, map its raw tags &mdash; and is deliberately not linked "
         "from anywhere in the application, so it cannot be reached by an administrator who has not been "
         "told it is there."),
        ("<strong>None of it has been tested against real equipment.</strong> The\n"
         "      adapters were written to cover whatever the scales or pump controllers turn out to speak; which of them\n"
         "      is correct is unknown until someone connects one.",
         "<strong>None of it has been tested against real equipment.</strong> The adapters were written to "
         "cover whatever the scales or pump controllers turn out to speak; which of them is correct is "
         "unknown until someone connects one. Until then the screen stays unlinked rather than deleted, "
         "so nothing is lost if the plant ever wants it."),
        ("Two things exist in the codebase that are <strong>not in use and\n  not decided on</strong>.",
         "Two things exist in the codebase that are <strong>not in use and not decided on</strong>."),
    ],
    26: [
        ('<span class="n">839</span><span class="l">assertions across eight suites',
         '<span class="n">869</span><span class="l">assertions across eight suites'),
        ('<span class="n">23</span><span class="l">checks driving a real browser',
         '<span class="n">35</span><span class="l">checks driving a real browser'),
        ("All eight migrations are applied to an empty database",
         "All nine migrations are applied to an empty database"),
        ('<span class="n">18</span><span class="l">screens rendered and checked for errors on every pass</span>',
         '<span class="n">19</span><span class="l">screens rendered and checked for errors on every pass</span>'),
    ],
}


def main():
    html = SRC.read_text(encoding="utf-8")
    head, body = html.split("</head>", 1)
    head = head.replace("</style>", EXTRA_CSS + "\n/* contents banding */\n"
                        ".toc-band{font-family:var(--mono); font-size:6.8pt; letter-spacing:.16em;\n"
                        "          text-transform:uppercase; color:var(--accent); margin:11pt 0 3pt;}\n"
                        ".toc .row:first-of-type{border-top:none;}\n</style>")

    secs = split_sections(html)
    if len(secs) != 27:
        raise SystemExit(f"expected 27 source pages, found {len(secs)}")

    # Pass one: work out the finished page number of every entry, so the
    # contents can be generated rather than kept in step by hand.
    pages, page_no = [], 3          # 1 cover, 2 contents
    for src, band, eyebrow, status, new_h2 in ORDER:
        pages.append((src, band, eyebrow, status, new_h2, page_no))
        page_no += 1

    # Pass two: build the contents rows from the same table.
    rows, seen = [], set()
    band_name = {P1: "Part One &mdash; in service",
                 P2: "Part Two &mdash; available if wanted",
                 PA: "Appendices"}
    current = "Part One &mdash; in service"
    desc = {
        "01": "What the record holds, and what it asks of anyone",
        "02": "One database, and every screen a window onto it",
        "03": "The one screen an operator uses",
        "04": "Which lot went into which containers",
        "05": "Scrap, trends, exports and the shift handover",
        "06": "The live view of the floor as it stands",
        "07": "Roles, and what each one can reach",
        "08": "Backups, accounts, and keeping the record honest",
        "09": "Dispatching runs to stations and tracking them",
        "10": "Recording what a container actually weighed",
        "11": "Vessel levels and the wall display",
        "A": "Working guides for operator, manager and administrator",
        "B": "Gloves, lighting, contrast and colour on the floor",
        "C": "What is checked before a release, and what that has caught",
        "D": "Built, not in use, and not proposed",
    }
    for src, band, eyebrow, status, new_h2, pno in pages:
        if band:
            current = band_name[band]
        if eyebrow is None:                       # Appendix B, written by hand
            num, title = "Appendix B", "Reading the screen on the floor"
        else:
            num, _, title = eyebrow.partition(" &nbsp;/&nbsp; ")
        # The number column is sized for two digits. "Appendix A" wraps in it,
        # and the word is already on the band above, so only the letter goes
        # in the column.
        num = num.replace("Appendix ", "")
        if num in seen:                           # a section spanning pages
            continue
        seen.add(num)
        rows.append((current, num, title, desc.get(num, ""), pno))

    # Pass three: emit.
    out = [cover(), contents(rows)]
    for src, band, eyebrow, status, new_h2, pno in pages:
        if src == "APPENDIX_B":
            sec = APPENDIX_B.replace("__FOLIO__", FOLIO_LABEL).replace("__PAGE__", str(pno))
            out.append(sec)
            continue
        sec = secs[src - 1]
        for old, new in EDITS.get(src, []):
            if old not in sec:
                raise SystemExit(f"page {src}: edit did not match:\n{old[:90]}")
            sec = sec.replace(old, new, 1)
        sec = rewrite_head(sec, band, eyebrow, status, new_h2)
        sec = rewrite_folio(sec, pno)
        out.append(sec)

    SRC.write_text(head + "</head>\n<body>\n\n" + "\n\n".join(out) + "\n\n</body></html>\n",
                   encoding="utf-8")
    print(f"handbook.html rebuilt: {len(out)} pages")


if __name__ == "__main__":
    main()
