import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import SESSION_TTL
from app.db.session import get_db
from app.models import User, UserSession

SESSION_COOKIE = "__Host-session"


class LoginRequired(Exception):
    pass


def _session_id(token: str) -> uuid.UUID:
    return uuid.UUID(bytes=hashlib.sha256(token.encode()).digest()[:16])


def create_session(db: Session, user: User, response: Response) -> None:
    now = datetime.now(UTC)
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= now)
    )
    token = secrets.token_urlsafe(32)
    db.add(UserSession(id=_session_id(token), user_id=user.id, expires_at=now + SESSION_TTL))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.id == _session_id(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


def delete_all_sessions(db: Session, user: User) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))


def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_session = db.get(UserSession, _session_id(token))
    if user_session is None:
        return None
    if user_session.expires_at <= datetime.now(UTC):
        db.delete(user_session)
        db.commit()
        return None
    return db.get(User, user_session.user_id)


def require_user(user: Annotated[User | None, Depends(get_current_user)]) -> User:
    if user is None:
        raise LoginRequired
    return user


CurrentUser = Annotated[User | None, Depends(get_current_user)]
RequiredUser = Annotated[User, Depends(require_user)]
