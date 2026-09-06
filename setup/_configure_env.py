"""
_configure_env.py - writes this PC's .env and proves it actually works.

The single most common reason this project "won't run on a new machine"
is not code: it is that .env still holds the previous PC's Postgres
password, and every failure downstream of that - alembic, crud, the app
itself - reports something that says nothing about a password.

So this asks once, writes it, and then CONNECTS before letting setup
continue. If it can't connect it says which of the four things is wrong
(server not running / wrong password / wrong port / no such user)
instead of handing the problem to the next step.

    python setup/_configure_env.py mes        this PC hosts the database
    python setup/_configure_env.py gateway    this PC finds one on the LAN

Exit 0 = .env is good. Exit 1 = stop setup.
"""
import getpass
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

PLACEHOLDERS = {"", "USER", "PASSWORD", "YOURPASSWORD", "CHANGEME", "auto"}


# --------------------------------------------------------------- .env io

def read_env():
    """Every line, in order, so comments and unknown keys survive a rewrite."""
    if ENV.exists():
        return ENV.read_text(encoding="utf-8", errors="replace").splitlines()
    if EXAMPLE.exists():
        return EXAMPLE.read_text(encoding="utf-8", errors="replace").splitlines()
    return []


def get_value(lines, key):
    pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=(.*)$")
    for line in lines:
        m = pat.match(line)
        if m:
            return m.group(1).strip()
    return ""


def set_value(lines, key, value):
    pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    for i, line in enumerate(lines):
        if pat.match(line):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def write_env(lines):
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------- postgres bin

def find_pg_bin():
    """Highest-numbered PostgreSQL\\NN\\bin that actually holds psql.exe."""
    roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PostgreSQL",
        Path(r"C:\Program Files (x86)\PostgreSQL"),
    ]
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if (child / "bin" / "psql.exe").exists():
                try:
                    found.append((int(child.name), child / "bin"))
                except ValueError:
                    found.append((0, child / "bin"))
    if not found:
        return ""
    found.sort(reverse=True)
    return str(found[0][1])


# ------------------------------------------------------------ connection

def split_url(url):
    """user, password, host, port, dbname out of a postgres URL. Blanks if it
    isn't one - a half-filled .env is normal here, that's why we're asking."""
    m = re.match(
        r"^postgres(?:ql)?://([^:/@]*):?([^@]*)@([^:/]+):?(\d*)/(.*)$", url or ""
    )
    if not m:
        return "", "", "", "", ""
    # The password is percent-encoded in the URL (see set_value below), so
    # decode it here - otherwise a password with an @ or # in it comes back
    # as gibberish and the "wrong password" message is a lie.
    return (m.group(1), unquote(m.group(2)), m.group(3),
            m.group(4), m.group(5))


def try_connect(user, password, host, port, dbname="postgres"):
    """(ok, message). Connects to the maintenance database, not the app's -
    the app's may not exist yet, and that is not an error worth stopping for."""
    try:
        import psycopg2
    except ImportError:
        return None, "psycopg2 not installed yet - skipping the connection test."
    try:
        conn = psycopg2.connect(
            user=user, password=password, host=host,
            port=int(port or 5432), dbname=dbname, connect_timeout=6,
        )
        conn.close()
        return True, "Connected."
    except Exception as exc:  # noqa: BLE001 - the text is the whole point
        return False, str(exc).strip().splitlines()[0]


def explain(err):
    low = err.lower()
    if "password authentication failed" in low:
        return ("The password for that user is wrong.\n"
                "       This is the same password you typed into the\n"
                "       PostgreSQL installer, not your Windows password.")
    if "could not connect" in low or "connection refused" in low or "timeout" in low:
        return ("Nothing is listening there.\n"
                "       The PostgreSQL service probably isn't running:\n"
                "       press Win+R, type services.msc, find\n"
                "       postgresql-x64-... and start it.")
    if "does not exist" in low and "role" in low:
        return ("There is no user by that name in PostgreSQL.\n"
                "       On a standard install the user is: postgres")
    return "See the error text above."


