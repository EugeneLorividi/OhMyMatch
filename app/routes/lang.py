from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.i18n import LANG_COOKIE, LANG_COOKIE_MAX_AGE, LOCALES, safe_next

router = APIRouter()


@router.get("/lang/{code}")
def switch_language(
    code: str, next_path: Annotated[str, Query(alias="next")] = "/"
) -> RedirectResponse:
    if code not in LOCALES:
        raise HTTPException(status_code=404)
    response = RedirectResponse(safe_next(next_path), status_code=303)
    # Only the language code: no personal data in this cookie.
    response.set_cookie(
        LANG_COOKIE,
        code,
        max_age=LANG_COOKIE_MAX_AGE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response
