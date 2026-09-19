"""Checks for a newer signed update package than this PC is running, and
applies one - the network-reachable half of the same trusted pipeline
setup/apply_update.py already runs off a USB stick.

Two places it can look, in this order:

  * MES_UPDATE_URL in .env - any address serving a small latest.json, which
    is what setup/update_server.py does from a PC you run yourself. Nothing
    about it is GitHub-shaped: a folder on a web server, a NAS, or a home PC
    with one port open all work the same way.
  * GitHub Releases otherwise (see dev/update_publish.py for what puts one
    there). A private repo needs a read-only token on this PC.

Where it came from doesn't decide whether it's trusted: the package is signed
and every file checksummed, and setup/apply_update.py refuses one that isn't
signed by the real key whichever route it arrived by. That is why serving
updates over plain HTTP from a home PC is not the hole it sounds like - the
worst a tampered copy achieves is a refused update.

Deliberately thin: every safety property (checksum, signature, backup,
rollback-on-failure) already lives in setup/apply_update.py and
setup/update_signing.py, and this module reuses that code rather than
duplicating any of it. Its only two jobs are "is there something newer" and
"fetch it to updates\\ so apply_update.py can take it from there exactly
like it always has" - a plant PC on the auto-update path and one worked
from a USB stick end up running the identical apply().
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPDATES = ROOT / "updates"

sys.path.insert(0, str(ROOT / "setup"))

GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "kcooperlawson/pouring_mes_logger"

# GitHub allows 60 unauthenticated API calls an hour per IP. The banner asks
# every open manager tab every few minutes and the Updates tab asks on every
# visit, all from this one server, so without a shared answer a few tabs left
# open all day would spend the whole allowance and start reporting failures
# instead of updates. A release nobody has published yet is not urgent news.
CACHE_TTL_S = 900.0
_cache_lock = threading.Lock()
_cached: dict = {"at": 0.0, "value": None}


def publish_enabled() -> bool:
    """Building and signing a release from inside the app is a developer
    action, not a plant one: it needs the private signing key, and anyone
    who can reach the admin console on the PC holding that key could
    otherwise publish a release every plant PC would trust. Off unless the
    machine says otherwise in its own .env."""
    return os.getenv("MES_ALLOW_PUBLISH", "").strip() == "1"


class CheckError(RuntimeError):
    """A message that's safe to show as-is in the UI - never a raw
    requests/network exception, and never includes a token."""


ENV_FILE = ROOT / ".env"
# Anything outside this can't be part of an address, and letting it through
# would mean a typed-in "address" could write extra lines into .env.
_ADDRESS_OK = re.compile(r"^[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$")


def _update_url() -> str:
    """The base address of a self-hosted update server, if this PC has been
    pointed at one - always a base, never a specific file, whether .env holds
    "192.168.0.15", "http://host:8443" or an older ".../latest.json"."""
    raw = os.getenv("MES_UPDATE_URL", "").strip()
    if not raw:
        return ""
    try:
        return normalise_address(raw)
    except CheckError:
        return raw.rstrip("/")


def normalise_address(address: str) -> str:
    """What someone types in the Updates tab -> a base URL.

    "192.168.0.15"                     -> http://192.168.0.15:8443
    "192.168.0.15:9000"                -> http://192.168.0.15:9000
    "https://updates.example.com/x/"   -> https://updates.example.com/x
    "http://host:8443/latest.json"     -> http://host:8443
    """
    address = (address or "").strip().rstrip("/")
    if not address:
        return ""
    if not _ADDRESS_OK.match(address):
        raise CheckError("that doesn't look like an address - letters, numbers, dots, "
                         "colons and slashes only")
    if "://" not in address:
        address = f"http://{address}"
    for tail in ("/latest.json", "/updates.json"):
        if address.endswith(tail):
            address = address[: -len(tail)]
    # A bare host with no port: the update server's own default.
    from urllib.parse import urlsplit
    parts = urlsplit(address)
    if not parts.port and parts.scheme == "http" and "/" not in parts.path.strip("/"):
        address = f"{address}:8443" if parts.path in ("", "/") else address
    return address.rstrip("/")


def _write_env_values(values: dict) -> None:
    """Writes .env in place, one key per line, leaving every other line as it
    is. .env is never touched by an update, so this survives them."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    for key, value in values.items():
        replaced = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i], replaced = f"{key}={value}", True
                break
        if not replaced:
            lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def source_info() -> dict:
    url = _update_url()
    return {
        "kind": "server" if url else "github",
        "address": url,
        "repo": _repo() if not url else "",
        "token_set": bool(os.getenv("MES_UPDATE_TOKEN", "").strip() if url
                          else os.getenv("GITHUB_RELEASE_TOKEN", "").strip()),
    }


