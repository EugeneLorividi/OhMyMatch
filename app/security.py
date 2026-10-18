import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# No 0/O, 1/I/L, U: codes are typed by hand.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
CODE_GROUPS = 4
CODE_GROUP_LENGTH = 4

_hasher = PasswordHasher()
# Used to spend the same time on unknown handles as on wrong passwords.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_secret(value: str) -> str:
    return _hasher.hash(value)


def verify_secret(stored_hash: str | None, value: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, value) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def generate_code() -> str:
    groups = (
        "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_GROUP_LENGTH))
        for _ in range(CODE_GROUPS)
    )
    return "-".join(groups)


def normalize_code(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isascii() and ch.isalnum())


def hash_invite_code(code: str) -> str:
    # Invite codes are high-entropy and looked up by hash, so a fast hash is enough.
    return hashlib.sha256(normalize_code(code).encode()).hexdigest()
