"""Builds the feed on the fly: SQL narrows by gender, Python filters and ranks."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import any_, select
from sqlalchemy.orm import Session

from app.config import FEED_PAGE_SIZE
from app.matching.explain import explain
from app.matching.filters import passes_filters
from app.matching.profile import Profile
from app.matching.scoring import MatchScore, score_match
from app.models import Dislike, TestScore, User


@dataclass(frozen=True)
class Card:
    """Everything the viewer may learn about a candidate (section 7, step 7)."""

    public_id: uuid.UUID
    handle: str
    matched: tuple[str, ...]
    curious: tuple[str, ...]


@dataclass(frozen=True)
class FeedPage:
    cards: list[Card]
    page: int
    has_next: bool


def _profiles(db: Session, rows) -> list[Profile]:
    ids = [user.id for user, _ in rows]
    dislikes: dict[uuid.UUID, set[str]] = {}
    if ids:
        query = select(Dislike.user_id, Dislike.category_key).where(Dislike.user_id.in_(ids))
        for user_id, key in db.execute(query):
            dislikes.setdefault(user_id, set()).add(key)
    return [
        Profile(
            id=user.id,
            gender=user.gender,
            seeking=frozenset(user.seeking or ()),
            mode=user.mode,
            scores=scores,
            dislikes=frozenset(dislikes.get(user.id, ())),
        )
        for user, scores in rows
    ]


def load_viewer(db: Session, user: User) -> Profile | None:
    if not user.is_active:
        return None
    scores = db.scalar(select(TestScore.scores).where(TestScore.user_id == user.id))
    if scores is None:
        return None
    return _profiles(db, [(user, scores)])[0]


def load_candidates(db: Session, viewer: Profile) -> tuple[list[Profile], dict[uuid.UUID, str]]:
    query = (
        select(User, TestScore.scores)
        .join(TestScore, TestScore.user_id == User.id)
        .where(
            User.is_active.is_(True),
            User.id != viewer.id,
            User.gender.in_(viewer.seeking),
            any_(User.seeking) == viewer.gender,
        )
    )
    rows = db.execute(query).all()
    handles = {user.id: user.handle for user, _ in rows}
    return _profiles(db, rows), handles


def excluded_ids(db: Session, viewer: Profile) -> frozenset[uuid.UUID]:
    """Candidates hidden by reactions. Reactions arrive in stage 6; until then nobody is."""
    return frozenset()


def tie_key(viewer_id: uuid.UUID, candidate_id: uuid.UUID, day: date) -> bytes:
    """Random but stable for a viewer within a day."""
    return hashlib.sha256(f"{viewer_id}:{day.isoformat()}:{candidate_id}".encode()).digest()


def rank(
    viewer: Profile,
    candidates: list[Profile],
    excluded: frozenset[uuid.UUID],
    day: date,
) -> list[tuple[Profile, MatchScore]]:
    ranked = []
    for candidate in candidates:
        if not passes_filters(viewer, candidate, excluded):
            continue
        match = score_match(viewer, candidate)
        if not match.has_strict:
            continue
        ranked.append((candidate, match))
    ranked.sort(key=lambda item: (-round(item[1].score, 9), tie_key(viewer.id, item[0].id, day)))
    return ranked


def build_feed(db: Session, user: User, page: int, day: date | None = None) -> FeedPage | None:
    viewer = load_viewer(db, user)
    if viewer is None:
        return None
    candidates, handles = load_candidates(db, viewer)
    day = day or datetime.now(UTC).date()
    ranked = rank(viewer, candidates, excluded_ids(db, viewer), day)
    start = (page - 1) * FEED_PAGE_SIZE
    window = ranked[start : start + FEED_PAGE_SIZE]
    cards = []
    for candidate, match in window:
        explanation = explain(match)
        cards.append(
            Card(candidate.id, handles[candidate.id], explanation.matched, explanation.curious)
        )
    return FeedPage(cards, page, has_next=len(ranked) > start + FEED_PAGE_SIZE)
