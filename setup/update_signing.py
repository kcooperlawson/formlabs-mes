"""update_signing.py - one canonical way to sign and check an update package.

Shared by dev/make_update.py (which signs a release, on whoever's machine
builds them) and setup/apply_update.py (which checks that signature, on
every plant PC). Living in one file rather than two means the builder and
the checker can never quietly disagree about what a signature covers.

Written for Finding 6 in the security posture doc: the update applier
already checksums every file against the manifest (that catches a
half-copied USB stick), but a checksum only proves a file arrived intact,
not who produced it. Anybody who could write to updates\\ could have code
run as whoever runs the application. Signing the manifest with a private
key that never leaves the machine that builds releases turns that
integrity check into an authenticity check.

Two keys, two very different sensitivities:

  * The PRIVATE key (dev/update_signing_private.pem) signs releases. It
    is created once with --init-keys, never committed (see .gitignore),
    never copied to a plant PC, and losing it means generating a new pair
    and re-shipping the new public key to every install before the next
    release will verify. Back it up somewhere that is not this repo.

  * The PUBLIC key (setup/update_signing_public.pem) checks signatures.
    It is not a secret - it ships with the project like any other file,
    which is the whole point of asymmetric signing: every plant PC can
    verify without being able to sign.

Ed25519 rather than RSA: a signature this small (64 bytes) is cheap to
carry in the manifest as base64, and 'cryptography' has supported it for
years - nothing new to install beyond what the TLS certificate fix
already added.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_KEY_FILE = ROOT / "setup" / "update_signing_public.pem"
PRIVATE_KEY_FILE = ROOT / "dev" / "update_signing_private.pem"


def signable_bytes(manifest: dict) -> bytes:
    """The exact bytes a signature covers.

    Deliberately not "the manifest JSON as written": key order in a dict
    is not something a signature should depend on, and the signature
    field obviously cannot sign itself. This pulls out only the parts
    that describe what the update DOES - which files, with what
    checksums, replacing what version with what, what gets deleted, what
    gets installed - sorts everything, and serializes it one fixed way.
    """
    files = sorted(
        (e["path"].replace("\\", "/"), e["sha256"])
        for e in manifest.get("files", [])
    )
    payload = {
        "from_version": manifest.get("from_version") or None,
        "to_version": manifest.get("to_version") or "",
        "files": files,
        "delete": sorted(r.replace("\\", "/") for r in manifest.get("delete", [])),
        "packages": sorted(manifest.get("packages", [])),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_keypair(private_key_path: Path = PRIVATE_KEY_FILE,
                     public_key_path: Path = PUBLIC_KEY_FILE,
                     force: bool = False):
    """Writes a brand new keypair. Refuses to overwrite an existing private
    key unless force=True - regenerating orphans every plant PC's public
    key until it is redistributed, so this should not happen by accident.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if private_key_path.exists() and not force:
        raise FileExistsError(
            f"{private_key_path} already exists. Delete it first (and "
            f"understand that every plant PC's public key becomes useless "
            f"until you redistribute the new one) if you really mean to "
            f"replace it."
        )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)

    key = Ed25519PrivateKey.generate()
    private_key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    public_key_path.write_bytes(key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return private_key_path, public_key_path


def sign(manifest: dict, private_key_path: Path = PRIVATE_KEY_FILE) -> str:
    """Base64 signature over signable_bytes(manifest). Raises FileNotFoundError
    with a plain message if there is no private key on this machine yet."""
    if not private_key_path.exists():
        raise FileNotFoundError(
            f"no signing key at {private_key_path}. Run:\n"
            f"    python dev/make_update.py --init-keys\n"
            f"once, then keep that file safe and never commit it."
        )
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    key = load_pem_private_key(private_key_path.read_bytes(), password=None)
    signature = key.sign(signable_bytes(manifest))
    return base64.b64encode(signature).decode("ascii")


def verify(manifest: dict, public_key_path: Path = PUBLIC_KEY_FILE) -> tuple[bool, str]:
    """(ok, reason). Never raises - a corrupt key file or a garbled
    signature is exactly the kind of thing this function exists to catch,
    not something that should crash the applier instead of refusing."""
    signature_b64 = manifest.get("signature", "")
    if not signature_b64:
        return False, "this package was not signed"
    if not public_key_path.exists():
        return False, (f"no {public_key_path.name} on this PC to check it "
                       f"against - reinstall from a source you trust")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError:
        return False, "'cryptography' isn't installed - can't check the signature"

    try:
        public_key = load_pem_public_key(public_key_path.read_bytes())
        public_key.verify(base64.b64decode(signature_b64), signable_bytes(manifest))
        return True, "signature verified"
    except InvalidSignature:
        return False, ("signature does not match - this package was changed "
                       "after it was signed, or was never signed with the "
                       "real key")
    except Exception as exc:
        return False, f"could not check the signature ({exc})"