def set_source(address: str, token: str | None = None) -> dict:
    """Points this PC at an update server (or back at GitHub, with a blank
    address). Written to .env AND to this process, so it takes effect without
    a restart."""
    url = normalise_address(address)
    values = {"MES_UPDATE_URL": url}
    if token is not None:
        values["MES_UPDATE_TOKEN"] = token.strip()
    _write_env_values(values)
    os.environ["MES_UPDATE_URL"] = url
    if token is not None:
        os.environ["MES_UPDATE_TOKEN"] = token.strip()
    with _cache_lock:
        _cached.update(at=0.0, value=None)
    return source_info()


def list_available() -> list:
    """Every version this PC could install, newest first, each marked with
    whether it is what's already running and whether it can be installed
    (the applier refuses to go backwards unless told to)."""
    here = current_version()
    releases = _all_releases()
    out = []
    for release in releases:
        version = release["tag_name"]
        out.append({
            "version": version,
            "notes": release.get("notes", "") or "",
            "published_at": release.get("published_at", "") or "",
            "size": release.get("size"),
            "current": version == here,
            "newer": version_tuple(version) > version_tuple(here),
        })
    return out


def _all_releases() -> list:
    """Every package the configured source offers, newest first."""
    import requests

    url = _update_url()
    if url:
        try:
            resp = requests.get(f"{url}/updates.json", headers=_self_hosted_headers(),
                                timeout=15, verify=_verify_tls())
        except requests.RequestException as exc:
            raise CheckError(f"could not reach the update server at {url} "
                             f"({exc.__class__.__name__}). Is it running?") from exc
        if resp.status_code == 401:
            raise CheckError("the update server refused this PC's password")
        if resp.status_code == 404:
            # An older update server only knows latest.json.
            one = _latest_from_url(f"{url}/latest.json")
            return [one] if one else []
        if resp.status_code != 200:
            raise CheckError(f"the update server answered {resp.status_code}")
        from urllib.parse import urljoin
        releases = []
        for entry in resp.json().get("packages", []):
            releases.append({
                "tag_name": entry.get("version", ""),
                "html_url": urljoin(f"{url}/", entry.get("file", "")),
                "notes": entry.get("notes", "") or "",
                "published_at": entry.get("published_at", ""),
                "asset_name": entry.get("file", ""),
                "asset_url": urljoin(f"{url}/", entry.get("file", "")),
                "sha256": entry.get("sha256", ""),
                "size": entry.get("size"),
                "self_hosted": True,
            })
        return [r for r in releases if r["tag_name"] and r["asset_name"]]

    repo = _repo()
    try:
        resp = requests.get(f"{GITHUB_API}/repos/{repo}/releases?per_page=30",
                            headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise CheckError(f"could not reach GitHub ({exc})") from exc
    if resp.status_code in (401, 403):
        raise CheckError(f"GitHub refused this PC's token for {repo}")
    if resp.status_code != 200:
        raise CheckError(f"GitHub returned {resp.status_code} listing releases")
    releases = []
    for data in resp.json():
        asset = next((a for a in data.get("assets", []) if a["name"].lower().endswith(".zip")), None)
        if asset is None:
            continue
        releases.append({
            "tag_name": data.get("tag_name", ""),
            "html_url": data.get("html_url", ""),
            "notes": data.get("body", "") or "",
            "published_at": data.get("published_at", ""),
            "asset_name": asset["name"],
            "asset_url": asset["url"],
            "size": asset.get("size"),
        })
    return releases


def _self_hosted_headers() -> dict:
    headers = {"Accept": "application/json"}
    token = os.getenv("MES_UPDATE_TOKEN", "").strip()
    if token:
        headers["X-MES-Update-Token"] = token
    return headers


def _verify_tls() -> bool:
    """A self-signed certificate on a home PC can't be verified by a plant PC
    that has never seen it. MES_UPDATE_INSECURE=1 accepts it anyway, which is
    safe here for the one reason that matters: the package's signature, not
    the connection, is what says the package is genuine."""
    return os.getenv("MES_UPDATE_INSECURE", "").strip() != "1"


def _latest_from_url(url: str) -> dict | None:
    """The same shape latest_release() returns, from a plain latest.json:
    {"version", "file", "size", "sha256", "notes", "published_at"}."""
    import requests
    from urllib.parse import urljoin

    if not _verify_tls():
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = requests.get(url, headers=_self_hosted_headers(), timeout=15, verify=_verify_tls())
    except requests.RequestException as exc:
        raise CheckError(f"could not reach the update server at {url} ({exc.__class__.__name__}). "
                         f"Is it running, and reachable from this PC?") from exc
    if resp.status_code == 401:
        raise CheckError("the update server refused this PC's token (MES_UPDATE_TOKEN in .env)")
    if resp.status_code != 200:
        raise CheckError(f"the update server answered {resp.status_code} for {url}")
    try:
        data = resp.json()
        version, name = data["version"], data["file"]
    except Exception as exc:
        raise CheckError(f"{url} didn't answer with an update listing ({exc})") from exc
    if not version:
        return None
    return {
        "tag_name": version,
        "html_url": urljoin(url, name),
        "notes": data.get("notes", "") or "",
        "published_at": data.get("published_at", ""),
        "asset_name": name,
        "asset_url": urljoin(url, name),
        "sha256": data.get("sha256", ""),
        "self_hosted": True,
    }


def _repo() -> str:
    # Same override knob dev/update_publish.py's --repo offers, kept as an
    # env var here since the checker has no command line - lets a fork or a
    # private mirror point somewhere other than DEFAULT_REPO without a code
    # change.
    return os.getenv("GITHUB_UPDATE_REPO", "").strip() or DEFAULT_REPO


def _headers(accept: str = "application/vnd.github+json") -> dict:
    """GitHub asks for a token on a PRIVATE repo even just to look. Without
    one, every call to a private repo answers 404 - indistinguishable from
    "no release has been published yet", which is how a private repo used to
    look like nothing was ever released."""
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_RELEASE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def current_version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def version_tuple(text) -> tuple[int, ...]:
    """PT-V3.40 -> (3, 40). Anything unparseable sorts before everything.
    Copied from setup/apply_update.py's own version_tuple() rather than
    imported, so this module still works standalone if that one ever
    changes shape - the two only need to agree on ORDER, not on identity."""
    nums = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in nums) if nums else (0,)


