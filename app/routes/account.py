from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth import RequiredUser, create_session, delete_all_sessions, end_session
from app.config import ACCOUNT_ACTIONS_PER_USER
from app.csrf import rotate_csrf_token
from app.db.session import get_db
from app.eventlog import event
from app.i18n import msg
from app.models import User
from app.ratelimit import limiter
from app.routes._limits import too_many
from app.routes.auth import _password_errors
from app.security import hash_secret, verify_secret
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]
FormStr = Annotated[str, Form()]


def _page(request: Request, user: User, status_code: int = 200, **context) -> Response:
    return render(request, "account.html", {"user": user, **context}, status_code)


def _limited(request: Request, user: User) -> Response | None:
    wait = limiter.hit(ACCOUNT_ACTIONS_PER_USER, str(user.id))
    if wait:
        rule = ACCOUNT_ACTIONS_PER_USER
        return too_many(request, rule, wait, "rate.attempts", user, back="/account")
    return None


@router.get("/account")
def account_page(request: Request, user: RequiredUser) -> Response:
    return _page(request, user)


@router.post("/account/password")
def change_password(
    request: Request,
    user: RequiredUser,
    db: Db,
    current_password: FormStr = "",
    password: FormStr = "",
    password_confirm: FormStr = "",
) -> Response:
    if (limited := _limited(request, user)) is not None:
        return limited
    if not verify_secret(user.password_hash, current_password):
        event(request, "password_change_failed")
        return _page(request, user, 400, password_errors=[msg("error.wrong_password")])
    errors = _password_errors(password, password_confirm)
    if errors:
        return _page(request, user, 400, password_errors=errors)
    user.password_hash = hash_secret(password)
    # Section 6: every session ends on a password change; this browser gets a fresh one.
    delete_all_sessions(db, user)
    db.commit()
    event(request, "password_changed")
    rotate_csrf_token(request)
    response = _page(request, user, notice=msg("account.password_changed"))
    create_session(db, user, response)
    return response


@router.post("/account/delete")
def delete_account(
    request: Request, user: RequiredUser, db: Db, password: FormStr = ""
) -> Response:
    if (limited := _limited(request, user)) is not None:
        return limited
    if not verify_secret(user.password_hash, password):
        event(request, "account_delete_failed")
        return _page(request, user, 400, delete_errors=[msg("error.wrong_password")])
    # Hard delete; every other table cascades from users (sessions included).
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    event(request, "account_deleted")
    rotate_csrf_token(request)
    response = render(request, "account_deleted.html", {"user": None})
    end_session(db, request, response)
    return response
