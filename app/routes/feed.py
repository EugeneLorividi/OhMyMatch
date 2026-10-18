from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import RequiredUser
from app.config import FEED_PAGES_PER_USER
from app.db.session import get_db
from app.matching.feed import build_feed
from app.ratelimit import limiter
from app.routes._limits import too_many
from app.templating import render

router = APIRouter()


@router.get("/feed")
def feed(
    request: Request,
    user: RequiredUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
) -> Response:
    htmx = request.headers.get("HX-Request") == "true"
    if user.is_active:
        wait = limiter.hit(FEED_PAGES_PER_USER, str(user.id))
        if wait:
            return too_many(request, FEED_PAGES_PER_USER, wait, "rate.feed", user, htmx)
    feed_page = build_feed(db, user, page)
    context = {"user": user, "feed": feed_page}
    if htmx and feed_page is not None:
        return render(request, "_feed_page.html", context, no_store=True)
    return render(request, "feed.html", context, no_store=True)
