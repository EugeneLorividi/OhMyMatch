from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.csrf import get_csrf_token
from app.i18n import LOCALES, get_locale, translate, translate_msg

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["password_min"] = PASSWORD_MIN_LENGTH
templates.env.globals["password_max"] = PASSWORD_MAX_LENGTH


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
    no_store: bool = False,
) -> HTMLResponse:
    locale = get_locale(request)
    ctx = {
        "csrf_token": get_csrf_token(request),
        "lang": locale,
        "other_lang": next(code for code in LOCALES if code != locale),
        "t": lambda key, **params: translate(locale, key, **params),
        "tm": lambda message: translate_msg(locale, message),
        **(context or {}),
    }
    response = templates.TemplateResponse(request, name, ctx, status_code=status_code)
    if no_store:
        response.headers["Cache-Control"] = "no-store"
    return response
