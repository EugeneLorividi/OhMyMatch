"""Synthetic profiles for matching tests."""

import uuid

from app.categories import CATEGORY_KEYS
from app.matching.profile import Profile


def profile(
    gender: str = "man",
    seeking: tuple[str, ...] = ("woman",),
    mode: str = "normal",
    dislikes: tuple[str, ...] = (),
    base: int = 0,
    **scores: int,
) -> Profile:
    values = dict.fromkeys(CATEGORY_KEYS, base)
    for name, value in scores.items():
        key = name.replace("_", "-")
        assert key in values, key
        values[key] = value
    return Profile(
        id=uuid.uuid4(),
        gender=gender,
        seeking=frozenset(seeking),
        mode=mode,
        scores=values,
        dislikes=frozenset(dislikes),
    )


def her(**kwargs) -> Profile:
    kwargs.setdefault("gender", "woman")
    kwargs.setdefault("seeking", ("man",))
    return profile(**kwargs)
