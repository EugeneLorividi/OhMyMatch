"""Pure ASGI middleware that caps request body size before anything parses it."""

from starlette.requests import cookie_parser
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.i18n import LANG_COOKIE, negotiate, translate


class BodySizeLimit:
    def __init__(self, app: ASGIApp, default: int, per_path: dict[str, int]) -> None:
        self.app = app
        self.default = default
        self.per_path = per_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.per_path.get(scope["path"], self.default)
        headers = {
            name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]
        }
        locale = negotiate(
            cookie_parser(headers.get("cookie", "")).get(LANG_COOKIE),
            headers.get("accept-language"),
        )
        too_large = PlainTextResponse(translate(locale, "error.too_large"), status_code=413)
        for name, value in scope["headers"]:
            if name == b"content-length" and (not value.isdigit() or int(value) > limit):
                await too_large(scope, receive, send)
                return

        received = 0
        overflow = False

        async def limited_receive() -> Message:
            # FastAPI turns exceptions raised while reading the body into a 400, so instead
            # of raising, pretend the client went away and replace the response below.
            nonlocal received, overflow
            if overflow:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    overflow = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not overflow:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not overflow:
                raise
        if overflow:
            await too_large(scope, receive, send)
