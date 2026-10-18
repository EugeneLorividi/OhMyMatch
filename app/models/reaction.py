import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

KINDS = ("like", "pass", "block")


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (
        CheckConstraint("kind IN ('like', 'pass', 'block')", name="kind"),
        CheckConstraint("from_user <> to_user", name="not_self"),
    )

    from_user: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    to_user: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
