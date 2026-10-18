from sqlalchemy.orm import Session

from app.models import TestScore, User


def refresh_is_active(db: Session, user: User) -> None:
    """A user takes part in matching once the profile and all 25 scores are saved."""
    has_profile = bool(user.gender) and bool(user.seeking)
    has_scores = db.get(TestScore, user.id) is not None
    user.is_active = has_profile and has_scores
