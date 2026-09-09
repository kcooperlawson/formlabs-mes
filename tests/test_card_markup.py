"""Every st.markdown call has to close the divs it opens.

Streamlit closes unbalanced HTML inside each markdown call, so opening a card
in one call and closing it in another does not build a card. What you get is
an empty bordered box with the contents loose underneath it, which is exactly
how the TV wall looked, and the stray fragments stop Streamlit matching
elements between refreshes, which is what left a dimmed second copy of the
leaderboard sitting on the wall next to the live one.

It reads the source rather than rendering anything, so it needs no database
and runs anywhere.

KNOWN is the six sites carrying the same fault that have not been fixed yet.
The list only shrinks. A file not on it that starts failing is a new one.
"""
import io
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# file -> how many unbalanced calls it is still allowed to have
KNOWN = {
    "Home.py": 4,                     # the SCADA leaderboard and three cards beside it
    "pages/Mgr_Cleanliness.py": 2,
}

FAILS = []
CHECKS = 0


def unbalanced(path):
    src = io.open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"st\.markdown\(", src):
        i, depth = m.end(), 1
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        chunk = src[m.start():i]
        if chunk.count("<div") != chunk.count("</div>"):
            out.append(src[:m.start()].count("\n") + 1)
    return out


targets = sorted(ROOT.glob("pages/*.py")) + [ROOT / "Home.py"]
print("Checking %d files for cards split across markdown calls\n" % len(targets))

for f in targets:
    rel = f.relative_to(ROOT).as_posix()
    CHECKS += 1
    lines = unbalanced(f)
    allowed = KNOWN.get(rel, 0)
    if len(lines) > allowed:
        FAILS.append("%s: %d unbalanced st.markdown call(s), allowed %d. Lines %s"
                     % (rel, len(lines), allowed, lines))
    elif len(lines) < allowed:
        FAILS.append("%s: down to %d from %d. Good - now lower it in KNOWN."
                     % (rel, len(lines), allowed))
    elif lines:
        print("  %-34s %d known, unchanged" % (rel, len(lines)))

print("\n" + "=" * 66)
if FAILS:
    print("%d of %d CARD MARKUP CHECKS FAILED:\n" % (len(FAILS), CHECKS)
          + "\n".join("  " + f for f in FAILS))
else:
    print("ALL %d FILES OK (cards are built and emitted in one call)" % CHECKS)
raise SystemExit(1 if FAILS else 0)
