from pydantic import BaseModel


class UpdateStatusOut(BaseModel):
    current_version: str
    latest_version: str | None
    update_available: bool
    notes: str | None = None
    published_at: str | None = None
    error: str | None = None
    # Whether THIS machine can build and sign a release (MES_ALLOW_PUBLISH=1
    # in its .env) - a plant PC has neither the key nor the dev tools, so the
    # page hides that half rather than offering a button that can only fail.
    publish_enabled: bool = False


class ApplyUpdateOut(BaseModel):
    ok: bool
    version: str
    log: str
    restarting: bool
    # "supervised" (the launcher will start it again), "relaunch" (nothing is
    # watching, so a helper will), or "manual" (somebody has to).
    restart_mode: str = "manual"


class PublishUpdateRequest(BaseModel):
    from_version: str = ""
    notes: str = ""


class PublishUpdateOut(BaseModel):
    html_url: str
    tag_name: str
    asset_name: str
    asset_size: int


class UpdateSourceOut(BaseModel):
    kind: str          # "server" (one you host) or "github"
    address: str       # the update server's address, when that's the source
    repo: str          # the GitHub repo, when that is
    token_set: bool


class UpdateSourceRequest(BaseModel):
    address: str = ""          # blank goes back to GitHub
    token: str | None = None   # None leaves whatever is already set alone


class AvailableUpdate(BaseModel):
    version: str
    notes: str = ""
    published_at: str = ""
    size: int | None = None
    current: bool = False
    newer: bool = False


class ApplyVersionRequest(BaseModel):
    version: str = ""          # blank means "the newest one"
    allow_older: bool = False  # installing an older release, deliberately