def ask(prompt, default=""):
    shown = f" [{default}]" if default else ""
    got = input(f"     {prompt}{shown}: ").strip()
    return got or default


# ----------------------------------------------------------------- modes

def configure_mes(lines):
    url = get_value(lines, "DB_URL")
    u_user, u_pass, u_host, u_port, u_db = split_url(url)

    print()
    print("     This PC will host the database. I need its PostgreSQL login.")
    print("     (The password you set when PostgreSQL was installed.)")
    print()

    user = u_user if u_user not in PLACEHOLDERS else "postgres"
    host = u_host if u_host not in PLACEHOLDERS else "localhost"
    port = u_port or "5432"
    dbname = u_db if u_db not in PLACEHOLDERS else "formlabs_mes"

    for attempt in range(1, 4):
        user = ask("PostgreSQL user", user)
        password = getpass.getpass(f"     Password for {user} (typing is hidden): ")
        if not password and u_pass not in PLACEHOLDERS:
            password = u_pass
            print("     (kept the password already in .env)")

        ok, msg = try_connect(user, password, host, port)
        if ok is None:
            print(f"     {msg}")
            break
        if ok:
            print("     Connected to PostgreSQL.")
            break
        print()
        print(f"     [X] {msg}")
        print(f"         {explain(msg)}")
        print()
        if attempt == 3:
            print("     Giving up after three tries. Nothing was changed.")
            return 1
        print(f"     Try again ({attempt}/3).")
    else:
        return 1

    # Percent-encode the password: Postgres passwords routinely contain @ / #
    # : and ?, every one of which means something else inside a URL. SQLAlchemy
    # and psycopg2 both decode it back. PG_PASS stays raw - the pg_dump/psql
    # tooling passes it as an environment variable, not as part of a URL.
    lines = set_value(lines, "DB_URL",
                      f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
                      f"@{host}:{port}/{dbname}")
    lines = set_value(lines, "PG_PASS", password)

    pg_bin = find_pg_bin()
    if pg_bin:
        lines = set_value(lines, "PG_BIN_DIR", pg_bin)
        print(f"     PG_BIN_DIR set to {pg_bin}")
    elif not get_value(lines, "PG_BIN_DIR"):
        print("     [!] Couldn't find pg_dump/psql automatically. Backups and")
        print("         restores will not work until PG_BIN_DIR is set in .env.")

    write_env(lines)
    print(f"     Wrote {ENV}")
    return 0


def configure_gateway(lines):
    print()
    print("     This PC only talks to machines. It does NOT need PostgreSQL")
    print("     installed - it finds the MES database on the network.")
    print()
    print("     It still needs a login for that database. Use the same user")
    print("     and password the MES PC uses.")
    print()

    user = get_value(lines, "DB_USER") or "postgres"
    user = ask("PostgreSQL user on the MES PC", user)
    password = getpass.getpass("     Password (typing is hidden): ")
    if not password:
        password = get_value(lines, "DB_PASSWORD")
        if password:
            print("     (kept the password already in .env)")
        else:
            print("     [X] A password is required.")
            return 1

    lines = set_value(lines, "DB_USER", user)
    lines = set_value(lines, "DB_PASSWORD", password)

    # "auto" is the sentinel run_gateway.py checks for: it means "discover
    # the database over mDNS", and stops it treating a stale URL copied
    # from another PC as a real target.
    current = get_value(lines, "DB_URL")
    if not current or split_url(current)[0] in PLACEHOLDERS:
        lines = set_value(lines, "DB_URL", "auto")

    write_env(lines)
    print(f"     Wrote {ENV}")
    print()
    print("     If this PC's network blocks mDNS between machines, set")
    print("     GATEWAY_DB_URL in .env to the MES PC directly, e.g.")
    print(f"       GATEWAY_DB_URL=postgresql://{user}:PASSWORD@MES-PC-NAME:5432/formlabs_mes")
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "mes"
    lines = read_env()
    if mode == "gateway":
        return configure_gateway(lines)
    return configure_mes(lines)


if __name__ == "__main__":
    sys.exit(main())
