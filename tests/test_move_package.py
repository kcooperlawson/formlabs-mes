"""Unlock_Move_Package.bat carries its own decrypt logic, not just a
pointer to it.

The receiving PC only ever gets two things: the encrypted package and
this one .bat file. It can't also be handed Unlock_Move_Package.ps1
separately - that was the actual bug report that led here: the
"copy BOTH of these files" instructions never mentioned a third file
the .bat silently depended on, so a PC that got only the two listed
files failed with "Unlock_Move_Package.ps1 is missing" and the user
had no idea a second file even existed.

The fix embeds a base64 copy of Unlock_Move_Package.ps1 inside the .bat
itself, after a :PAYLOAD marker - the .bat extracts it to a temp file
and runs that, self-contained, wherever it's copied. Which makes the
embedded copy exactly the kind of thing that quietly drifts: someone
fixes a bug in the real Unlock_Move_Package.ps1, forgets the embedded
copy exists, and ships a .bat that still carries the OLD, broken logic
forever. This is the check that catches that the moment it happens.

To regenerate the embedded payload after editing Unlock_Move_Package.ps1:

    $bytes = [System.IO.File]::ReadAllBytes("Unlock_Move_Package.ps1")
    $b64 = [Convert]::ToBase64String($bytes)
    ($b64 -split '(.{1,76})' | Where-Object { $_ -ne '' }) -join "`n"

...and replace everything after the ":PAYLOAD" line in
Unlock_Move_Package.bat with the result.
"""
import base64
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 66)
print("MOVE PACKAGE: the self-contained unlock tool")
print("=" * 66)

bat_path = ROOT / "Unlock_Move_Package.bat"
ps1_path = ROOT / "Unlock_Move_Package.ps1"
bat_lines = bat_path.read_text(encoding="utf-8").splitlines()

check("the .bat still has its :PAYLOAD marker, exactly once",
      bat_lines.count(":PAYLOAD"), 1)

marker_at = bat_lines.index(":PAYLOAD")
payload_lines = bat_lines[marker_at + 1:]
check("there is a payload after the marker, not an empty tail",
      len(payload_lines) > 0, True)

try:
    embedded_bytes = base64.b64decode("".join(payload_lines))
except Exception as e:
    embedded_bytes = None
    check(f"the embedded payload is valid base64 (got {e})", True, False)

if embedded_bytes is not None:
    real_bytes = ps1_path.read_bytes()
    check("the embedded copy is byte-for-byte the real Unlock_Move_Package.ps1 - "
          "if this fails, regenerate the payload per this file's own docstring",
          embedded_bytes, real_bytes)

# --- the instructions Move_To_New_PC.bat prints match what's actually needed
# The .ps1 legitimately appears elsewhere in this file (it's what actually
# runs the encrypt step on the source PC) - the thing worth pinning down is
# the DONE message specifically, which is what a person actually reads and
# acts on, and that has to ask for exactly the two files a destination PC
# needs, not a third one left over from before the .bat became self-contained.
move_lines = (ROOT / "Move_To_New_PC.bat").read_text(encoding="utf-8").splitlines()
done_at = next(i for i, line in enumerate(move_lines) if "echo  DONE." in line)
done_block = "\n".join(move_lines[done_at:done_at + 20])
check("the DONE message still says to copy BOTH files, not three",
      "Copy BOTH of these files" in done_block, True)
check("...names the self-contained .bat",
      "Unlock_Move_Package.bat" in done_block, True)
check("...and does not also send Unlock_Move_Package.ps1 - it's embedded now",
      "Unlock_Move_Package.ps1" in done_block, False)

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} MOVE PACKAGE CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} MOVE PACKAGE ASSERTIONS PASSED")
sys.exit(1 if FAILS else 0)
