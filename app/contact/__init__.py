"""Contact between matched people. Telegram arrives in a separate spec; the MVP does nothing."""

import uuid


class ContactGateway:
    def on_match(self, match_id: uuid.UUID) -> None:
        """Called once, after a new match is committed."""


gateway = ContactGateway()
