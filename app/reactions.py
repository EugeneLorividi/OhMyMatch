"""Likes, passes, blocks and mutual matches (section 8)."""

import enum
import uuid

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import contact
from app.matching.feed import load_profile
from app.matching.filters import passes_filters
from app.matching.scoring import score_match
from app.models import Match, Reaction, User
from app.models.reaction import KINDS


class Outcome(enum.Enum):
    LIKED = "liked"
    MATCHED = "matched"
    PASSED = "passed"
    BLOCKED = "blocked"
    UNCHANGED = "unchanged"


class Unavailable(Exception):
    """Target missing, self, or not someone the viewer may like. Same answer for all cases."""


def ordered(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


def _lock_pair(db: Session, a: uuid.UUID, b: uuid.UUID) -> None:
    """Serializes reactions within one pair, so two simultaneous likes make one match."""
    low, high = ordered(a, b)
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"pair:{low}:{high}"},
    )


def blocked_either_way(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    query = select(func.count()).where(
        Reaction.kind == "block",
        or_(
            (Reaction.from_user == a) & (Reaction.to_user == b),
            (Reaction.from_user == b) & (Reaction.to_user == a),
        ),
    )
    return bool(db.scalar(query))


def _may_like(db: Session, viewer: User, target_id: uuid.UUID) -> bool:
    """A like needs the same eligibility as the feed, so it cannot bypass the filters."""
    me = load_profile(db, viewer)
    target = db.get(User, target_id)
    if me is None or target is None:
        return False
    them = load_profile(db, target)
    if them is None or blocked_either_way(db, viewer.id, target_id):
        return False
    return passes_filters(me, them) and score_match(me, them).has_strict


def _delete_match(db: Session, a: uuid.UUID, b: uuid.UUID) -> None:
    low, high = ordered(a, b)
    db.execute(delete(Match).where(Match.user_a == low, Match.user_b == high))


def _set_block(db: Session, from_user: uuid.UUID, to_user: uuid.UUID) -> None:
    statement = insert(Reaction).values(from_user=from_user, to_user=to_user, kind="block")
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[Reaction.from_user, Reaction.to_user],
            set_={"kind": "block", "created_at": func.now()},
        )
    )


def react(db: Session, viewer: User, target_id: uuid.UUID, kind: str) -> Outcome:
    if kind not in KINDS:
        raise ValueError(kind)
    if target_id == viewer.id or db.get(User, target_id) is None:
        raise Unavailable
    _lock_pair(db, viewer.id, target_id)
    existing = db.get(Reaction, (viewer.id, target_id))

    if kind == "block":
        if existing is None:
            db.add(Reaction(from_user=viewer.id, to_user=target_id, kind="block"))
        elif existing.kind != "block":
            db.execute(
                update(Reaction)
                .where(Reaction.from_user == viewer.id, Reaction.to_user == target_id)
                .values(kind="block", created_at=func.now())
            )
        _delete_match(db, viewer.id, target_id)
        db.commit()
        return Outcome.BLOCKED

    if existing is not None:
        # Only a block replaces an earlier reaction.
        db.rollback()
        return Outcome.UNCHANGED
    if kind == "pass":
        db.add(Reaction(from_user=viewer.id, to_user=target_id, kind="pass"))
        db.commit()
        return Outcome.PASSED

    if not _may_like(db, viewer, target_id):
        db.rollback()
        raise Unavailable
    db.add(Reaction(from_user=viewer.id, to_user=target_id, kind="like"))
    db.flush()
    mutual = db.get(Reaction, (target_id, viewer.id))
    if mutual is None or mutual.kind != "like":
        db.commit()
        return Outcome.LIKED
    low, high = ordered(viewer.id, target_id)
    match = Match(user_a=low, user_b=high)
    db.add(match)
    db.commit()
    contact.gateway.on_match(match.id)
    return Outcome.MATCHED


def matches_of(db: Session, user: User) -> list[tuple[Match, User]]:
    other = User.id == func.coalesce(
        func.nullif(Match.user_a, user.id), func.nullif(Match.user_b, user.id)
    )
    query = (
        select(Match, User)
        .join(User, other)
        .where(or_(Match.user_a == user.id, Match.user_b == user.id))
        .order_by(Match.created_at.desc())
    )
    return [(match, partner) for match, partner in db.execute(query).all()]


def remove_match(db: Session, user: User, match_id: uuid.UUID) -> bool:
    match = db.get(Match, match_id)
    if match is None or user.id not in (match.user_a, match.user_b):
        return False
    other = match.user_b if match.user_a == user.id else match.user_a
    _lock_pair(db, user.id, other)
    db.delete(match)
    # Removing a match blocks both ways (section 8).
    _set_block(db, user.id, other)
    _set_block(db, other, user.id)
    db.commit()
    return True
