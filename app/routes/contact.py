import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app import contact
from app.auth import RequiredUser
from app.config import CONTACT_SAVES_PER_USER, CONTACT_SHARES_PER_USER
from app.contact.username import normalize
from app.db.session import get_db
from app.eventlog import event
from app.i18n import msg
from app.models import Match
from app.ratelimit import limiter
from app.routes._limits import too_many
from app.routes.account import account_view
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]
FormStr = Annotated[str, Form()]


def _message_page(request: Request, user, key: str, status_code: int, back: str) -> Response:
    context = {"user": user, "message": msg(key), "back": back}
    return render(request, "message.html", context, status_code, no_store=True)


def _not_found(request: Request, user) -> Response:
    return _message_page(request, user, "error.not_found", 404, "/")


@router.post("/account/contact")
def save_contact(
    request: Request, user: RequiredUser, db: Db, username: FormStr = "", ack: FormStr = ""
) -> Response:
    if not contact.gateway.enabled:
        return _not_found(request, user)
    wait = limiter.hit(CONTACT_SAVES_PER_USER, str(user.id))
    if wait:
        return too_many(
            request, CONTACT_SAVES_PER_USER, wait, "rate.changes", user, back="/account"
        )
    if not username.strip():
        contact.gateway.save_username(db, user.id, None)
        event(request, "contact_cleared")
        return account_view(request, db, user, notice=msg("account.contact_removed"))
    clean = normalize(username)
    errors = []
    if clean is None:
        errors.append(msg("error.contact_username"))
    if ack != "yes":
        errors.append(msg("error.contact_ack"))
    if errors:
        # The rejected input is not sent back to the page.
        return account_view(request, db, user, 400, contact_errors=errors)
    contact.gateway.save_username(db, user.id, clean)
    event(request, "contact_saved")
    return account_view(request, db, user, notice=msg("account.contact_saved"))


@router.get("/matches/{match_id}/contact")
def share_confirm(request: Request, user: RequiredUser, db: Db, match_id: uuid.UUID) -> Response:
    """The warning page. Shows nothing about the other person except what /matches shows."""
    if not contact.gateway.enabled:
        return _not_found(request, user)
    match = db.get(Match, match_id)
    if match is None or user.id not in (match.user_a, match.user_b):
        return _message_page(request, user, "error.match_not_found", 404, "/matches")
    username = contact.gateway.own_username(db, user.id)
    if username is None:
        return _message_page(request, user, "error.contact_needs_username", 400, "/account")
    context = {"user": user, "match": match, "username": username}
    return render(request, "contact_confirm.html", context, no_store=True)


@router.post("/matches/{match_id}/contact")
def share(
    request: Request, user: RequiredUser, db: Db, match_id: uuid.UUID, confirm: FormStr = ""
) -> Response:
    if not contact.gateway.enabled:
        return _not_found(request, user)
    if confirm != "yes":
        return _message_page(request, user, "error.contact_confirm", 400, "/matches")
    wait = limiter.hit(CONTACT_SHARES_PER_USER, str(user.id))
    if wait:
        rule = CONTACT_SHARES_PER_USER
        return too_many(request, rule, wait, "rate.contact_shares", user, back="/matches")
    try:
        mutual = contact.gateway.share(db, user.id, match_id)
    except contact.MatchNotFound:
        return _message_page(request, user, "error.match_not_found", 404, "/matches")
    except contact.NoUsername:
        return _message_page(request, user, "error.contact_needs_username", 400, "/account")
    event(request, "contact_mutual" if mutual else "contact_shared")
    return RedirectResponse("/matches", status_code=303)
