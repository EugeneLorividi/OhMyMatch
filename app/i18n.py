"""UI strings in Ukrainian (default) and English. All user-facing text lives in app/locales."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

LOCALES = ("uk", "en")
DEFAULT_LOCALE = "uk"
LANG_COOKIE = "__Host-lang"
LANG_COOKIE_MAX_AGE = 365 * 24 * 3600

_DIR = Path(__file__).parent / "locales"
CATALOGS: dict[str, dict[str, str]] = {
    code: json.loads((_DIR / f"{code}.json").read_text(encoding="utf-8")) for code in LOCALES
}


@dataclass(frozen=True)
class Msg:
    """A translatable message: produced by code, rendered in the viewer's language."""

    key: str
    params: Mapping[str, Any] = field(default_factory=dict)


def msg(key: str, **params: Any) -> Msg:
    return Msg(key, params)


def translate(locale: str, key: str, **params: Any) -> str:
    return CATALOGS[locale][key].format(**params)


def translate_msg(locale: str, message: Msg) -> str:
    return translate(locale, message.key, **message.params)


def negotiate(cookie: str | None, accept_language: str | None) -> str:
    if cookie in LOCALES:
        return cookie
    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate((accept_language or "").split(",")):
        tag, _, rest = part.strip().partition(";")
        quality = 1.0
        if rest.strip().startswith("q="):
            try:
                quality = float(rest.strip()[2:])
            except ValueError:
                continue
        primary = tag.split("-")[0].strip().lower()
        if primary in LOCALES and quality > 0:
            ranked.append((-quality, index, primary))
    return min(ranked)[2] if ranked else DEFAULT_LOCALE


def get_locale(request: Request) -> str:
    locale = getattr(request.state, "locale", None)
    if locale is None:
        locale = negotiate(request.cookies.get(LANG_COOKIE), request.headers.get("accept-language"))
        request.state.locale = locale
    return locale


def safe_next(path: str | None) -> str:
    """Only same-site absolute paths, so the language switch is not an open redirect."""
    if not path or not path.startswith("/") or path.startswith(("//", "/\\")):
        return "/"
    return path
