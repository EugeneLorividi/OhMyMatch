from sqlalchemy import func, select

from app.auth import SESSION_COOKIE
from app.config import ACCOUNT_ACTIONS_PER_USER
from app.models import User, UserSession
from tests.helpers import PASSWORD, post, register, uk

NEW_PASSWORD = "a brand new password"


def test_account_page_requires_login(client):
    assert client.get("/account", follow_redirects=False).status_code == 303


def change(client, current, new=NEW_PASSWORD, confirm=None):
    data = {"current_password": current, "password": new, "password_confirm": confirm or new}
    return post(client, "/account/password", data)


def test_change_password_ends_all_other_sessions(client, db):
    handle, _, _ = register(client, db)
    other = post(client, "/login", {"handle": handle, "password": PASSWORD})
    assert other.status_code == 200
    assert db.scalar(select(func.count()).select_from(UserSession)) == 2

    assert change(client, "wrong password!").status_code == 400
    assert change(client, PASSWORD, "short").status_code == 400
    response = change(client, PASSWORD)
    assert response.status_code == 200
    assert uk("account.password_changed") in response.text
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(UserSession)) == 1
    assert handle in client.get("/").text  # this browser stays signed in

    client.cookies.clear()
    assert (
        post(
            client, "/login", {"handle": handle, "password": PASSWORD}, follow_redirects=False
        ).status_code
        == 400
    )
    assert (
        post(
            client, "/login", {"handle": handle, "password": NEW_PASSWORD}, follow_redirects=False
        ).status_code
        == 303
    )


def test_delete_needs_password_and_removes_everything(client, db):
    handle, _, _ = register(client, db)
    wrong = post(client, "/account/delete", {"password": "wrong password!"})
    assert wrong.status_code == 400
    assert uk("error.wrong_password") in wrong.text
    assert db.scalar(select(func.count()).select_from(User)) == 1

    response = post(client, "/account/delete", {"password": PASSWORD})
    assert response.status_code == 200
    assert uk("account.deleted_text") in response.text
    assert any(
        value.startswith(f"{SESSION_COOKIE}=") and "max-age=0" in value.lower()
        for value in response.headers.get_list("set-cookie")
    )
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(UserSession)) == 0
    assert client.get("/profile", follow_redirects=False).status_code == 303
    client.cookies.clear()
    assert (
        post(
            client, "/login", {"handle": handle, "password": PASSWORD}, follow_redirects=False
        ).status_code
        == 400
    )


def test_account_actions_are_limited(client, db):
    register(client, db)
    for _ in range(ACCOUNT_ACTIONS_PER_USER.limit):
        assert post(client, "/account/delete", {"password": "wrong password!"}).status_code == 400
    assert post(client, "/account/delete", {"password": PASSWORD}).status_code == 429
    assert db.scalar(select(func.count()).select_from(User)) == 1
