from fastapi import Request
from fastapi.responses import Response

from app.config import Rule
from app.eventlog import event
from app.i18n import msg
from app.templating import render


def too_many(
    request: Request,
    rule: Rule,
    retry_after: int,
    key: str,
    user=None,
    htmx: bool = False,
    back: str = "/",
) -> Response:
    event(request, f"rate_limited.{rule.name}")
    message = msg(key, limit=rule.limit)
    if htmx:
        # HTMX only swaps 2xx responses; the status still says what happened in Retry-After.
        response = render(request, "_reaction_done.html", {"message": message})
    else:
        context = {"user": user, "message": message, "back": back}
        response = render(request, "message.html", context, 429)
    response.headers["Retry-After"] = str(retry_after)
    return response
