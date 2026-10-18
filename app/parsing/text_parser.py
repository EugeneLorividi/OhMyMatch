"""Parse pasted bdsmtest.org results: lines like `92% Rigger`. Other lines are ignored."""

import re
import unicodedata
from dataclasses import dataclass, field

from app.categories import ALIASES, CATEGORIES, CATEGORY_BY_KEY, CATEGORY_KEYS
from app.i18n import Msg, msg

LINE_RE = re.compile(r"^\s*(\d{1,3})\s*%\s+(.+?)\s*$", re.ASCII)

_PERCENT_SIGNS = str.maketrans({"％": "%", "﹪": "%", "٪": "%"})
_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—−", "-"))
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


@dataclass
class ParseResult:
    values: dict[str, int] = field(default_factory=dict)
    errors: list[Msg] = field(default_factory=list)
    # Keys that need the user's attention on the confirmation form.
    flagged: set[str] = field(default_factory=set)

    @property
    def missing(self) -> list[str]:
        return [key for key in CATEGORY_KEYS if key not in self.values]


def normalize_spaces(text: str) -> str:
    text = text.translate(_ZERO_WIDTH)
    return "".join(" " if unicodedata.category(ch) == "Zs" or ch == "\t" else ch for ch in text)


def normalize_name(name: str) -> str:
    name = normalize_spaces(name).translate(_DASHES).casefold()
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\s*([/()-])\s*", r"\1", name)
    return re.sub(r"(\S)\(", r"\1 (", name)


_CANONICAL = {normalize_name(c.name): c.key for c in CATEGORIES}


def match_name(name: str) -> str | None:
    normalized = normalize_name(name)
    return _CANONICAL.get(normalized) or ALIASES.get(normalized)


def split_line(raw: str) -> tuple[int, str] | None:
    """Returns (percent, name) for a `N% Name` line, None for any other line."""
    match = LINE_RE.match(normalize_spaces(raw).translate(_PERCENT_SIGNS))
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def parse_text(text: str) -> ParseResult:
    result = ParseResult()
    seen_on: dict[str, tuple[int, int]] = {}
    conflicting: set[str] = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        parts = split_line(raw)
        if parts is None:
            continue
        percent, name = parts
        key = match_name(name)
        if key is None:
            result.errors.append(msg("parse.unknown_category", line=number, name=name))
            continue
        label = CATEGORY_BY_KEY[key].name
        if not 0 <= percent <= 100:
            result.errors.append(
                msg("parse.out_of_range", line=number, category=label, percent=percent)
            )
            result.flagged.add(key)
            continue
        if key in seen_on:
            first_line, first_percent = seen_on[key]
            result.errors.append(
                msg(
                    "parse.duplicate",
                    line=number,
                    category=label,
                    first_line=first_line,
                    first_percent=first_percent,
                    percent=percent,
                )
            )
            result.flagged.add(key)
            if percent != first_percent:
                conflicting.add(key)
            continue
        seen_on[key] = (number, percent)
        result.values[key] = percent
    for key in conflicting:
        del result.values[key]
    result.flagged.update(result.missing)
    return result
