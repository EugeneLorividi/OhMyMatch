"""Pure ASGI middleware: request ids, error containment, security headers, no-store default."""

import secrets

from starlette.requests import cookie_parser
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.eventlog import log_event
from app.i18n import LANG_COOKIE, negotiate, translate

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
    "form-action 'self'; object-src 'none'"
)
SECURITY_HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}


def locale_from_scope(scope: Scope) -> str:
    headers = {name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]}
    cookie = cookie_parser(headers.get("cookie", "")).get(LANG_COOKIE)
    return negotiate(cookie, headers.get("accept-language"))


class SecurityHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_static = scope["path"].startswith("/static/")

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                for name, value in SECURITY_HEADERS.items():
                    if name.encode() not in present:
                        headers.append((name.encode(), value.encode()))
                # Pages carry personal data: keep them out of every cache by default.
                if not is_static and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, add_headers)


class RequestContext:
    """Gives each request a random id and turns unhandled errors into a bare 500, so
    exception messages (which may contain data) never reach the server log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = secrets.token_hex(16)
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def with_id(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, with_id)
        except Exception:
            log_event("unhandled_error", request_id)
            if not started:
                text = translate(locale_from_scope(scope), "error.server")
                await PlainTextResponse(text, status_code=500)(scope, receive, with_id)
