import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TestScore(Base):
    __tablename__ = "test_scores"
    __test__ = False  # not a pytest class
    __table_args__ = (
        CheckConstraint("jsonb_typeof(scores) = 'object'", name="scores_object"),
        # Every value is an integer in 0..100. The set of keys is validated in the app.
        CheckConstraint(
            "NOT jsonb_path_exists(scores, "
            "'$.* ? (@.type() != \"number\" || @ < 0 || @ > 100 || @ != @.floor())')",
            name="scores_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    scores: Mapped[dict[str, int]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
