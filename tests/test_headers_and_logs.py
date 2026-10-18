import io
import logging
import re
import struct
import zlib

import pytest
from PIL import ImageFile

from app.eventlog import logger
from app.main import app
from app.middleware import SECURITY_HEADERS
from app.parsing.ocr_parser import ImageRejected, load_image
from tests.helpers import PASSWORD, post, register

LINE = re.compile(r"event=[a-z_.]+ request_id=[0-9a-f]{32}")


@pytest.mark.parametrize(
    "path", ["/", "/login", "/privacy", "/nope", "/static/style.css", "/healthz"]
)
def test_security_headers_everywhere(client, path):
    response = client.get(path)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value, (path, name)
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_csp_is_strict():
    csp = SECURITY_HEADERS["content-security-policy"]
    assert "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp


def test_pages_are_not_cached_but_static_files_may_be(client):
    assert client.get("/").headers["cache-control"] == "no-store"
    assert client.get("/nope").headers["cache-control"] == "no-store"
    assert "no-store" not in client.get("/static/style.css").headers.get("cache-control", "")


def test_error_responses_have_headers_too(client):
    client.get("/login")
    response = client.post(
        "/login", content=b"x" * (2 * 1024 * 1024), headers={"content-type": "text/plain"}
    )
    assert response.status_code == 413
    assert response.headers["x-frame-options"] == "DENY"


@pytest.fixture
def records():
    captured: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            captured.append(record)

    handler = Collect()
    logger.addHandler(handler)
    yield captured
    logger.removeHandler(handler)


def test_log_lines_are_event_and_request_id_only(client, db, records):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    post(client, "/login", {"handle": handle, "password": "wrong password!"})
    post(client, "/login", {"handle": handle, "password": PASSWORD})
    client.post("/logout", data={})  # CSRF failure
    lines = [record.getMessage() for record in records]
    events = [line.split()[0] for line in lines]
    assert events == [
        "event=registered",
        "event=login_failed",
        "event=login_succeeded",
        "event=csrf_failed",
    ]
    for line in lines:
        assert LINE.fullmatch(line), line
        assert handle not in line and PASSWORD not in line


def test_unhandled_error_is_contained(client, records, monkeypatch):
    from app.routes import pages

    def boom(*args, **kwargs):
        raise RuntimeError("sensitive detail: dominant=91 brave-fox-11")

    monkeypatch.setattr(pages, "render", boom)
    root_records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            root_records.append(record)

    root = logging.getLogger()
    collector = Collect()
    root.addHandler(collector)
    try:
        response = client.get("/")
    finally:
        root.removeHandler(collector)
    assert response.status_code == 500
    assert "sensitive" not in response.text
    assert [record.getMessage().split()[0] for record in records] == ["event=unhandled_error"]
    assert all("sensitive" not in record.getMessage() for record in root_records + records)


def test_event_names_cannot_carry_data():
    from app.eventlog import log_event

    with pytest.raises(ValueError):
        log_event("login_failed handle=brave-fox-11", "0" * 32)


def png_header_only(width: int, height: int) -> bytes:
    """A PNG that declares a huge size but carries almost no pixel data."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("size", [(7_000, 7_000), (20_000, 20_000)])
def test_pixel_limit_is_checked_before_decoding(monkeypatch, size):
    """49 MP passes Pillow's guard and is caught by our header check; 400 MP trips Pillow's
    own decompression-bomb error in Image.open. Neither decodes a single pixel."""

    def no_decoding(self):
        raise AssertionError("pixel data must not be decoded")

    monkeypatch.setattr(ImageFile.ImageFile, "load", no_decoding)
    with pytest.raises(ImageRejected) as caught:
        load_image(png_header_only(*size))
    assert caught.value.message.key == "error.image_pixels"


def test_app_does_not_expose_docs():
    assert app.docs_url is None and app.openapi_url is None
    assert io  # keeps the import used for symmetry with other image tests
