"""Draw the print-build pieces on their own, before any page gets them.

The same approach that got the vessels right: render the pure functions onto
one sheet against the app's own background, look at it, fix what reads badly,
and only then wire it into a page that operators depend on.
"""
import base64
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import print_build as pb  # noqa: E402

OUT = "/tmp/build_sheet.html"


def b64(name):
    with open(os.path.join(ROOT, "assets", name), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


cart = b64("resin_cartridge.png")
printer = b64("form_printer.png")

cells = []
for pct, done, target in ((0, 0, 900), (18, 162, 900), (47, 423, 900),
                          (78, 702, 900), (100, 900, 900)):
    cells.append(
        f'<div style="flex:1; min-width:150px;">'
        f'{pb.cartridge_build(pct, cart, done, target, height_px=300, uid=f"c{pct}")}'
        f'</div>')

bars = "".join(
    f'<div style="margin:14px 0;">'
    f'<div style="font:600 0.72rem monospace; color:#7C8DB0; letter-spacing:.1em;'
    f' margin-bottom:5px;">{lbl}</div>{pb.layer_bar(p, colour=c)}</div>'
    for lbl, p, c in (("SHIFT OUTPUT 62%", 62, "#00D2FF"),
                      ("LOT 41%", 41, "#F97316"),
                      ("TANK 88%", 88, "#10B981"),
                      ("EMPTY 0%", 0, "#00D2FF"),
                      ("FULL 100%", 100, "#10B981")))

html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
 body {{ background:#02040A; color:#E6EDF7; font-family:'Segoe UI',sans-serif;
        margin:0; padding:28px; }}
 h2 {{ font-size:0.8rem; letter-spacing:0.22em; color:#5A6B8C; font-weight:600;
       text-transform:uppercase; margin:34px 0 16px; border-bottom:1px solid #16203A;
       padding-bottom:8px; }}
 .row {{ display:flex; gap:26px; align-items:flex-end; }}
</style></head><body>
<h2>Shift build &mdash; wall display</h2>
<div class="row">{''.join(cells)}</div>
<h2>Layer progress bars</h2>
<div style="max-width:520px;">{bars}</div>
<h2>Sign-in laser</h2>
<div style="max-width:420px; background:#070C16; border:1px solid #16203A;
     border-radius:12px; padding:24px;">
{pb.laser_sweep(printer, height_px=220, uid="signin")}
</div>
</body></html>"""

with open(OUT, "w") as fh:
    fh.write(html)
print(OUT)
