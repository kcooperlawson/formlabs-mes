"""The FastAPI backend for the React frontend replacing this project's
Streamlit pages one at a time, starting with the Operator Form (see the
migration plan). Reuses crud.py/models.py/db_core.py exactly as the
Streamlit pages do - import crud/models/db_core directly here, never
database.py, which is a Streamlit-only facade (st.cache_data, a can() that
reads st.session_state) around the same functions.

Route handlers in this package are plain `def`, not `async def`: crud.py's
ScopedSession is thread-local, and Starlette runs sync routes in its own
thread pool, which is the model this DB layer already assumes (the same way
Streamlit runs each script on a worker thread). An async route would run
psycopg2's blocking calls on the single event-loop thread instead.
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import crud
from api import realtime
from api.deps import SESSION_COOKIE
from api.security import CSRFHeaderMiddleware
from api.routers import account as account_router
from api.routers import admin as admin_router
from api.routers import analytics as analytics_router
from api.routers import assigned_runs as assigned_runs_router
from api.routers import audit as audit_router
from api.routers import auth as auth_router
from api.routers import batch_history as batch_history_router
from api.routers import checklist as checklist_router
from api.routers import cleanliness as cleanliness_router
from api.routers import devices as devices_router
from api.routers import downtime as downtime_router
from api.routers import floor_comms as floor_comms_router
from api.routers import google_sync as google_sync_router
from api.routers import historical as historical_router
from api.routers import log_management as log_management_router
from api.routers import lot_verification as lot_verification_router
from api.routers import notes as notes_router
from api.routers import packing as packing_router
from api.routers import pouring as pouring_router
from api.routers import reactors as reactors_router
from api.routers import reference as reference_router
from api.routers import resin_canvas as resin_canvas_router
from api.routers import roster as roster_router
from api.routers import scada as scada_router
from api.routers import scrap as scrap_router
from api.routers import summary as summary_router
from api.routers import tv as tv_router
from api.routers import updates as updates_router
from api.routers import drill as drill_router

app = FastAPI(title="Formlabs MES API")
app.add_middleware(CSRFHeaderMiddleware)


@app.on_event("startup")
def _announce_on_lan():
    # Ported from Home.py's own @st.cache_resource-wrapped startup call -
    # see service_announcer.py. Safe to call unconditionally: it no-ops when
    # the device gateway is off, DB_URL is unset, or zeroconf isn't installed.
    #
    # Has to run off the event loop, in a plain thread of its own - a sync
    # `def` startup handler like this one still runs directly ON uvicorn's
    # event loop (Starlette only hands route handlers to its thread pool,
    # not startup/shutdown events), and zeroconf's client detects "a loop is
    # already running on this thread" and tries to attach to it instead of
    # starting its own. It then hands its registration handshake back to
    # that same loop and waits on the result - which can never arrive while
    # this call is the thing blocking that loop - and gives up with
    # zeroconf._exceptions.EventLoopBlocked. A background thread has no
    # loop of its own to be detected, so zeroconf falls back to running
    # independently instead, which is what actually lets this succeed.
    import threading
    import service_announcer
    threading.Thread(target=service_announcer.start_announcing, daemon=True, name="mdns-announce").start()


@app.on_event("startup")
async def _capture_event_loop():
    # api/realtime.py's notify() gets called from the sync route handlers
    # that make up most of this app (worker threads), but the WebSocket
    # connections it wakes up live on this loop - the one uvicorn actually
    # runs. Async, so `asyncio.get_running_loop()` returns the real thing
    # rather than creating a throwaway one.
    realtime.set_loop(asyncio.get_running_loop())


@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    """Wakes a live dashboard (SCADA, TV) the moment a pour/pack/downtime
    lands, instead of leaving it to that screen's own poll interval. Carries
    no data of its own - a client that gets a message just re-runs the same
    query it already had, so the REST endpoint stays the one place the
    actual shape of the data is decided.
    """
    token = websocket.cookies.get(SESSION_COOKIE)
    user = crud.get_user_by_session_token(token) if token else None
    if not user:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    queue = realtime.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json({"event": event})
    except WebSocketDisconnect:
        pass
    finally:
        realtime.unsubscribe(queue)


for _router in (auth_router, reference_router, checklist_router, pouring_router,
                packing_router, downtime_router, audit_router, notes_router, summary_router,
                scada_router, floor_comms_router, reactors_router, cleanliness_router, roster_router,
                scrap_router, lot_verification_router, batch_history_router, historical_router,
                resin_canvas_router, assigned_runs_router, log_management_router, google_sync_router,
                analytics_router, admin_router, tv_router, devices_router, account_router,
                updates_router, drill_router):
    app.include_router(_router.router, prefix="/api")

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    # Registered last: FastAPI/Starlette matches routes in registration
    # order, so every /api/* router above always wins before either of these
    # ever sees the request. Absent during early development (before
    # `npm run build` exists) so the API still boots and serves /api/* alone.
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="spa-assets")

    # A plain StaticFiles(html=True) mount 404s on a path with no matching
    # file - fine for an app with one screen, wrong the moment a second
    # route exists (TV Dashboard's own /tv, opened as a direct browser
    # navigation on a wall-mounted screen, not a client-side link). This
    # serves a real file when the build produced one (favicon.svg,
    # resin_cartridge.png - anything Vite copied from frontend/public/
    # verbatim) and falls back to index.html otherwise, letting React
    # Router's client-side routing take it from there.
    #
    # Two things this must never do: swallow an /api/* path that didn't
    # match one of the routers above (that has to stay a 404, not the SPA
    # shell - a request with a path-traversal filename that slips past a
    # router's own {filename} pattern must not land here and get a 200),
    # and resolve a candidate file outside frontend/dist at all - `full_path`
    # is attacker-controlled, and Path("dist") / "../../.env" walks straight
    # out of it without an explicit containment check.
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_relative_to(_FRONTEND_DIST) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
