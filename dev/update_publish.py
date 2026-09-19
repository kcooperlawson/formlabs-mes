"""Publishes a signed update package to GitHub Releases, so a plant PC can
find it without this machine and that one ever being on the same network.

Used by dev/make_update.py's --publish flag (CLI, run at home) and by
api/routers/updates.py's own /updates/publish endpoint (the in-app "Push
latest update" button, gated by require_admin_console - meaningfully usable
only on the machine that actually holds dev/update_signing_private.pem and
a GITHUB_RELEASE_TOKEN, but not restricted by machine identity, since
checking "am I the home PC" from inside a request is not a real boundary
and pretending it is would be worse than just relying on the ability gate
and the fact that only one machine has the private key to sign with in the
first place).

One release per version, tagged with the exact string in VERSION (e.g.
PT-V4.07) so a plant PC's own version_tuple() comparison (see
setup/apply_update.py) works the same way it always has - GitHub is just
where the zip lives now, not a new source of truth about versions.

Publishing always needs authentication, even though the repo itself is
public: creating a release and uploading an asset are write operations.
GITHUB_RELEASE_TOKEN lives in .env exactly like GATEWAY_ENCRYPTION_KEY and
PG_PASS - never committed, read with os.getenv, and never printed back.
A fine-grained personal access token scoped to just this one repo's
"Contents: Read and write" permission is all this needs; a classic token
with the narrower "repo" scope also works.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "kcooperlawson/pouring_mes_logger"


class PublishError(RuntimeError):
    """Raised with a message that's safe and useful to show as-is - never
    wraps a raw requests exception, so a caller (CLI or the API route) can
    just print/return str(exc) without leaking a token or a stack trace."""


def _token() -> str:
    token = os.getenv("GITHUB_RELEASE_TOKEN", "").strip()
    if not token:
        raise PublishError(
            "no GITHUB_RELEASE_TOKEN in .env. Create a fine-grained GitHub "
            "token scoped to just this repo (Settings -> Developer settings "
            "-> Personal access tokens on github.com), with Contents: Read "
            "and write, and add it to .env as GITHUB_RELEASE_TOKEN=<token>."
        )
    return token


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _find_release_by_tag(repo: str, tag: str, token: str):
    import requests
    resp = requests.get(f"{GITHUB_API}/repos/{repo}/releases/tags/{tag}",
                        headers=_headers(token), timeout=30)
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 404:
        return None
    raise PublishError(f"could not check for an existing {tag} release "
                       f"({resp.status_code}: {resp.text[:300]})")


def publish_release(zip_path: Path, manifest: dict, repo: str = DEFAULT_REPO,
                    token: str | None = None) -> dict:
    """Creates (or replaces the asset on) a GitHub Release tagged with
    manifest['to_version'] and uploads zip_path as its one asset.

    Re-publishing the same version is not an error - it happens whenever a
    mistake is caught right after pushing "Publish", so this looks for an
    existing release with that tag first and replaces its asset rather than
    failing on "already exists". A plant PC checking for updates always
    reads the CURRENT asset on that tag, so this is safe to do right up
    until some PC has already started downloading it.

    Returns {"html_url", "tag_name", "asset_name", "asset_size"}.
    """
    import requests

    to_version = manifest.get("to_version") or ""
    if not to_version:
        raise PublishError("this manifest has no to_version - nothing to tag")

    tok = token or _token()
    headers = _headers(tok)

    existing = _find_release_by_tag(repo, to_version, tok)
    if existing is None:
        body = manifest.get("notes") or f"Formlabs MES {to_version}"
        resp = requests.post(
            f"{GITHUB_API}/repos/{repo}/releases",
            headers=headers,
            json={
                "tag_name": to_version,
                "name": to_version,
                "body": body,
                "draft": False,
                "prerelease": False,
            },
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise PublishError(f"could not create the {to_version} release "
                               f"({resp.status_code}: {resp.text[:300]})")
        release = resp.json()
    else:
        release = existing
        # Replace any asset that shares the new file's name - GitHub refuses
        # to upload a second asset with a name already taken on the release,
        # and "the last publish wins" is the behavior a re-run should have.
        for asset in release.get("assets", []):
            if asset["name"] == zip_path.name:
                del_resp = requests.delete(
                    f"{GITHUB_API}/repos/{repo}/releases/assets/{asset['id']}",
                    headers=headers, timeout=30,
                )
                if del_resp.status_code not in (200, 204):
                    raise PublishError(
                        f"could not remove the old {zip_path.name} asset "
                        f"before replacing it ({del_resp.status_code})"
                    )

    # upload_url arrives as a URI template like ".../assets{?name,label}" -
    # only the {?name,label} part is templated; everything before the brace
    # is the real endpoint.
    upload_url = release["upload_url"].split("{")[0]
    data = zip_path.read_bytes()
    upload_headers = dict(headers)
    upload_headers["Content-Type"] = "application/zip"
    resp = requests.post(
        f"{upload_url}?name={zip_path.name}",
        headers=upload_headers,
        data=data,
        timeout=180,
    )
    if resp.status_code not in (200, 201):
        raise PublishError(f"the release was created but the file upload "
                           f"failed ({resp.status_code}: {resp.text[:300]}). "
                           f"The {to_version} release on GitHub may need its "
                           f"asset added by hand, or try publishing again.")
    asset = resp.json()

    return {
        "html_url": release.get("html_url", ""),
        "tag_name": to_version,
        "asset_name": asset.get("name", zip_path.name),
        "asset_size": asset.get("size", len(data)),
    }
