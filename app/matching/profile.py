import uuid
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """Everything matching needs about one person. Never sent to other users."""

    id: uuid.UUID
    gender: str
    seeking: frozenset[str]
    mode: str
    scores: Mapping[str, int]
    dislikes: frozenset[str] = frozenset()
