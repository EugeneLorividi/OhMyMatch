"""Upload route and image validation; Tesseract is replaced where it is not the subject."""

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.config import OCR_MAX_FILE_BYTES
from app.models import TestScore
from app.parsing import ocr_parser
from app.parsing.ocr_parser import ImageRejected, OcrLine, load_image
from tests.helpers import csrf, post, register, uk
from tests.ocr_fixtures import render

WARNING = uk("result.ocr_warning")


@pytest.fixture
def fake_ocr(monkeypatch):
    lines = [OcrLine("92% Rigger", 95.0), OcrLine("79% Dominant", 40.0)]
    monkeypatch.setattr(ocr_parser, "recognize_lines", lambda binary: lines)


def upload(client, files, data=None):
    form = {"csrf_token": csrf(client), **(data or {})}
    return client.post("/result/parse-image", data=form, files=files)


def png(size=(40, 20)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_requires_login(client):
    form = {"csrf_token": csrf(client)}
    files = [("images", ("a.png", png(), "image/png"))]
    response = client.post("/result/parse-image", data=form, files=files, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_ocr_result_shows_warning_and_flags(client, db, fake_ocr):
    register(client, db)
    response = upload(client, [("images", ("a.png", png(), "image/png"))])
    assert response.status_code == 200
    assert WARNING in response.text
    assert response.headers["cache-control"] == "no-store"
    assert 'value="92"' in response.text
    assert response.text.count("score flagged") == 24  # dominant low confidence + 23 missing
    assert db.scalars(select(TestScore)).first() is None


def test_text_parse_has_no_ocr_warning(client, db):
    register(client, db)
    response = post(client, "/result/parse-text", {"text": "92% Rigger"})
    assert WARNING not in response.text


def test_rejects_more_than_three_files(client, db, fake_ocr):
    register(client, db)
    files = [("images", (f"{i}.png", png(), "image/png")) for i in range(4)]
    response = upload(client, files)
    assert response.status_code == 400
    assert uk("error.too_many_images", max=3) in response.text


def test_rejects_no_files(client, db):
    register(client, db)
    assert upload(client, [("images", ("", b"", "application/octet-stream"))]).status_code == 400


def test_rejects_large_file(client, db, fake_ocr):
    register(client, db)
    big = b"\x89PNG" + b"0" * OCR_MAX_FILE_BYTES
    response = upload(client, [("images", ("a.png", big, "image/png"))])
    assert response.status_code == 400
    assert uk("error.image_too_big") in response.text


@pytest.mark.parametrize(
    "data",
    [b"not an image at all", b"GIF89a" + b"\x00" * 20],
)
def test_rejects_non_images(client, db, fake_ocr, data):
    register(client, db)
    response = upload(client, [("images", ("a.png", data, "image/png"))])
    assert response.status_code == 400


def test_rejects_gif_even_with_png_name(client, db, fake_ocr):
    register(client, db)
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    response = upload(client, [("images", ("a.png", gif.getvalue(), "image/png"))])
    assert response.status_code == 400
    assert uk("error.image_format") in response.text


def test_busy_returns_503(client, db, fake_ocr, monkeypatch):
    register(client, db)

    class Busy:
        def acquire(self, timeout):
            return False

        def release(self):
            raise AssertionError("must not release a slot it did not get")

    monkeypatch.setattr(ocr_parser, "slots", Busy())
    response = upload(client, [("images", ("a.png", png(), "image/png"))])
    assert response.status_code == 503


def test_slot_is_released_after_rejection(client, db, fake_ocr):
    register(client, db)
    for _ in range(3):
        upload(client, [("images", ("a.png", b"junk", "image/png"))])
    assert ocr_parser.slots.acquire(timeout=0)
    ocr_parser.slots.release()


def test_exif_is_removed():
    image = Image.new("RGB", (30, 20), "white")
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCam"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    clean = load_image(buffer.getvalue())
    assert clean.size == (20, 30)  # orientation applied before metadata was dropped
    assert dict(clean.getexif()) == {}
    assert clean.info == {}


def test_rejects_huge_pixel_count(monkeypatch):
    monkeypatch.setattr(ocr_parser, "OCR_MAX_INPUT_PIXELS", 100)
    with pytest.raises(ImageRejected):
        load_image(png((20, 20)))


def test_synthetic_fixture_is_valid_image():
    assert load_image(render(["10% Pet"])).size[0] == 560
