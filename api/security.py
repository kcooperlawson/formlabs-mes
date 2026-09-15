"""CSRF defense for the API.

No CSRF protection exists in the Streamlit app today - it never needed any,
since a server-rendered st.form only ever posts back to the page that drew
it. A decoupled React frontend calling this API from the browser does need
one. The frontend and API are same-origin in production (one FastAPI
process serves both, see api/main.py), so the session cookie's
SameSite=Lax is already the primary defense: a cross-site <form> POST or a
no-cors cross-site fetch can't attach it. This middleware is the cheap
second layer - any state-changing request must also carry a custom header,
which only same-origin JS can set (a plain HTML form cannot add arbitrary
headers). No token to generate, store, rotate or leak.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

CSRF_HEADER = "x-mes-client"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            if request.headers.get(CSRF_HEADER) != "1":
                return JSONResponse({"detail": "Missing CSRF header"}, status_code=403)
        return await call_next(request)
