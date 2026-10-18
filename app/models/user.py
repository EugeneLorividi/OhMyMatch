import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("mode IN ('normal', 'experimental')", name="mode"),
        Index("ix_users_is_active_gender", "is_active", "gender"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    recovery_code_hash: Mapped[str] = mapped_column(String(255))
    # Profile fields are filled in on the profile page, so they start empty.
    gender: Mapped[str | None] = mapped_column(String(32))
    seeking: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    mode: Mapped[str] = mapped_column(String(16), default="normal", server_default=text("'normal'"))
    # Reserved for the "by point" search mode; no logic yet.
    focus: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    consent_version: Mapped[str] = mapped_column(String(32))
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    age_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
