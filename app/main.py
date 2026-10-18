from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import LoginRequired
from app.config import MAX_BODY_BYTES, MAX_UPLOAD_BODY_BYTES, settings
from app.csrf import CsrfFailed, set_csrf_cookie, verify_csrf
from app.eventlog import event
from app.i18n import get_locale, translate
from app.limits import BodySizeLimit
from app.middleware import RequestContext, SecurityHeaders
from app.routes import account, auth, feed, lang, pages, privacy, profile, reactions, result

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    # Applied to every route; it is a no-op for safe methods.
    dependencies=[Depends(verify_csrf)],
)
app.state.settings = settings
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
ROUTERS = (
    pages.router,
    lang.router,
    auth.router,
    profile.router,
    result.router,
    feed.router,
    reactions.router,
    account.router,
    privacy.router,
)
for router in ROUTERS:
    app.include_router(router)


@app.middleware("http")
async def csrf_cookie(request: Request, call_next):
    response = await call_next(request)
    set_csrf_cookie(request, response)
    return response


# Starlette puts the last added middleware outermost. Order, outside in:
# RequestContext (request id, error containment), SecurityHeaders, BodySizeLimit.
app.add_middleware(
    BodySizeLimit,
    default=MAX_BODY_BYTES,
    per_path={"/result/parse-image": MAX_UPLOAD_BODY_BYTES},
)
app.add_middleware(SecurityHeaders)
app.add_middleware(RequestContext)


@app.exception_handler(CsrfFailed)
async def csrf_failed(request: Request, exc: CsrfFailed) -> PlainTextResponse:
    event(request, "csrf_failed")
    return PlainTextResponse(translate(get_locale(request), "error.csrf"), status_code=403)


@app.exception_handler(LoginRequired)
async def login_required(request: Request, exc: LoginRequired) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)
