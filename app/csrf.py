"""Double-submit CSRF protection for every unsafe request, forms and HTMX alike."""

import secrets

from fastapi import Request, Response

CSRF_COOKIE = "__Host-csrf"
CSRF_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CsrfFailed(Exception):
    pass


def get_csrf_token(request: Request) -> str:
    """Token for forms on this page; a new one is issued if the browser has none."""
    token = getattr(request.state, "csrf_token", None) or request.cookies.get(CSRF_COOKIE)
    if not token:
        token = secrets.token_urlsafe(32)
    request.state.csrf_token = token
    return token


def rotate_csrf_token(request: Request) -> None:
    request.state.csrf_token = secrets.token_urlsafe(32)


def set_csrf_cookie(request: Request, response: Response) -> None:
    token = getattr(request.state, "csrf_token", None)
    if token and token != request.cookies.get(CSRF_COOKIE):
        response.set_cookie(
            CSRF_COOKIE, token, path="/", secure=True, httponly=True, samesite="lax"
        )


async def verify_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    expected = request.cookies.get(CSRF_COOKIE)
    submitted = request.headers.get(CSRF_HEADER)
    if submitted is None:
        form = await request.form()
        value = form.get(CSRF_FIELD)
        submitted = value if isinstance(value, str) else None
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        raise CsrfFailed
