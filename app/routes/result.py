from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.datastructures import FormData, UploadFile

from app.accounts import refresh_is_active
from app.auth import RequiredUser
from app.categories import CATEGORIES, CATEGORY_KEYS
from app.config import OCR_MAX_FILE_BYTES, OCR_MAX_FILES, OCR_QUEUE_WAIT_SECONDS, PASTE_MAX_CHARS
from app.db.session import get_db
from app.forms import form_data
from app.i18n import Msg, msg
from app.models import TestScore, User
from app.parsing import ocr_parser
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
    errors: list[Msg] | None = None,
    notice: Msg | None = None,
    status_code: int = 200,
    ocr: bool = False,
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
        "ocr_max_files": OCR_MAX_FILES,
        "ocr": ocr,
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
        error = msg("error.paste_empty")
        return _result_page(request, user, {}, errors=[error], status_code=400)
    if len(text) > PASTE_MAX_CHARS:
        error = msg("error.paste_too_long", max=PASTE_MAX_CHARS)
        return _result_page(request, user, {}, errors=[error], status_code=400)
    parsed = parse_text(text)
    found = len(parsed.values)
    notice = msg("result.found", found=found, total=len(CATEGORY_KEYS))
    return _result_page(request, user, parsed.values, parsed.flagged, parsed.errors, notice)


@router.post("/result/parse-image")
def parse_result_image(request: Request, user: RequiredUser, form: Form) -> Response:
    uploads = [u for u in form.getlist("images") if isinstance(u, UploadFile) and u.filename]
    if not uploads:
        error = msg("error.no_images")
        return _result_page(request, user, {}, errors=[error], status_code=400)
    if len(uploads) > OCR_MAX_FILES:
        error = msg("error.too_many_images", max=OCR_MAX_FILES)
        return _result_page(request, user, {}, errors=[error], status_code=400)
    blobs = [upload.file.read(OCR_MAX_FILE_BYTES + 1) for upload in uploads]

    if not ocr_parser.slots.acquire(timeout=OCR_QUEUE_WAIT_SECONDS):
        error = msg("error.ocr_busy")
        return _result_page(request, user, {}, errors=[error], status_code=503)
    try:
        parsed = ocr_parser.parse_images(blobs)
    except ocr_parser.ImageRejected as exc:
        return _result_page(request, user, {}, errors=[exc.message], status_code=400)
    except RuntimeError:  # Tesseract timeout
        error = msg("error.ocr_timeout")
        return _result_page(request, user, {}, errors=[error], status_code=503)
    finally:
        ocr_parser.slots.release()

    notice = msg("result.found_ocr", found=len(parsed.values), total=len(CATEGORY_KEYS))
    return _result_page(
        request, user, parsed.values, parsed.flagged, parsed.errors, notice, ocr=True
    )


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
        error = msg("error.scores_invalid")
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
