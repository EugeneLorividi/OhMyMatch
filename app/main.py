from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import LoginRequired
from app.config import settings
from app.csrf import set_csrf_cookie, verify_csrf
from app.routes import auth, pages, profile, result

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    # Applied to every route; it is a no-op for safe methods.
    dependencies=[Depends(verify_csrf)],
)
app.state.settings = settings
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
ROUTERS = (pages.router, auth.router, profile.router, result.router)
for router in ROUTERS:
    app.include_router(router)


@app.middleware("http")
async def csrf_cookie(request: Request, call_next):
    response = await call_next(request)
    set_csrf_cookie(request, response)
    return response


@app.exception_handler(LoginRequired)
async def login_required(request: Request, exc: LoginRequired) -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)
