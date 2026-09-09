"""requirements.txt describes something that actually runs.

The failure this exists to prevent is quiet and only shows up on a machine
that is not this one. requirements.txt carried numpy==2.5.2, which needs
Python 3.12; the deployment runs 3.11 and had 2.4.6 installed. Nothing noticed,
because a machine that is already set up never reads that file again. What it
would have done is stop a fresh install dead at step 3 of install_mes.bat, on
any PC with 3.11 - which is most work PCs - and it silently killed the offline
package bundle that exists so a locked-down machine does not need the internet.

Two rules, both checkable without a network:

  * every third-party module the application imports is in the file, because
    one that is missing installs fine here and fails on a new machine at the
    first page that imports it

  * the file itself is coherent - no duplicate names, no pin without a
    version, nothing listed twice under two spellings

What this cannot check is whether a pinned version exists for the Python the
plant PC runs. That needs PyPI, and a test suite that fails when the network
is down is a test suite people learn to skip. It is checked by hand when the
file changes, with a resolve against the target platform:

    pip install --dry-run --ignore-installed -r requirements.txt \\
        --python-version 3.11 --platform win_amd64 --only-binary=:all: \\
        --target /tmp/x
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES, COUNT = [], 0


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


# The name you import is not always the name you install.
IMPORT_TO_PACKAGE = {
    "dotenv": "python-dotenv",
    "psycopg2": "psycopg2-binary",
    "dateutil": "python-dateutil",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "sqlalchemy": "sqlalchemy",
    "streamlit_lottie": "streamlit-lottie",
    "extra_streamlit_components": "extra-streamlit-components",
    "multipart": "python-multipart",
}

# Imported only by the Device Gateway, which has its own requirements file and
# is installed separately. Every adapter imports its library inside connect(),
# so the application runs without any of them.
GATEWAY_ONLY = {"pymodbus", "serial", "opcua", "paho", "asyncua"}

# Ours, or the standard library's.
LOCAL = ({p.stem for p in ROOT.glob("*.py")}
         | {p.stem for p in (ROOT / "pages").glob("*.py")}
         | {"device_gateway", "migrations", "tests", "dev", "setup", "assets"}
         | set(sys.stdlib_module_names))


def parse_requirements(path):
    """(name -> version) plus the raw order, ignoring comments and blanks."""
    pins, order = {}, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        name = line.split("==")[0].split(">=")[0].split("<")[0].strip()
        version = line.split("==")[1].strip() if "==" in line else ""
        pins[name.lower().replace("_", "-")] = version
        order.append(name)
    return pins, order


def app_imports():
    """Every third-party module name the application imports."""
    found = set()
    files = ([ROOT / "Home.py"] + sorted(ROOT.glob("*.py"))
             + sorted((ROOT / "pages").glob("*.py")))
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            check(False, f"{path.name} does not parse")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return {m for m in found if m not in LOCAL and m not in GATEWAY_ONLY}


print("=" * 62)
print("REQUIREMENTS")
print("=" * 62)

req = ROOT / "requirements.txt"
check(req.is_file(), "there is a requirements.txt")
pins, order = parse_requirements(req)
print(f"\n  {len(pins)} packages pinned")

# --- the file is coherent -------------------------------------------------
seen = {}
for name in order:
    key = name.lower().replace("_", "-")
    check(key not in seen, f"{name} is listed twice (also as {seen.get(key)})")
    seen[key] = name
for name, version in pins.items():
    check(bool(version) or name == "alembic",
          f"{name} has no version - a fresh install would take whatever is newest")

# --- every import is covered ---------------------------------------------
print("\n  Imports the application makes")
missing = []
for module in sorted(app_imports()):
    package = IMPORT_TO_PACKAGE.get(module, module).lower().replace("_", "-")
    if package not in pins:
        missing.append(f"{module} (would install as {package})")
    check(package in pins,
          f"{module} is imported but not in requirements.txt")
if not missing:
    print(f"    all {len(app_imports())} covered")

# --- and nothing is in there for a library the app dropped ----------------
# Not every pin is imported directly - most of these are Streamlit's own
# dependencies, pinned so an install is reproducible. This checks the specific
# ones that were left behind when the Google Sheets sync moved to a webhook,
# because ten unused pins are ten more ways for a fresh install to fail on a
# locked-down network.
print("\n  Nothing left over")
for gone in ("gspread", "google-auth", "google-auth-oauthlib", "oauthlib",
             "requests-oauthlib", "pyasn1", "pyasn1-modules"):
    check(gone not in pins,
          f"{gone} is pinned, and nothing imports it - the sync uses a webhook")

print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
