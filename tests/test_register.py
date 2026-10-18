from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth import SESSION_COOKIE
from app.config import CONSENT_VERSION
from app.models import Invite, User, UserSession
from app.security import normalize_code, verify_secret
from tests.helpers import PASSWORD, handle_from, make_invite, post, register


def details(code, handle, **overrides):
    data = {
        "step": "details",
        "invite_code": code,
        "handle": handle,
        "age_confirmed": "yes",
        "consent": "yes",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }
    data.update(overrides)
    return data


def test_full_registration(client, db):
    handle, recovery_code, response = register(client, db)
    assert response.headers["cache-control"] == "no-store"
    assert handle in response.text

    user = db.scalars(select(User)).one()
    assert user.handle == handle
    assert user.consent_version == CONSENT_VERSION
    assert user.consent_at is not None
    assert user.age_confirmed_at is not None
    assert user.is_active is False
    assert user.gender is None
    assert user.mode == "normal"
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert recovery_code not in user.recovery_code_hash
    assert verify_secret(user.recovery_code_hash, normalize_code(recovery_code))

    invite = db.scalars(select(Invite)).one()
    assert invite.used_by == user.id
    assert invite.used_at is not None

    assert db.scalars(select(UserSession)).one().user_id == user.id
    assert handle in client.get("/").text


def test_session_cookie_flags(client, db):
    _, _, response = register(client, db)
    cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(SESSION_COOKIE)
    )
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered
    assert "max-age=" in lowered


def test_invalid_code(client):
    response = post(client, "/register", {"step": "code", "invite_code": "AAAA-BBBB-CCCC-DDDD"})
    assert response.status_code == 400
    assert "Код недействителен" in response.text


def test_code_is_case_and_dash_insensitive(client, db):
    code = make_invite(db)
    sloppy = " " + code.lower().replace("-", " ") + " "
    response = post(client, "/register", {"step": "code", "invite_code": sloppy})
    assert response.status_code == 200
    assert 'name="handle"' in response.text


def test_expired_code(client, db):
    code = make_invite(db)
    invite = db.scalars(select(Invite)).one()
    invite.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    response = post(client, "/register", {"step": "code", "invite_code": code})
    assert response.status_code == 400


def test_code_cannot_be_reused(client, db):
    code = make_invite(db)
    handle = handle_from(post(client, "/register", {"step": "code", "invite_code": code}).text)
    assert post(client, "/register", details(code, handle)).status_code == 200
    client.cookies.clear()
    response = post(client, "/register", {"step": "code", "invite_code": code})
    assert response.status_code == 400
    response = post(client, "/register", details(code, "brave-fox-11"))
    assert response.status_code == 400
    assert db.scalars(select(User)).all().__len__() == 1


def test_regenerate_handle(client, db):
    code = make_invite(db)
    handles = {
        handle_from(post(client, "/register", {"step": "regen", "invite_code": code}).text)
        for _ in range(10)
    }
    assert len(handles) > 1


def test_requires_age_and_consent(client, db):
    code = make_invite(db)
    for missing in ("age_confirmed", "consent"):
        response = post(client, "/register", details(code, "brave-fox-11", **{missing: ""}))
        assert response.status_code == 400
    assert db.scalars(select(User)).first() is None


def test_rejects_free_text_handle(client, db):
    code = make_invite(db)
    response = post(client, "/register", details(code, "anna-smith-1990"))
    assert response.status_code == 400
    assert "Выбери ник из предложенных" in response.text
    assert db.scalars(select(User)).first() is None


def test_password_rules(client, db):
    code = make_invite(db)
    for password, confirm in [("short", "short"), (PASSWORD, PASSWORD + "x"), ("x" * 129,) * 2]:
        data = details(code, "brave-fox-11", password=password, password_confirm=confirm)
        assert post(client, "/register", data).status_code == 400
    assert db.scalars(select(User)).first() is None


def test_taken_handle_offers_another(client, db):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    code = make_invite(db)
    response = post(client, "/register", details(code, handle))
    assert response.status_code == 409
    assert handle_from(response.text) != handle
    assert db.scalars(select(Invite).where(Invite.used_at.is_(None))).one()


def test_logged_in_user_is_redirected_from_register(client, db):
    register(client, db)
    response = client.get("/register", follow_redirects=False)
    assert response.status_code == 303
