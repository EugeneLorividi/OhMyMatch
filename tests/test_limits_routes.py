"""Every rate limit from stage 7, through the real routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import clientip
from app.categories import CATEGORY_KEYS
from app.config import (
    DISLIKES_SAVES_PER_USER,
    FEED_PAGES_PER_USER,
    LOGIN_FAILS_PER_HANDLE,
    LOGIN_PER_IP,
    OCR_PER_USER,
    PROFILE_SAVES_PER_USER,
    REACTIONS_PER_USER,
    RECOVER_FAILS_PER_HANDLE,
    RECOVER_PER_IP,
    REGISTER_PER_IP,
    RESULT_SAVES_PER_USER,
)
from app.main import app
from app.models import User
from app.parsing import ocr_parser
from app.parsing.ocr_parser import OcrLine
from tests.helpers import PASSWORD, csrf, post, register, score_form, uk
from tests.test_feed import add_user
from tests.test_upload import png

SCORES = {**dict.fromkeys(CATEGORY_KEYS, 0), "dominant": 90}


def login(client, handle, password="wrong password!"):  # noqa: S107
    return post(client, "/login", {"handle": handle, "password": password}, follow_redirects=False)


def test_login_per_handle(client, db):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    for _ in range(LOGIN_FAILS_PER_HANDLE.limit):
        assert login(client, handle).status_code == 400
    blocked = login(client, handle, PASSWORD)  # even the right password waits now
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert uk("rate.attempts") in blocked.text
    assert login(client, "brave-fox-11").status_code == 400  # other handles unaffected


def test_login_success_does_not_count_against_handle(client, db):
    handle, _, _ = register(client, db)
    for _ in range(LOGIN_FAILS_PER_HANDLE.limit + 2):
        client.cookies.clear()
        assert login(client, handle, PASSWORD).status_code == 303


def test_login_per_ip(client):
    for index in range(LOGIN_PER_IP.limit):
        assert login(client, f"user-{index}").status_code == 400
    assert login(client, "user-final").status_code == 429


def test_register_per_ip(client):
    for _ in range(REGISTER_PER_IP.limit):
        assert post(client, "/register", {"invite_code": "AAAA"}).status_code == 400
    assert post(client, "/register", {"invite_code": "AAAA"}).status_code == 429


def recover(client, handle, code="AAAA-BBBB-CCCC-DDDD"):
    data = {
        "handle": handle,
        "recovery_code": code,
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }
    return post(client, "/recover", data)


def test_recover_per_handle_and_per_ip(client, db):
    handle, code, _ = register(client, db)
    client.cookies.clear()
    for _ in range(RECOVER_FAILS_PER_HANDLE.limit):
        assert recover(client, handle).status_code == 400
    assert recover(client, handle, code).status_code == 429  # right code, but handle is locked
    remaining = RECOVER_PER_IP.limit - RECOVER_FAILS_PER_HANDLE.limit - 1
    for index in range(remaining):
        assert recover(client, f"other-{index}").status_code == 400
    assert recover(client, "fresh-handle").status_code == 429


@pytest.fixture
def via_proxy(monkeypatch):
    """A client behind a trusted proxy, so X-Forwarded-For picks the address."""
    monkeypatch.setattr(clientip.settings, "trusted_proxies", "172.31.240.1")
    clientip._trusted.cache_clear()
    with TestClient(app, base_url="https://testserver", client=("172.31.240.1", 40000)) as c:
        yield c
    clientip._trusted.cache_clear()


def test_per_ip_limits_follow_forwarded_address(via_proxy):
    counter = iter(range(1000))

    def attempt(ip, forged=None):
        header = f"{forged}, {ip}" if forged else ip
        handle = f"nobody-{next(counter)}"  # distinct, so only the per-IP rule can trigger
        data = {"csrf_token": csrf(via_proxy), "handle": handle, "password": "x" * 12}
        return via_proxy.post("/login", data=data, headers={"X-Forwarded-For": header})

    for _ in range(LOGIN_PER_IP.limit):
        attempt("203.0.113.1")
    assert attempt("203.0.113.1").status_code == 429
    assert attempt("203.0.113.2").status_code == 400  # another client is unaffected
    # A forged leftmost entry does not help the limited client.
    assert attempt("203.0.113.1", forged="198.51.100.77").status_code == 429


def active_user(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    post(client, "/result/save", score_form(SCORES))
    return db.scalars(select(User)).one()


def test_feed_pages_per_day(client, db):
    active_user(client, db)
    for _ in range(FEED_PAGES_PER_USER.limit):
        assert client.get("/feed").status_code == 200
    blocked = client.get("/feed")
    assert blocked.status_code == 429
    assert uk("rate.feed", limit=FEED_PAGES_PER_USER.limit) in blocked.text
    fragment = client.get("/feed?page=2", headers={"HX-Request": "true"})
    assert fragment.status_code == 200 and "<html" not in fragment.text


def test_inactive_user_feed_visits_do_not_count(client, db):
    register(client, db)
    for _ in range(FEED_PAGES_PER_USER.limit + 3):
        assert client.get("/feed").status_code == 200


def test_reactions_per_day(client, db):
    active_user(client, db)
    her = add_user(db, submissive=80)
    for _ in range(REACTIONS_PER_USER.limit):
        post(client, "/react", {"target": str(her.id), "kind": "pass"})
    blocked = post(client, "/react", {"target": str(her.id), "kind": "pass"})
    assert blocked.status_code == 429
    assert uk("rate.reactions", limit=REACTIONS_PER_USER.limit) in blocked.text


@pytest.mark.parametrize(
    ("path", "data", "rule", "already"),
    [
        ("/result/save", score_form(SCORES), RESULT_SAVES_PER_USER, 1),
        ("/dislikes", {"category": ["brat"]}, DISLIKES_SAVES_PER_USER, 0),
        (
            "/profile",
            {"gender": "man", "seeking": ["woman"], "mode": "normal"},
            PROFILE_SAVES_PER_USER,
            1,
        ),
    ],
)
def test_few_changes_per_day(client, db, path, data, rule, already):
    active_user(client, db)
    for _ in range(rule.limit - already):
        assert post(client, path, data, follow_redirects=False).status_code == 303
    blocked = post(client, path, data)
    assert blocked.status_code == 429
    assert uk("rate.changes", limit=rule.limit) in blocked.text


def test_failed_change_does_not_count(client, db):
    active_user(client, db)
    for _ in range(PROFILE_SAVES_PER_USER.limit + 2):
        assert post(client, "/profile", {"gender": "robot"}).status_code == 400


def test_ocr_per_user(client, db, monkeypatch):
    monkeypatch.setattr(ocr_parser, "recognize_lines", lambda binary: [OcrLine("92% Rigger", 95.0)])
    register(client, db)
    files = [("images", ("a.png", png(), "image/png"))]
    for _ in range(OCR_PER_USER.limit):
        assert post(client, "/result/parse-image", files=files).status_code == 200
    blocked = post(client, "/result/parse-image", files=files)
    assert blocked.status_code == 429
    assert uk("rate.ocr", limit=OCR_PER_USER.limit) in blocked.text
