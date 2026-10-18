from app.security import (
    CODE_ALPHABET,
    generate_code,
    hash_invite_code,
    hash_secret,
    normalize_code,
    verify_secret,
)


def test_code_format():
    code = generate_code()
    groups = code.split("-")
    assert [len(group) for group in groups] == [4, 4, 4, 4]
    assert set(code.replace("-", "")) <= set(CODE_ALPHABET)


def test_code_normalization():
    assert normalize_code(" abcd-efgh ") == "ABCDEFGH"
    assert hash_invite_code("abcd-efgh") == hash_invite_code("ABCD EFGH")


def test_secret_hash_is_argon2id_and_verifies():
    hashed = hash_secret("some secret value")
    assert hashed.startswith("$argon2id$")
    assert verify_secret(hashed, "some secret value")
    assert not verify_secret(hashed, "other value")
    assert not verify_secret(None, "some secret value")
    assert not verify_secret("not a hash", "some secret value")
