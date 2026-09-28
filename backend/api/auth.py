import hmac
import os
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.config import settings

COOKIE_NAME = "af_token"
PUBLIC_PATHS = {"/login", "/api/health", "/favicon.svg"}

router = APIRouter()


def auth_enabled() -> bool:
    return bool(settings.API_TOKEN) and os.environ.get("TESTING") != "true"


def _token_ok(candidate: Optional[str]) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate.encode(), settings.API_TOKEN.encode())


def _request_token(headers, cookies) -> Optional[str]:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return headers.get("x-api-key") or cookies.get(COOKIE_NAME)


def websocket_authorized(websocket: WebSocket) -> bool:
    if not auth_enabled():
        return True
    return _token_ok(_request_token(websocket.headers, websocket.cookies) or websocket.query_params.get("token"))


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if not auth_enabled() or path in PUBLIC_PATHS:
        return await call_next(request)
    if _token_ok(_request_token(request.headers, request.cookies)):
        return await call_next(request)
    if path.startswith("/api/") or path.startswith("/docs") or path == "/openapi.json":
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


LOGIN_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlphaForge Login</title>
<style>
body{background:#0b1120;color:#e2e8f0;font-family:system-ui,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
form{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:28px;width:min(360px,90vw)}
input{width:100%;box-sizing:border-box;padding:10px;margin:12px 0;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0}
button{width:100%;padding:10px;border:0;border-radius:8px;background:#4f46e5;color:white;font-weight:700;cursor:pointer}
.err{color:#f87171;font-size:13px}
</style></head><body>
<form method="post" action="/login">
<h2 style="margin:0">AlphaForge</h2>
<p style="color:#94a3b8;font-size:13px">Enter the API_TOKEN from the server's .env file.</p>
<!--ERROR-->
<input type="password" name="token" placeholder="API token" autofocus required>
<button type="submit">Sign in</button>
</form></body></html>"""

WRONG_TOKEN_PAGE = LOGIN_PAGE.replace("<!--ERROR-->", '<p class="err">Wrong token.</p>')


def _login_response() -> RedirectResponse:
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE_NAME, settings.API_TOKEN, httponly=True, samesite="lax", max_age=365 * 24 * 3600)
    return resp


@router.get("/login")
async def login_page(token: Optional[str] = None):
    if not auth_enabled():
        return RedirectResponse("/", status_code=303)
    if token is not None:
        return _login_response() if _token_ok(token) else HTMLResponse(WRONG_TOKEN_PAGE, status_code=401)
    return HTMLResponse(LOGIN_PAGE)


@router.post("/login")
async def login_submit(request: Request):
    form = parse_qs((await request.body()).decode("utf-8", errors="ignore"))
    token = (form.get("token") or [""])[0]
    return _login_response() if _token_ok(token) else HTMLResponse(WRONG_TOKEN_PAGE, status_code=401)


@router.get("/api/health")
async def health():
    return {"ok": True}
