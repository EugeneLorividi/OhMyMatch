from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.accounts import refresh_is_active
from app.auth import RequiredUser
from app.categories import CATEGORIES, CATEGORY_KEYS
from app.config import GENDERS, MODES
from app.db.session import get_db
from app.forms import form_data
from app.i18n import msg
from app.models import Dislike
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]
Form = Annotated[FormData, Depends(form_data)]


def _profile_page(request, user, gender, seeking, mode, errors=None, status=200):
    context = {
        "user": user,
        "genders": GENDERS,
        "modes": MODES,
        "gender": gender,
        "seeking": seeking,
        "mode": mode,
        "errors": errors or [],
    }
    return render(request, "profile.html", context, status)


@router.get("/profile")
def profile_page(request: Request, user: RequiredUser) -> Response:
    return _profile_page(request, user, user.gender, user.seeking or [], user.mode)


@router.post("/profile")
def save_profile(request: Request, user: RequiredUser, db: Db, form: Form) -> Response:
    gender = form.get("gender")
    seeking = form.getlist("seeking")
    mode = form.get("mode")
    errors = []
    if gender not in GENDERS:
        errors.append(msg("error.pick_gender"))
    if not seeking or not set(seeking) <= set(GENDERS):
        errors.append(msg("error.pick_seeking"))
    if mode not in MODES:
        errors.append(msg("error.pick_mode"))
    if errors:
        clean_seeking = [g for g in seeking if g in GENDERS]
        return _profile_page(request, user, gender, clean_seeking, mode, errors, status=400)

    user.gender = gender
    user.seeking = [g for g in GENDERS if g in seeking]
    user.mode = mode
    refresh_is_active(db, user)
    db.commit()
    return RedirectResponse("/", status_code=303)


def _current_dislikes(db: Session, user) -> set[str]:
    return set(db.scalars(select(Dislike.category_key).where(Dislike.user_id == user.id)))


@router.get("/dislikes")
def dislikes_page(request: Request, user: RequiredUser, db: Db) -> Response:
    context = {"user": user, "categories": CATEGORIES, "selected": _current_dislikes(db, user)}
    return render(request, "dislikes.html", context)


@router.post("/dislikes")
def save_dislikes(request: Request, user: RequiredUser, db: Db, form: Form) -> Response:
    chosen = form.getlist("category")
    if not set(chosen) <= set(CATEGORY_KEYS):
        context = {
            "user": user,
            "categories": CATEGORIES,
            "selected": {key for key in chosen if key in CATEGORY_KEYS},
            "errors": [msg("error.unknown_category_key")],
        }
        return render(request, "dislikes.html", context, 400)
    db.execute(delete(Dislike).where(Dislike.user_id == user.id))
    db.add_all(Dislike(user_id=user.id, category_key=key) for key in set(chosen))
    db.commit()
    return RedirectResponse("/", status_code=303)
