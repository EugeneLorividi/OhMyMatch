"""Telegram @username: strict ASCII validation. The result is also the only thing ever put
into a t.me link, so anything that passes here is safe in a URL path and in HTML."""

import re

# 5-32 characters: Latin letters, digits and single underscores, starting with a letter and
# not ending with an underscore.
_USERNAME = re.compile(r"[a-z][a-z0-9_]{3,30}[a-z0-9]")
_RAW_MAX = 64  # anything longer is rejected before it is looked at


def normalize(raw: str) -> str | None:
    """The canonical form (lower case, no "@"), or None if this is not a valid username."""
    value = raw.strip()
    if len(value) > _RAW_MAX:
        return None
    value = value.removeprefix("@").lower()
    if "__" in value or not _USERNAME.fullmatch(value):
        return None
    return value
