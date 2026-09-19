"""Serve updates from this PC, so other PCs can fetch them without GitHub.

    START_HERE.bat, option 16
    python setup/update_server.py                      (HTTP, port 8443)
    python setup/update_server.py --token SECRET       (only callers who know it)
    python setup/update_server.py --https              (using certs\\mes.crt/key)

It serves three kinds of thing out of dist\\, read-only:

    /updates.json                 every package here, newest first
    /latest.json                  just the newest one
    /mes_update_PT-V4.08.zip      a package itself

Both listings are generated on the fly from the mes_update_*.zip files in
dist\\, so publishing an update is nothing more than building one and leaving
this running. A plant PC pointed at this address lists exactly what is in
that folder - including older releases, which is what you want on the day a
new one turns out to be wrong.

Trust does not come from this server, and does not need to. Every package is
signed (setup/update_signing.py), and the plant PC checks that signature and
every checksum before it writes a single file - so a package altered on the
way, or served by something pretending to be this PC, is refused there. That
is what makes it safe to serve this over plain HTTP if a certificate is
awkward, and why --token is about keeping strangers out of your logs rather
than about protecting the update itself.

On the plant PC, one line in .env:

    MES_UPDATE_URL=http://your-home-address:8443/latest.json
    MES_UPDATE_TOKEN=SECRET          (only if you used --token)

See api/update_check.py for what it does with that.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_NAME = re.compile(r"^mes_update_[A-Za-z0-9._-]+\.zip$")


def all_packages(directory: Path) -> list:
    """Every package in the folder, newest release first. Sorted by the
    version inside each package, not by file name or date - a rebuilt older
    release must not push itself to the top of a plant PC's list."""
    import sys

    sys.path.insert(0, str(ROOT / "setup"))
    from apply_update import version_tuple

    described = []
    for path in directory.glob("mes_update_*.zip"):
        if not path.is_file():
            continue
        try:
            described.append(describe(path))
        except Exception:
            continue  # not a package, or half-copied: simply not on the list
    described.sort(key=lambda d: version_tuple(d["version"]), reverse=True)
    return described


def newest_package(directory: Path) -> Path | None:
    packages = all_packages(directory)
    return directory / packages[0]["file"] if packages else None


def describe(package: Path) -> dict:
    """What /latest.json says. The version is read from the package's own
    signed manifest, never from the file name - a renamed file cannot talk a
    plant PC into installing something."""
    import zipfile

    with zipfile.ZipFile(package) as zf:
        manifest = json.loads(zf.read("mes_update.json").decode("utf-8"))
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    return {
        "version": manifest.get("to_version", ""),
        "file": package.name,
        "size": package.stat().st_size,
        "sha256": digest,
        "notes": manifest.get("notes", ""),
        "published_at": datetime.fromtimestamp(package.stat().st_mtime, timezone.utc).isoformat(),
    }


def _local_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "THIS-PC-ADDRESS"
    finally:
        s.close()


def make_handler(directory: Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FormlabsMESUpdates/1.0"

        def _deny(self, code: int, message: str):
            body = json.dumps({"error": message}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorised(self) -> bool:
            if not token:
                return True
            return self.headers.get("X-MES-Update-Token", "") == token

        def do_GET(self):  # noqa: N802  (http.server's own naming)
            path = self.path.split("?", 1)[0].lstrip("/")
            if not self._authorised():
                self._deny(401, "this server needs the token in X-MES-Update-Token")
                return

            if path in ("", "latest.json", "updates.json"):
                packages = all_packages(directory)
                if not packages:
                    self._deny(404, f"no mes_update_*.zip in {directory}")
                    return
                payload = {"packages": packages} if path == "updates.json" else packages[0]
                body = json.dumps(payload, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Only ever a package file in this one folder: no paths, no
            # traversal, nothing else on this PC is reachable from here.
            if not PACKAGE_NAME.match(path):
                self._deny(404, "not found")
                return
            target = directory / path
            if not target.is_file():
                self._deny(404, "not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(target.stat().st_size))
            self.end_headers()
            with open(target, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    self.wfile.write(chunk)

        def log_message(self, fmt, *args):
            print(f"  {self.client_address[0]}  {fmt % args}", flush=True)

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--dir", default=str(ROOT / "dist"))
    ap.add_argument("--token", default="", help="require this in the X-MES-Update-Token header")
    ap.add_argument("--https", action="store_true", help="serve over TLS using certs\\mes.crt and certs\\mes.key")
    args = ap.parse_args()

    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        sys.exit(f"{directory} isn't a folder")

    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(directory, args.token))
    scheme = "http"
    if args.https:
        cert, key = ROOT / "certs" / "mes.crt", ROOT / "certs" / "mes.key"
        if not (cert.is_file() and key.is_file()):
            sys.exit("certs\\mes.crt / mes.key are missing - run setup\\generate_tls_cert.py, "
                     "or leave --https off (the package's signature is what protects it either way)")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert), str(key))
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"

    packages = all_packages(directory)
    address = _local_ip()
    print()
    print("  ===================================================")
    print("   Formlabs MES - update server")
    print("  ===================================================")
    print()
    print(f"  Serving {directory}")
    if packages:
        for entry in packages[:8]:
            print(f"    {entry['version']:<12} {entry['size'] / 1024 / 1024:5.1f} MB   {entry['file']}")
        if len(packages) > 8:
            print(f"    ... and {len(packages) - 8} more")
    else:
        print("    (nothing here yet - build one with dev\\make_update.py)")
    print()
    print("  On the other PC: IT Admin -> Updates -> Update source, and enter")
    print(f"      {scheme}://{address}:{args.port}")
    if args.token:
        print(f"      with this password: {args.token}")
    print()
    print("  From another network, that address has to be your own public one")
    print("  (or a dynamic-DNS name), with this port forwarded to this PC.")
    print()
    print("  Leave this window open. Ctrl+C stops it.")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
