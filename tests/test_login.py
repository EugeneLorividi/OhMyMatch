from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth import SESSION_COOKIE
from app.models import UserSession
from tests.helpers import PASSWORD, post, register


def login(client, handle, password=PASSWORD):
    return post(client, "/login", {"handle": handle, "password": password}, follow_redirects=False)


def test_login_and_logout(client, db):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    assert handle not in client.get("/").text

    response = login(client, handle.upper() + " ")
    assert response.status_code == 303
    assert handle in client.get("/").text
    assert len(db.scalars(select(UserSession)).all()) == 2

    response = post(client, "/logout", follow_redirects=False)
    assert response.status_code == 303
    assert handle not in client.get("/").text
    assert len(db.scalars(select(UserSession)).all()) == 1


def test_wrong_password_and_unknown_handle_look_the_same(client, db):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    wrong = login(client, handle, "wrong password!")
    unknown = login(client, "brave-fox-11")
    assert wrong.status_code == unknown.status_code == 400
    assert "Неверный ник или пароль" in wrong.text
    assert "Неверный ник или пароль" in unknown.text
    assert SESSION_COOKIE not in client.cookies


def test_session_token_is_not_stored(client, db):
    register(client, db)
    token = client.cookies[SESSION_COOKIE]
    stored = db.scalars(select(UserSession)).one()
    assert token not in str(stored.id)
    assert token.replace("-", "") not in stored.id.hex


def test_expired_session_is_rejected_and_deleted(client, db):
    handle, _, _ = register(client, db)
    stored = db.scalars(select(UserSession)).one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert handle not in client.get("/").text
    db.expire_all()
    assert db.scalars(select(UserSession)).first() is None


def test_forged_session_cookie_is_ignored(client, db):
    handle, _, _ = register(client, db)
    client.cookies.delete(SESSION_COOKIE)
    client.cookies.set(SESSION_COOKIE, "forged")
    assert client.cookies[SESSION_COOKIE] == "forged"
    assert handle not in client.get("/").text
