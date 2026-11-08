import logging

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text

from app import contact
from app.categories import CATEGORY_KEYS
from app.config import Settings
from app.contact import ContactGateway
from app.contact.username import normalize
from app.eventlog import logger
from app.main import app
from app.models import ContactShare, Match, TelegramContact, User
from app.reactions import react, remove_match
from tests.helpers import post, register, score_form, uk, without_random_values

ALICE = "alice_tg"
BOB = "bob_on_tg"


def member(client, db, gender, seeking, **scores) -> User:
    """A registered, active member signed in on `client`."""
    handle, _ = register(client, db)
    post(client, "/profile", {"gender": gender, "seeking": [seeking], "mode": "normal"})
    values = {**dict.fromkeys(CATEGORY_KEYS, 40), **scores}
    post(client, "/result/save", score_form(values))
    return db.scalars(select(User).where(User.handle == handle)).one()


@pytest.fixture
def pair(client, db):
    """Two signed-in members (alice on `client`, bob on `other`) who have matched."""
    alice = member(client, db, "man", "woman", dominant=90)
    with TestClient(app, base_url="https://testserver") as other:
        bob = member(other, db, "woman", "man", submissive=85)
        react(db, bob, alice.id, "like")
        react(db, alice, bob.id, "like")
        match = db.scalars(select(Match)).one()
        yield alice, bob, match, other


def save_at(client, name: str, ack: str = "yes"):
    return post(client, "/account/contact", {"username": name, "ack": ack})


def press(client, match_id):
    return post(client, f"/matches/{match_id}/contact", {"confirm": "yes"}, follow_redirects=False)


def page_texts(client, pair_handles, match_id) -> dict[str, str]:
    """Every page a member can open that could carry contact data."""
    paths = [
        "/",
        "/feed",
        "/matches",
        "/account",
        "/profile",
        "/privacy",
        f"/matches/{match_id}/contact",
    ]
    texts = {}
    for path in paths:
        response = client.get(path)
        texts[path] = without_random_values(response.text, client, *pair_handles)
    return texts


# Username format


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("alice_tg", "alice_tg"),
        ("@Alice_TG", "alice_tg"),
        ("  @abcde  ", "abcde"),
        ("alice_tg\n", "alice_tg"),  # surrounding whitespace is dropped
        ("a" + "b" * 30 + "c", "a" + "b" * 30 + "c"),
        ("a1b2c3", "a1b2c3"),
    ],
)
def test_valid_usernames(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "@",
        "abcd",  # too short
        "a" * 33,  # too long
        "1abcde",  # starts with a digit
        "_abcde",
        "abcde_",  # ends with an underscore
        "ab__cde",  # two underscores in a row
        "ab-cde",
        "ab cde",
        "@@abcde",
        "аліса_tg",  # Cyrillic
        "alice​_tg",  # zero-width space
        "https://t.me/alice_tg",
        '"><script>alert(1)</script>',
        "javascript:alert(1)",
        "a" * 5000,
    ],
)
def test_invalid_usernames(raw):
    assert normalize(raw) is None


def test_contact_key_must_be_a_fernet_key(monkeypatch):
    monkeypatch.setenv("CONTACT_KEY", "not-a-key")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "not-a-key" not in str(caught.value)
    monkeypatch.setenv("CONTACT_KEY", "")
    assert Settings().contact_key == ""
    monkeypatch.setenv("CONTACT_KEY", Fernet.generate_key().decode())
    assert Settings().contact_key


# Storage


def test_only_ciphertext_is_stored(client, db):
    user = member(client, db, "man", "woman")
    save_at(client, f"@{ALICE}")
    token = db.scalars(select(TelegramContact.username_enc)).one()
    assert ALICE.encode() not in token
    # Nothing in any text column or in the table dump mentions the plain value.
    dump = db.execute(text("SELECT t::text FROM telegram_contacts t")).scalars().all()
    assert ALICE not in "".join(dump)
    assert contact.gateway.own_username(db, user.id) == ALICE


def test_ciphertext_copied_to_another_row_is_useless(client, db):
    alice = member(client, db, "man", "woman")
    save_at(client, ALICE)
    with TestClient(app, base_url="https://testserver") as other:
        bob = member(other, db, "woman", "man")
    token = db.scalars(select(TelegramContact.username_enc)).one()
    db.add(TelegramContact(user_id=bob.id, username_enc=token))
    db.commit()
    assert contact.gateway.own_username(db, alice.id) == ALICE
    assert contact.gateway.own_username(db, bob.id) is None


