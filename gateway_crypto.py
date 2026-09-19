"""gateway_crypto.py - encrypts Device Gateway connection details at rest.

Finding 7 in the security posture doc: connection_json on the devices
table can hold a username and password for an MQTT broker or an OPC-UA
endpoint, and until now it sat there as plain text - readable by anyone
who could query the database directly or read a backup file.

device_crud.py is the only code that ever touches connection_json (see
get_device_dict, create_device, update_device) - every page and every
protocol adapter works with a plain `connection` dict and has no idea
this file exists. That is deliberate: encryption lives at exactly one
boundary, so nothing else has to change, and it stays that way if a
future protocol adds new fields to the blob.

The key (GATEWAY_ENCRYPTION_KEY in .env) is created automatically the
first time any device is ever saved - a plant that never touches the
gateway never gets one, and nobody has to remember a setup step to get
one before it matters. Losing .env without a backup means losing the
ability to decrypt existing device credentials, the same way it already
means losing the ability to reach the database - re-entering them on
the admin page is the recovery, not a new kind of failure this file
introduces.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"


def _append_to_env(name: str, value: str) -> None:
    """Adds one KEY=value line to .env, creating the file if it does not
    exist yet. Never rewrites or reorders any existing line."""
    line = f"{name}={value}\n"
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            text += "\n"
        ENV_FILE.write_text(text + line, encoding="utf-8")
    else:
        ENV_FILE.write_text(line, encoding="utf-8")


def _get_or_create_key() -> bytes:
    """The Fernet key used to encrypt. Created once, on first use, and
    appended to .env so every later read (including after a restart) sees
    the same key. Never called from the read path - decrypting must not
    invent a key that cannot possibly match anything already stored."""
    key = os.getenv("GATEWAY_ENCRYPTION_KEY")
    if key:
        return key.encode("ascii")

    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key()
    _append_to_env("GATEWAY_ENCRYPTION_KEY", new_key.decode("ascii"))
    os.environ["GATEWAY_ENCRYPTION_KEY"] = new_key.decode("ascii")
    return new_key


def encrypt_connection(connection: dict) -> str:
    """dict -> the string that gets stored in Device.connection_json."""
    from cryptography.fernet import Fernet
    key = _get_or_create_key()
    token = Fernet(key).encrypt(json.dumps(connection or {}).encode("utf-8"))
    return token.decode("ascii")


def decrypt_connection(stored: str) -> dict:
    """The reverse of encrypt_connection - what get_device_dict calls.

    Falls back to reading `stored` as plain JSON if it is not (or cannot
    be read as) a Fernet token, so a row written before this fix, or a
    read attempted with no key configured at all, still comes back as a
    dict instead of raising.
    """
    if not stored:
        return {}

    key = os.getenv("GATEWAY_ENCRYPTION_KEY")
    if key:
        try:
            from cryptography.fernet import Fernet
            plaintext = Fernet(key.encode("ascii")).decrypt(stored.encode("ascii"))
            return json.loads(plaintext.decode("utf-8"))
        except Exception:
            pass  # not a token this key can open - fall through to plain JSON

    try:
        return json.loads(stored)
    except Exception:
        return {}


class KeyMismatchError(RuntimeError):
    """Raised by decrypt_connection_strict when stored connection details are
    encrypted and this PC's key cannot open them."""


KEY_MISMATCH_HELP = (
    "This PC can't read the device's saved connection details: its "
    "GATEWAY_ENCRYPTION_KEY {problem} the one the MES PC saved them with. "
    "Copy the GATEWAY_ENCRYPTION_KEY line from the MES PC's .env into this "
    "PC's .env, then restart the gateway."
)


def _looks_encrypted(stored: str) -> bool:
    # Every Fernet token starts with version byte 0x80, which is "gAAAAA" in
    # URL-safe base64. Plain JSON starts with "{".
    return stored.lstrip().startswith("gAAAAA")


def decrypt_connection_strict(stored: str) -> dict:
    """decrypt_connection for the gateway's own use, where a wrong key must
    not be quietly turned into an empty dict.

    decrypt_connection's lenient fallback is right for the admin page, but on
    a gateway PC it turned "this PC's .env has a different key" into a device
    with no host or port, which then failed with nothing more than KeyError:
    'host'. The key is created on the MES PC the first time a device is saved,
    so a gateway PC set up before that has no key at all - an easy state to
    be in, and one that deserves a sentence, not a key name.
    """
    if not stored:
        return {}
    if not _looks_encrypted(stored):
        try:
            return json.loads(stored)
        except Exception:
            return {}

    key = os.getenv("GATEWAY_ENCRYPTION_KEY")
    if not key:
        raise KeyMismatchError(KEY_MISMATCH_HELP.format(problem="is missing, so it can't match"))
    try:
        from cryptography.fernet import Fernet
        plaintext = Fernet(key.encode("ascii")).decrypt(stored.encode("ascii"))
    except Exception:
        raise KeyMismatchError(KEY_MISMATCH_HELP.format(problem="doesn't match"))
    return json.loads(plaintext.decode("utf-8"))
