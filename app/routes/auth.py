from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, create_session, delete_all_sessions, end_session
from app.config import CONSENT_VERSION, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.csrf import rotate_csrf_token
from app.db.session import get_db
from app.handles import generate_handle, is_generated_handle
from app.i18n import Msg, msg
from app.models import Invite, User
from app.security import (
    generate_code,
    hash_invite_code,
    hash_secret,
    needs_rehash,
    normalize_code,
    verify_secret,
)
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]
FormStr = Annotated[str, Form()]

INVALID_INVITE = msg("error.invalid_invite")
INVALID_LOGIN = msg("error.invalid_login")
INVALID_RECOVERY = msg("error.invalid_recovery")


def _password_errors(password: str, confirm: str) -> list[Msg]:
    if len(password) < PASSWORD_MIN_LENGTH:
        return [msg("error.password_short", min=PASSWORD_MIN_LENGTH)]
    if len(password) > PASSWORD_MAX_LENGTH:
        return [msg("error.password_long", max=PASSWORD_MAX_LENGTH)]
    if password != confirm:
        return [msg("error.password_mismatch")]
    return []


def _find_invite(db: Session, code: str, *, lock: bool = False) -> Invite | None:
    stmt = select(Invite).where(
        Invite.code_hash == hash_invite_code(code),
        Invite.used_at.is_(None),
        Invite.expires_at > datetime.now(UTC),
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def _find_user(db: Session, handle: str) -> User | None:
    return db.scalars(select(User).where(User.handle == handle.strip().lower())).first()


def _redirect_home() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


def _register_details(
    request: Request,
    code: str,
    handle: str,
    errors: list[Msg] | None = None,
    status_code: int = 200,
    **checked: bool,
) -> Response:
    context = {"invite_code": code, "handle": handle, "errors": errors or [], **checked}
    return render(request, "register_details.html", context, status_code, no_store=True)


@router.get("/register")
def register_page(request: Request, user: CurrentUser) -> Response:
    if user is not None:
        return _redirect_home()
    return render(request, "register_code.html")


@router.post("/register")
def register(
    request: Request,
    db: Db,
    step: FormStr = "code",
    invite_code: FormStr = "",
    handle: FormStr = "",
    password: FormStr = "",
    password_confirm: FormStr = "",
    age_confirmed: FormStr = "",
    consent: FormStr = "",
) -> Response:
    code = normalize_code(invite_code)
    if not code or _find_invite(db, code) is None:
        return render(request, "register_code.html", {"errors": [INVALID_INVITE]}, 400)
    if step != "details":
        return _register_details(request, code, generate_handle())

    errors = []
    if age_confirmed != "yes":
        errors.append(msg("error.age_required"))
    if consent != "yes":
        errors.append(msg("error.consent_required"))
    if not is_generated_handle(handle):
        handle = generate_handle()
        errors.append(msg("error.pick_handle"))
    errors += _password_errors(password, password_confirm)
    checked = {"age_checked": age_confirmed == "yes", "consent_checked": consent == "yes"}
    if errors:
        return _register_details(request, code, handle, errors, 400, **checked)

    invite = _find_invite(db, code, lock=True)
    if invite is None:
        db.rollback()
        return render(request, "register_code.html", {"errors": [INVALID_INVITE]}, 400)
    now = datetime.now(UTC)
    recovery_code = generate_code()
    user = User(
        handle=handle,
        password_hash=hash_secret(password),
        recovery_code_hash=hash_secret(normalize_code(recovery_code)),
        consent_version=CONSENT_VERSION,
        consent_at=now,
        age_confirmed_at=now,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        taken = [msg("error.handle_taken")]
        return _register_details(request, code, generate_handle(), taken, 409, **checked)
    invite.used_by = user.id
    invite.used_at = now
    db.commit()

    rotate_csrf_token(request)
    context = {"user": user, "recovery_code": recovery_code}
    response = render(request, "register_done.html", context, no_store=True)
    create_session(db, user, response)
    return response


@router.get("/login")
def login_page(request: Request, user: CurrentUser) -> Response:
    if user is not None:
        return _redirect_home()
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, db: Db, handle: FormStr = "", password: FormStr = "") -> Response:
    user = _find_user(db, handle)
    if not verify_secret(user.password_hash if user else None, password) or user is None:
        return render(request, "login.html", {"errors": [INVALID_LOGIN]}, 400)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_secret(password)
        db.commit()
    rotate_csrf_token(request)
    response = _redirect_home()
    create_session(db, user, response)
    return response


@router.post("/logout")
def logout(request: Request, db: Db) -> Response:
    rotate_csrf_token(request)
    response = _redirect_home()
    end_session(db, request, response)
    return response


@router.get("/recover")
def recover_page(request: Request, user: CurrentUser) -> Response:
    if user is not None:
        return _redirect_home()
    return render(request, "recover.html")


@router.post("/recover")
def recover(
    request: Request,
    db: Db,
    handle: FormStr = "",
    recovery_code: FormStr = "",
    password: FormStr = "",
    password_confirm: FormStr = "",
) -> Response:
    errors = _password_errors(password, password_confirm)
    if errors:
        return render(request, "recover.html", {"errors": errors}, 400)
    user = _find_user(db, handle)
    stored = user.recovery_code_hash if user else None
    if not verify_secret(stored, normalize_code(recovery_code)) or user is None:
        return render(request, "recover.html", {"errors": [INVALID_RECOVERY]}, 400)

    new_code = generate_code()
    user.password_hash = hash_secret(password)
    user.recovery_code_hash = hash_secret(normalize_code(new_code))
    delete_all_sessions(db, user)
    db.commit()

    rotate_csrf_token(request)
    context = {"user": user, "recovery_code": new_code}
    response = render(request, "recover_done.html", context, no_store=True)
    create_session(db, user, response)
    return response
