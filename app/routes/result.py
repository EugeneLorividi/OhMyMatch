from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.accounts import refresh_is_active
from app.auth import RequiredUser
from app.categories import CATEGORIES, CATEGORY_KEYS
from app.config import PASTE_MAX_CHARS
from app.db.session import get_db
from app.forms import form_data
from app.models import TestScore, User
from app.parsing.text_parser import parse_text
from app.templating import render

router = APIRouter()

Db = Annotated[Session, Depends(get_db)]
Form = Annotated[FormData, Depends(form_data)]

FIELD_PREFIX = "score_"


def _result_page(
    request: Request,
    user: User,
    values: dict[str, int | str],
    flagged: set[str] | None = None,
    errors: list[str] | None = None,
    notice: str | None = None,
    status_code: int = 200,
) -> Response:
    context = {
        "user": user,
        "categories": CATEGORIES,
        "values": values,
        "flagged": flagged or set(),
        "errors": errors or [],
        "notice": notice,
        "field_prefix": FIELD_PREFIX,
        "paste_max": PASTE_MAX_CHARS,
    }
    # The page carries the user's own percentages: keep it out of any cache.
    return render(request, "result.html", context, status_code, no_store=True)


@router.get("/result")
def result_page(request: Request, user: RequiredUser, db: Db) -> Response:
    saved = db.get(TestScore, user.id)
    return _result_page(request, user, dict(saved.scores) if saved else {})


@router.post("/result/parse-text")
def parse_result_text(request: Request, user: RequiredUser, form: Form) -> Response:
    text = form.get("text")
    if not isinstance(text, str) or not text.strip():
        return _result_page(request, user, {}, errors=["Вставь текст результата."], status_code=400)
    if len(text) > PASTE_MAX_CHARS:
        error = f"Текст слишком длинный: не больше {PASTE_MAX_CHARS} символов."
        return _result_page(request, user, {}, errors=[error], status_code=400)
    parsed = parse_text(text)
    found = len(parsed.values)
    notice = f"Найдено {found} из {len(CATEGORY_KEYS)}. Проверь значения и подтверди."
    return _result_page(request, user, parsed.values, parsed.flagged, parsed.errors, notice)


def _read_scores(form: FormData) -> tuple[dict[str, int | str], dict[str, int], set[str]]:
    """Returns (values to re-render, valid scores, invalid keys)."""
    shown: dict[str, int | str] = {}
    scores: dict[str, int] = {}
    invalid: set[str] = set()
    for key in CATEGORY_KEYS:
        raw = form.get(FIELD_PREFIX + key)
        raw = raw.strip() if isinstance(raw, str) else ""
        shown[key] = raw
        if raw.isascii() and raw.isdigit() and 0 <= int(raw) <= 100:
            scores[key] = int(raw)
            shown[key] = scores[key]
        else:
            invalid.add(key)
    return shown, scores, invalid


@router.post("/result/save")
def save_result(request: Request, user: RequiredUser, db: Db, form: Form) -> Response:
    shown, scores, invalid = _read_scores(form)
    if invalid:
        error = "Заполни все 25 полей целыми числами от 0 до 100."
        return _result_page(request, user, shown, invalid, [error], status_code=400)
    saved = db.get(TestScore, user.id)
    if saved is None:
        db.add(TestScore(user_id=user.id, scores=scores))
    else:
        saved.scores = scores
    db.flush()
    refresh_is_active(db, user)
    db.commit()
    return RedirectResponse("/", status_code=303)
