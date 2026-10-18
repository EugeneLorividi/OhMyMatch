import re
import string
from pathlib import Path

import pytest

from app.i18n import CATALOGS, DEFAULT_LOCALE, LANG_COOKIE, LOCALES, negotiate, safe_next, translate
from tests.helpers import full_result_text, post, register

APP = Path(__file__).resolve().parent.parent / "app"


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_locales_have_the_same_keys():
    assert set(CATALOGS["uk"]) == set(CATALOGS["en"])


def test_locales_have_the_same_placeholders():
    for key in CATALOGS["uk"]:
        assert placeholders(CATALOGS["uk"][key]) == placeholders(CATALOGS["en"][key]), key


def test_no_empty_strings():
    for locale in LOCALES:
        assert all(value.strip() for value in CATALOGS[locale].values()), locale


def used_keys() -> set[str]:
    keys = set()
    for path in APP.rglob("*"):
        if path.suffix not in {".py", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        keys |= set(
            re.findall(
                r"""\b(?:t|msg|translate\(\s*\w+\s*,)\(?\s*["']([a-z_]+\.[a-z_.]+)["']""", text
            )
        )
        keys |= set(re.findall(r"""ImageRejected\(\s*["']([a-z_]+\.[a-z_.]+)["']""", text))
    # Prefixes of keys built at render time (e.g. "gender." ~ key) are checked separately.
    return {key for key in keys if not key.endswith(("_", "."))}


def test_every_used_key_exists():
    keys = used_keys()
    assert len(keys) > 60
    assert keys - set(CATALOGS["uk"]) == set()


def test_dynamic_keys_exist():
    from app.categories import AXES
    from app.config import GENDERS, MODES

    for locale in LOCALES:
        catalog = CATALOGS[locale]
        for axis in AXES:
            assert f"axis.{axis.key}" in catalog
        for key in GENDERS:
            assert f"gender.{key}" in catalog
        for key in MODES:
            assert f"mode.{key}" in catalog
            assert f"profile.mode_{key}_hint" in catalog


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        (None, None, "uk"),
        (None, "en-US,en;q=0.9", "en"),
        (None, "uk-UA,uk;q=0.9,en;q=0.8", "uk"),
        (None, "de-DE,en;q=0.5", "en"),
        (None, "en;q=0.4,uk;q=0.8", "uk"),
        (None, "fr,de", "uk"),
        (None, "en;q=0", "uk"),
        (None, "garbage;q=x,en", "en"),
        ("en", "uk", "en"),
        ("xx", "en", "en"),
    ],
)
def test_negotiate(cookie, header, expected):
    assert negotiate(cookie, header) == expected
    assert DEFAULT_LOCALE == "uk"


def test_safe_next():
    assert safe_next("/feed") == "/feed"
    for bad in (None, "", "https://evil.example", "//evil.example", "/\\evil", "feed"):
        assert safe_next(bad) == "/"


def test_default_is_ukrainian_and_accept_language_works(client):
    assert '<html lang="uk">' in client.get("/").text
    page = client.get("/", headers={"Accept-Language": "en-GB,en;q=0.9"}).text
    assert '<html lang="en">' in page
    assert translate("en", "index.guest_intro") in page


def test_switch_sets_small_cookie_and_redirects(client):
    response = client.get("/lang/en?next=/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{LANG_COOKIE}=en;")
    lowered = cookie.lower()
    assert "secure" in lowered and "httponly" in lowered and "samesite=lax" in lowered
    page = client.get("/login").text
    assert '<html lang="en">' in page
    assert translate("en", "login.title") in page
    assert 'href="/lang/uk?next=/login"' in page


def test_switch_rejects_unknown_language_and_open_redirect(client):
    assert client.get("/lang/ru", follow_redirects=False).status_code == 404
    response = client.get("/lang/en?next=//evil.example", follow_redirects=False)
    assert response.headers["location"] == "/"


@pytest.mark.parametrize("locale", LOCALES)
def test_pages_render_in_both_languages(client, db, locale):
    client.cookies.set(LANG_COOKIE, locale)
    register(client, db)
    for path in ("/", "/profile", "/result", "/dislikes", "/feed"):
        page = client.get(path).text
        assert f'<html lang="{locale}">' in page, path
    page = client.get("/result").text
    assert translate(locale, "result.english_hint") in page
    response = post(client, "/result/parse-text", {"text": full_result_text()})
    assert translate(locale, "result.found", found=25, total=25) in response.text


@pytest.mark.parametrize("locale", LOCALES)
def test_ocr_warning_in_both_languages(client, db, locale, monkeypatch):
    from app.parsing import ocr_parser
    from app.parsing.ocr_parser import OcrLine
    from tests.test_upload import png, upload

    monkeypatch.setattr(ocr_parser, "recognize_lines", lambda binary: [OcrLine("92% Rigger", 95.0)])
    client.cookies.set(LANG_COOKIE, locale)
    register(client, db)
    response = upload(client, [("images", ("a.png", png(), "image/png"))])
    assert translate(locale, "result.ocr_warning") in response.text


def test_csrf_and_size_errors_are_translated(client):
    client.cookies.set(LANG_COOKIE, "en")
    client.get("/login")
    assert client.post("/login", data={}).text == translate("en", "error.csrf")
    body = client.post(
        "/login", content=b"x" * (2 * 1024 * 1024), headers={"content-type": "text/plain"}
    )
    assert body.status_code == 413
    assert body.text == translate("en", "error.too_large")