def test_a_different_key_reads_nothing(client, db):
    user = member(client, db, "man", "woman")
    save_at(client, ALICE)
    stranger = ContactGateway(Fernet.generate_key().decode())
    assert stranger.own_username(db, user.id) is None


# Settings form


def test_settings_save_normalizes_and_requires_ack(client, db):
    user = member(client, db, "man", "woman")
    page = client.get("/account")
    assert 'name="username"' in page.text and 'name="ack"' in page.text
    refused = save_at(client, "@Alice_TG", ack="")
    assert refused.status_code == 400
    assert uk("error.contact_ack") in refused.text
    assert contact.gateway.own_username(db, user.id) is None
    saved = save_at(client, "@Alice_TG")
    assert saved.status_code == 200
    assert uk("account.contact_saved") in saved.text
    assert 'value="@alice_tg"' in saved.text
    assert contact.gateway.own_username(db, user.id) == "alice_tg"


def test_settings_reject_bad_input_without_echoing_it(client, db):
    user = member(client, db, "man", "woman")
    for bad in ('"><script>alert(1)</script>', "zq9", "тест_нік"):
        response = save_at(client, bad)
        assert response.status_code == 400
        assert uk("error.contact_username") in response.text
        assert bad not in response.text
    assert contact.gateway.own_username(db, user.id) is None


def test_empty_value_removes_the_username(client, db):
    user = member(client, db, "man", "woman")
    save_at(client, ALICE)
    removed = save_at(client, "  ", ack="")
    assert removed.status_code == 200
    assert uk("account.contact_removed") in removed.text
    assert contact.gateway.own_username(db, user.id) is None
    assert db.scalar(select(func.count()).select_from(TelegramContact)) == 0


def test_saving_needs_a_session_and_csrf(client, db):
    assert client.post("/account/contact", data={"username": ALICE}).status_code == 403
    client.get("/login")
    response = post(
        client, "/account/contact", {"username": ALICE, "ack": "yes"}, follow_redirects=False
    )
    assert response.status_code == 303 and response.headers["location"] == "/login"


# Sharing


def test_warning_page_and_confirmation_are_required(client, db, pair):
    alice, _, match, _ = pair
    needs = client.get(f"/matches/{match.id}/contact")
    assert needs.status_code == 400 and uk("error.contact_needs_username") in needs.text
    assert press(client, match.id).status_code == 400  # no @ yet, no confirm either
    save_at(client, ALICE)
    warning = client.get(f"/matches/{match.id}/contact")
    assert warning.status_code == 200 and warning.headers["cache-control"] == "no-store"
    for key in ("contact.confirm_irreversible", "contact.confirm_unverified"):
        assert uk(key) in warning.text
    assert f"@{ALICE}" in warning.text
    no_confirm = post(client, f"/matches/{match.id}/contact", {})
    assert no_confirm.status_code == 400 and uk("error.contact_confirm") in no_confirm.text
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 0
    assert press(client, match.id).status_code == 303


def test_nothing_is_shown_until_both_pressed(client, db, pair):
    alice, bob, match, other = pair
    handles = (alice.handle, bob.handle)
    save_at(client, ALICE)
    save_at(other, BOB)

    def assert_no_leak(alice_pages, bob_pages):
        # Each @ appears only in its own owner's pages, never in the other person's.
        assert BOB not in "".join(alice_pages.values())
        assert ALICE not in "".join(bob_pages.values())

    baseline_alice = page_texts(client, handles, match.id)
    baseline_bob = page_texts(other, handles, match.id)
    assert_no_leak(baseline_alice, baseline_bob)

    # Alice presses. Bob must see exactly what he saw before: not the @, not the press.
    assert press(client, match.id).status_code == 303
    after_alice = page_texts(client, handles, match.id)
    after_bob = page_texts(other, handles, match.id)
    assert_no_leak(after_alice, after_bob)
    assert after_bob == baseline_bob
    assert uk("matches.contact_waiting") in after_alice["/matches"]
    assert uk("matches.contact_waiting") not in after_bob["/matches"]

    # Bob presses: now both see both.
    assert press(other, match.id).status_code == 303
    for who, mine, theirs in ((client, ALICE, BOB), (other, BOB, ALICE)):
        html = who.get("/matches").text
        assert f'href="https://t.me/{theirs}"' in html
        assert f"@{theirs}</a>" in html
        assert f"@{mine}" in html