def latest_release(repo: str | None = None) -> dict | None:
    """The newest published release on GitHub carrying a .zip asset, or
    None if there isn't one yet - a brand new repo, or nothing has ever
    been --publish'd, is a normal state, not an error. Raises CheckError
    only when the check itself could not be done (no internet, GitHub is
    down, the repo name is wrong)."""
    import requests

    url = _update_url()
    if url:
        return _latest_from_url(f"{url}/latest.json")

    repo = repo or _repo()
    try:
        resp = requests.get(f"{GITHUB_API}/repos/{repo}/releases/latest",
                            headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise CheckError(f"could not reach GitHub ({exc})") from exc
    if resp.status_code in (401, 403):
        raise CheckError(f"GitHub refused this PC's token for {repo}")
    if resp.status_code == 404:
        # Said plainly rather than silently: a private repo answers 404 to a
        # PC with no token, and "nothing published yet" would be a lie.
        if os.getenv("GITHUB_RELEASE_TOKEN", "").strip():
            raise CheckError(f"no release found in {repo} - the repo may have been "
                             f"renamed, or this PC's token can't see it")
        raise CheckError(f"no release found in {repo}. If that repo is private, this PC "
                         f"needs a read-only GITHUB_RELEASE_TOKEN in its .env to see it.")
    if resp.status_code != 200:
        raise CheckError(f"GitHub returned {resp.status_code} checking for updates")
    data = resp.json()
    asset = next((a for a in data.get("assets", []) if a["name"].lower().endswith(".zip")), None)
    if asset is None:
        return None
    return {
        "tag_name": data.get("tag_name", ""),
        "html_url": data.get("html_url", ""),
        "notes": data.get("body", "") or "",
        "published_at": data.get("published_at", ""),
        "asset_name": asset["name"],
        # The API asset URL (needed with an Accept: application/octet-stream
        # header to actually download the bytes) - not browser_download_url,
        # which redirects to a CDN this app has no reason to hit directly.
        "asset_url": asset["url"],
    }


def status(repo: str | None = None, force: bool = False) -> dict:
    """What the update banner shows, cached for CACHE_TTL_S and shared by
    every caller. force=True is the Updates tab's own "check now" button.

    update_available compares by parsed version number, the same ordering
    setup/apply_update.py already uses for its own from/to check - not "is
    the tag different than mine", so a plant PC that's ahead of the latest
    published release (mid-development, or hand-patched) is never told it
    needs to downgrade."""
    with _cache_lock:
        fresh = _cached["value"] is not None and (time.monotonic() - _cached["at"]) < CACHE_TTL_S
        if fresh and not force:
            # current_version() is read from disk every time: an update
            # applied a minute ago has to show as applied, not as whatever
            # the cached answer was built against.
            return {**_cached["value"], "current_version": current_version(),
                    "update_available": _cached["value"]["latest_version"] is not None
                    and version_tuple(_cached["value"]["latest_version"]) > version_tuple(current_version())}

    value = _status_uncached(repo)
    with _cache_lock:
        # An error is not worth caching for fifteen minutes - the internet
        # coming back should show up on the next look, not a quarter of an
        # hour later.
        if value.get("error") is None:
            _cached.update(at=time.monotonic(), value=value)
    return value


def _status_uncached(repo: str | None = None) -> dict:
    here = current_version()
    try:
        release = latest_release(repo)
    except CheckError as exc:
        return {"current_version": here, "latest_version": None,
                "update_available": False, "notes": None,
                "published_at": None, "error": str(exc)}
    if release is None:
        return {"current_version": here, "latest_version": None,
                "update_available": False, "notes": None,
                "published_at": None, "error": None}
    available = version_tuple(release["tag_name"]) > version_tuple(here)
    return {
        "current_version": here,
        "latest_version": release["tag_name"],
        "update_available": available,
        "notes": release["notes"],
        "published_at": release["published_at"],
        "error": None,
    }


def download_release(release: dict) -> Path:
    """Fetches the release's zip asset into updates\\, exactly where a
    hand-carried USB stick would have dropped it - apply_update.py's own
    newest_package() then picks it up with no idea whether it arrived over
    the network or on foot."""
    import requests

    if release.get("self_hosted"):
        headers, verify = _self_hosted_headers(), _verify_tls()
    else:
        # Required on a private repo, harmless on a public one.
        headers, verify = _headers("application/octet-stream"), True
    try:
        resp = requests.get(release["asset_url"], headers=headers, timeout=120,
                            stream=True, verify=verify)
    except requests.RequestException as exc:
        raise CheckError(f"could not download the update ({exc})") from exc
    if resp.status_code != 200:
        raise CheckError(f"GitHub returned {resp.status_code} downloading the update")
    UPDATES.mkdir(exist_ok=True)
    target = UPDATES / release["asset_name"]
    digest = hashlib.sha256()
    with open(target, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            if chunk:
                fh.write(chunk)
                digest.update(chunk)

    # A self-hosted listing says what the file should be; a download that
    # doesn't match it was cut short or swapped, and saying so here beats
    # letting apply_update.py find it one step later.
    expected = (release.get("sha256") or "").strip().lower()
    if expected and digest.hexdigest() != expected:
        target.unlink(missing_ok=True)
        raise CheckError("the downloaded update doesn't match what the update server said "
                         "it would be - it was interrupted, or something changed it on the way")
    return target


def apply_version(version: str, allow_older: bool = False) -> dict:
    """Installs one named version - what the Updates tab's per-row button
    asks for. Same pipeline as apply_latest; the only difference is which
    package it fetches."""
    release = next((r for r in _all_releases() if r["tag_name"] == version), None)
    if release is None:
        raise CheckError(f"{version} isn't on the update source any more")

    here = current_version()
    if version_tuple(version) <= version_tuple(here) and not allow_older:
        raise CheckError(f"this PC is already on {here}, which is not older than {version}")

    package_path = download_release(release)

    import apply_update  # setup/apply_update.py

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = apply_update.apply(str(package_path), root=str(ROOT), assume_yes=True,
                                  allow_older=allow_older)
    return {"ok": code == 0, "version": apply_update.read_version(str(ROOT)), "log": buf.getvalue()}


def apply_latest(repo: str | None = None) -> dict:
    """Downloads the latest release and runs it through
    setup/apply_update.py's real apply() - the same backup / copy-aside /
    write / verify-boots / rollback-on-failure pipeline a USB stick already
    goes through, completely unchanged. Returns
    {"ok", "version", "log"} - log is everything apply() printed, useful to
    show the caller when ok is False.

    assume_yes=True here is not skipping a safety check - it is skipping
    the CLI's console input() prompt, which has no terminal to type into
    from a web request. The confirmation this replaces already happened one
    layer up, in the browser, before this endpoint was ever called (see
    api/routers/updates.py's apply route) - apply() itself still runs every
    one of its own checks (package integrity, signature, version match,
    backup, verify-boots) and still restores the previous version
    automatically if any of them fail.
    """
    release = latest_release(repo)
    if release is None:
        raise CheckError("no update is available to apply")
    here = current_version()
    if version_tuple(release["tag_name"]) <= version_tuple(here):
        raise CheckError(f"this PC is already on {here}, which is not older "
                         f"than {release['tag_name']}")

    package_path = download_release(release)

    import apply_update  # setup/apply_update.py

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = apply_update.apply(str(package_path), root=str(ROOT), assume_yes=True)

    return {
        "ok": code == 0,
        "version": apply_update.read_version(str(ROOT)),
        "log": buf.getvalue(),
    }
