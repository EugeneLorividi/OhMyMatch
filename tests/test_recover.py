from sqlalchemy import select

from app.models import UserSession
from tests.helpers import PASSWORD, post, recovery_code_from, register, uk

NEW_PASSWORD = "another long password"


def recover(client, handle, code, password=NEW_PASSWORD):
    data = {
        "handle": handle,
        "recovery_code": code,
        "password": password,
        "password_confirm": password,
    }
    return post(client, "/recover", data)


def login_status(client, handle, password):
    data = {"handle": handle, "password": password}
    return post(client, "/login", data, follow_redirects=False).status_code


def test_recovery_resets_password_code_and_sessions(client, db):
    handle, code, _ = register(client, db)
    old_session = db.scalars(select(UserSession)).one().id
    client.cookies.clear()

    response = recover(client, handle, code.lower())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    new_code = recovery_code_from(response.text)
    assert new_code != code

    db.expire_all()
    sessions = db.scalars(select(UserSession)).all()
    assert old_session not in {s.id for s in sessions}
    assert len(sessions) == 1

    client.cookies.clear()
    assert login_status(client, handle, PASSWORD) == 400
    assert login_status(client, handle, NEW_PASSWORD) == 303

    client.cookies.clear()
    assert recover(client, handle, code).status_code == 400
    assert recover(client, handle, new_code, "third long password").status_code == 200


def test_wrong_code_and_unknown_handle_look_the_same(client, db):
    handle, _, _ = register(client, db)
    client.cookies.clear()
    wrong = recover(client, handle, "AAAA-BBBB-CCCC-DDDD")
    unknown = recover(client, "brave-fox-11", "AAAA-BBBB-CCCC-DDDD")
    assert wrong.status_code == unknown.status_code == 400
    assert uk("error.invalid_recovery") in wrong.text
    assert uk("error.invalid_recovery") in unknown.text
