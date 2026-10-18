import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.auth import RequiredUser
from app.db.session import get_db
from app.i18n import msg
from app.models.reaction import KINDS
from app.reactions import Outcome, Unavailable, matches_of, react, remove_match
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]

OUTCOME_KEYS = {
    Outcome.LIKED: "react.liked",
    Outcome.MATCHED: "react.matched",
    Outcome.PASSED: "react.passed",
    Outcome.BLOCKED: "react.blocked",
    Outcome.UNCHANGED: "react.unchanged",
}


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _message_page(request: Request, user, key: str, status_code: int) -> Response:
    context = {"user": user, "message": msg(key)}
    return render(request, "message.html", context, status_code, no_store=True)


@router.post("/react")
def post_reaction(
    request: Request,
    user: RequiredUser,
    db: Db,
    target: Annotated[str, Form()] = "",
    kind: Annotated[str, Form()] = "",
) -> Response:
    try:
        target_id = uuid.UUID(target)
    except ValueError:
        target_id = None
    if kind not in KINDS:
        return _message_page(request, user, "error.bad_reaction", 400)
    try:
        if target_id is None:
            raise Unavailable
        outcome = react(db, user, target_id, kind)
    except Unavailable:
        if _is_htmx(request):
            return render(
                request, "_reaction_done.html", {"message": msg("error.candidate_unavailable")}
            )
        return _message_page(request, user, "error.candidate_unavailable", 404)
    if _is_htmx(request):
        context = {"message": msg(OUTCOME_KEYS[outcome]), "matched": outcome is Outcome.MATCHED}
        return render(request, "_reaction_done.html", context, no_store=True)
    return RedirectResponse("/matches" if outcome is Outcome.MATCHED else "/feed", status_code=303)


@router.get("/matches")
def matches_page(request: Request, user: RequiredUser, db: Db) -> Response:
    context = {"user": user, "matches": matches_of(db, user)}
    return render(request, "matches.html", context, no_store=True)


@router.post("/matches/{match_id}/remove")
def remove(request: Request, user: RequiredUser, db: Db, match_id: uuid.UUID) -> Response:
    if not remove_match(db, user, match_id):
        return _message_page(request, user, "error.match_not_found", 404)
    return RedirectResponse("/matches", status_code=303)
