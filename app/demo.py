"""Synthetic demo users for a manual walk-through (admin CLI only, never a web page).

The profiles are hard-coded and stable. Every category not named below gets a fixed value
between 0 and 15, so nobody has a real or random result. All six are removed again by
`delete-demo` before invites are handed out.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.accounts import refresh_is_active
from app.categories import CATEGORY_KEYS
from app.config import CONSENT_VERSION
from app.models import Dislike, Reaction, TestScore, User
from app.security import hash_secret

DEMO_PREFIX = "demo_"
FILLER_MAX = 15
LIKER = f"{DEMO_PREFIX}1"  # likes the --target user, so the return like gives a match

_POWER_PROFILE = {
    "submissive": 90,
    "degradee": 85,
    "rope-bunny": 80,
    "voyeur": 70,
    "experimentalist": 60,
    "vanilla": 45,
}


@dataclass(frozen=True)
class DemoSpec:
    handle: str
    gender: str
    seeking: tuple[str, ...]
    mode: str
    scores: dict[str, int]
    dislikes: tuple[str, ...] = ()


DEMO_SPECS: tuple[DemoSpec, ...] = (
    DemoSpec("demo_1", "woman", ("man",), "normal", _POWER_PROFILE),
    DemoSpec("demo_2", "woman", ("man",), "normal", _POWER_PROFILE, ("degrader",)),
    DemoSpec("demo_3", "woman", ("woman",), "normal", _POWER_PROFILE),
    DemoSpec("demo_4", "man", ("woman",), "normal", _POWER_PROFILE),
    DemoSpec(
        "demo_5",
        "woman",
        ("man",),
        "experimental",
        {"voyeur": 80, "submissive": 45, "degradee": 40, "rope-bunny": 40},
    ),
    DemoSpec("demo_6", "woman", ("man",), "normal", {"dominant": 90, "degrader": 80, "sadist": 70}),
)


def full_scores(spec: DemoSpec) -> dict[str, int]:
    """All 25 values: the named ones, and a stable 0..15 for the rest."""
    number = int(spec.handle.removeprefix(DEMO_PREFIX))
    scores = {
        key: (index * 7 + number * 5) % (FILLER_MAX + 1) for index, key in enumerate(CATEGORY_KEYS)
    }
    scores.update(spec.scores)
    return scores


def _is_demo():
    # "_" is a wildcard in LIKE, so it is escaped to match the prefix literally.
    return User.handle.like(DEMO_PREFIX.replace("_", r"\_") + "%", escape="\\")


def demo_handles(db: Session) -> list[str]:
    return list(db.scalars(select(User.handle).where(_is_demo())))


def new_passwords() -> dict[str, str]:
    return {spec.handle: secrets.token_urlsafe(16) for spec in DEMO_SPECS}


def seed_demo(db: Session, passwords: dict[str, str], target: User) -> int:
    now = datetime.now(UTC)
    created: dict[str, User] = {}
    for spec in DEMO_SPECS:
        user = User(
            handle=spec.handle,
            password_hash=hash_secret(passwords[spec.handle]),
            gender=spec.gender,
            seeking=list(spec.seeking),
            mode=spec.mode,
            consent_version=CONSENT_VERSION,
            consent_at=now,
            age_confirmed_at=now,
        )
        db.add(user)
        db.flush()
        db.add(TestScore(user_id=user.id, scores=full_scores(spec)))
        db.add_all(Dislike(user_id=user.id, category_key=key) for key in spec.dislikes)
        db.flush()
        refresh_is_active(db, user)
        created[spec.handle] = user
    db.add(Reaction(from_user=created[LIKER].id, to_user=target.id, kind="like"))
    db.commit()
    return len(created)


def delete_demo(db: Session) -> int:
    result = db.execute(delete(User).where(_is_demo()))
    db.commit()
    return result.rowcount
