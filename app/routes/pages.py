from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db.session import get_db
from app.models import Dislike, TestScore
from app.templating import render

router = APIRouter()


@router.get("/")
def index(request: Request, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    context: dict = {"user": user}
    if user is not None:
        context["has_profile"] = bool(user.gender and user.seeking)
        context["has_scores"] = db.get(TestScore, user.id) is not None
        context["dislike_count"] = db.scalar(
            select(func.count()).select_from(Dislike).where(Dislike.user_id == user.id)
        )
    return render(request, "index.html", context)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return "User-agent: *\nDisallow: /\n"