def test_t_me_link_opens_safely(client, db, pair):
    _, _, match, other = pair
    save_at(client, ALICE)
    save_at(other, BOB)
    press(client, match.id)
    press(other, match.id)
    html = client.get("/matches").text
    link = f'<a href="https://t.me/{BOB}" target="_blank" rel="noopener noreferrer">@{BOB}</a>'
    assert link in html


def test_only_a_match_member_can_press(client, db, pair):
    _, _, match, _ = pair
    with TestClient(app, base_url="https://testserver") as outsider:
        member(outsider, db, "man", "woman")
        save_at(outsider, "outsider_tg")
        assert press(outsider, match.id).status_code == 404
        assert outsider.get(f"/matches/{match.id}/contact").status_code == 404
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 0


def test_pressing_twice_changes_nothing(client, db, pair):
    _, _, match, _ = pair
    save_at(client, ALICE)
    press(client, match.id)
    press(client, match.id)
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 1


def test_changing_or_removing_the_username_cancels_presses(client, db, pair):
    alice, bob, match, other = pair
    save_at(client, ALICE)
    save_at(other, BOB)
    press(client, match.id)
    save_at(client, "alice_new")
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 0
    # Bob presses now; the new @ must not be revealed because Alice's old press is gone.
    press(other, match.id)
    assert "alice_new" not in other.get("/matches").text
    assert uk("matches.contact_waiting") in other.get("/matches").text
    # Same value again keeps presses.
    press(client, match.id)
    save_at(client, "Alice_New")
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 2
    save_at(client, "", ack="")
    assert db.scalars(select(ContactShare.user_id)).all() == [bob.id]
    assert "alice_new" not in other.get("/matches").text


def test_removing_the_match_removes_the_presses(client, db, pair):
    alice, _, match, other = pair
    save_at(client, ALICE)
    press(client, match.id)
    assert remove_match(db, alice, match.id)
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 0


# Account deletion


def test_deleting_the_account_leaves_no_rows(client, db, pair):
    alice, bob, match, other = pair
    alice_id, bob_id = alice.id, bob.id
    save_at(client, ALICE)
    save_at(other, BOB)
    press(client, match.id)
    press(other, match.id)
    response = post(client, "/account/delete", {"password": "correct horse battery"})
    assert response.status_code == 200
    db.expire_all()
    for table, column in ((TelegramContact, "user_id"), (ContactShare, "user_id")):
        count = db.scalar(
            select(func.count()).select_from(table).where(getattr(table, column) == alice_id)
        )
        assert count == 0, table.__tablename__
    # Bob's @ is still his own; the match and Alice's press are gone.
    assert db.scalar(select(func.count()).select_from(ContactShare)) == 0
    assert db.scalar(select(func.count()).select_from(Match)) == 0
    assert contact.gateway.own_username(db, bob_id) == BOB
    db.execute(delete(User).where(User.id == bob_id))
    db.commit()
    assert db.scalar(select(func.count()).select_from(TelegramContact)) == 0


# Switched off


def test_without_a_key_the_feature_is_off(client, db, pair, monkeypatch):
    _, _, match, _ = pair
    monkeypatch.setattr(contact, "gateway", ContactGateway(""))
    assert 'name="username"' not in client.get("/account").text
    assert client.get("/matches").status_code == 200
    assert "/contact" not in client.get("/matches").text
    assert save_at(client, ALICE).status_code == 404
    assert client.get(f"/matches/{match.id}/contact").status_code == 404
    assert press(client, match.id).status_code == 404


# Logs


def test_username_never_reaches_the_logs(client, db, pair):
    _, _, match, other = pair
    seen: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Collect()
    for target in (logger, logging.getLogger()):
        target.addHandler(handler)
    try:
        save_at(client, ALICE)
        save_at(client, "no")  # rejected
        save_at(other, BOB)
        press(client, match.id)
        press(other, match.id)
        client.get("/matches")
        save_at(client, "", ack="")
    finally:
        for target in (logger, logging.getLogger()):
            target.removeHandler(handler)
    events = [line.split()[0] for line in seen]
    assert events == [
        "event=contact_saved",
        "event=contact_saved",
        "event=contact_shared",
        "event=contact_mutual",
        "event=contact_cleared",
    ]
    assert ALICE not in "".join(seen) and BOB not in "".join(seen)
