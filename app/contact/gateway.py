import uuid
from dataclasses import dataclass
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.contact.username import normalize
from app.models import ContactShare, Match, TelegramContact


class ContactDisabled(Exception):
    """CONTACT_KEY is not set, so the contact feature is switched off."""


class NoUsername(Exception):
    """The member has no @username saved, so there is nothing to share."""


class MatchNotFound(Exception):
    """Missing match, or one the member is not part of. Same answer for both."""


@dataclass(frozen=True)
class ContactView:
    """What one member may see about contact on one match card.

    "none": the member has not pressed. "waiting": only the member pressed. "mutual": both
    pressed, and only then `theirs` holds the other person's @. Whether the other person
    pressed first is never visible in the other two states.
    """

    status: Literal["none", "waiting", "mutual"] = "none"
    mine: str | None = None
    theirs: str | None = None


class ContactGateway:
    def __init__(self, key: str | None = None) -> None:
        key = settings.contact_key if key is None else key
        self._fernet = Fernet(key) if key else None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def on_match(self, match_id: uuid.UUID) -> None:
        """Called once, after a new match is committed. Nothing to do: sharing is the
        members' choice, and no notification is sent."""

    # Encryption. The user id is part of the plaintext, so a token copied from another row
    # does not decrypt for this user.

    def _encrypt(self, user_id: uuid.UUID, username: str) -> bytes:
        if self._fernet is None:
            raise ContactDisabled
        return self._fernet.encrypt(f"{user_id.hex}:{username}".encode("ascii"))

    def _decrypt(self, user_id: uuid.UUID, token: bytes) -> str | None:
        if self._fernet is None:
            return None
        try:
            owner, _, username = self._fernet.decrypt(token).decode("ascii").partition(":")
        except (InvalidToken, UnicodeDecodeError):
            return None
        if owner != user_id.hex or normalize(username) != username:
            return None
        return username

    def _saved(self, db: Session, user_id: uuid.UUID) -> str | None:
        token = db.scalar(
            select(TelegramContact.username_enc).where(TelegramContact.user_id == user_id)
        )
        return None if token is None else self._decrypt(user_id, token)

    @staticmethod
    def _lock(db: Session, user_id: uuid.UUID) -> None:
        """Row lock on the member's contact row: saving the @ and pressing "share" for the
        same member cannot interleave."""
        db.execute(
            select(TelegramContact.user_id)
            .where(TelegramContact.user_id == user_id)
            .with_for_update()
        ).all()

    def own_username(self, db: Session, user_id: uuid.UUID) -> str | None:
        return self._saved(db, user_id) if self.enabled else None

    def save_username(self, db: Session, user_id: uuid.UUID, username: str | None) -> None:
        """Stores, replaces or (with None) removes the @. `username` must be normalized.

        A changed or removed @ also drops the member's "share contact" presses: they were
        given for the old one, and must not reveal a new one."""
        if not self.enabled:
            raise ContactDisabled
        self._lock(db, user_id)
        if username == self._saved(db, user_id):
            db.rollback()
            return
        if username is None:
            db.execute(delete(TelegramContact).where(TelegramContact.user_id == user_id))
        else:
            token = self._encrypt(user_id, username)
            statement = insert(TelegramContact).values(user_id=user_id, username_enc=token)
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=[TelegramContact.user_id],
                    set_={"username_enc": token, "updated_at": statement.excluded.updated_at},
                )
            )
        db.execute(delete(ContactShare).where(ContactShare.user_id == user_id))
        db.commit()

    def share(self, db: Session, user_id: uuid.UUID, match_id: uuid.UUID) -> bool:
        """Records the member's consent for this match. Returns True if the other person had
        already agreed, so the two @ are visible now. Cannot be undone."""
        if not self.enabled:
            raise ContactDisabled
        match = db.get(Match, match_id)
        if match is None or user_id not in (match.user_a, match.user_b):
            raise MatchNotFound
        self._lock(db, user_id)
        if self._saved(db, user_id) is None:
            db.rollback()
            raise NoUsername
        try:
            db.execute(
                insert(ContactShare)
                .values(match_id=match_id, user_id=user_id)
                .on_conflict_do_nothing()
            )
            db.commit()
        except IntegrityError:  # the match was removed in the meantime
            db.rollback()
            raise MatchNotFound from None
        return self.views(db, user_id, [match])[match_id].status == "mutual"

    def views(
        self, db: Session, user_id: uuid.UUID, matches: list[Match]
    ) -> dict[uuid.UUID, ContactView]:
        """Contact state per match, as seen by `user_id`."""
        if not self.enabled or not matches:
            return {}
        mine = self._saved(db, user_id)
        pressed = db.execute(
            select(ContactShare.match_id, ContactShare.user_id).where(
                ContactShare.match_id.in_([match.id for match in matches])
            )
        ).all()
        by_match: dict[uuid.UUID, set[uuid.UUID]] = {}
        for match_id, presser in pressed:
            by_match.setdefault(match_id, set()).add(presser)
        result: dict[uuid.UUID, ContactView] = {}
        for match in matches:
            other = match.user_b if match.user_a == user_id else match.user_a
            pressers = by_match.get(match.id, set())
            if user_id not in pressers:
                result[match.id] = ContactView()
            elif other not in pressers:
                result[match.id] = ContactView("waiting", mine=mine)
            else:
                theirs = self._saved(db, other)
                # Both pressed but one @ cannot be read (key changed): show nothing.
                status = "mutual" if mine and theirs else "waiting"
                result[match.id] = ContactView(
                    status, mine=mine, theirs=theirs if status == "mutual" else None
                )
        return result


gateway = ContactGateway()
