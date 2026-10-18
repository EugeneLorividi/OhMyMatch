from sqlalchemy import select

from app.models import Dislike, User
from app.parsing.text_parser import parse_text
from tests.helpers import full_result_text, post, register, score_form, uk


def profile(client, gender="woman", seeking=("man", "other"), mode="normal"):
    data = {"gender": gender, "seeking": list(seeking), "mode": mode}
    return post(client, "/profile", data, follow_redirects=False)


def test_pages_require_login(client):
    for path in ("/profile", "/result", "/dislikes"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_save_profile(client, db):
    register(client, db)
    assert profile(client).status_code == 303
    user = db.scalars(select(User)).one()
    assert user.gender == "woman"
    assert user.seeking == ["man", "other"]
    assert user.mode == "normal"
    assert user.is_active is False  # no scores yet

    page = client.get("/profile").text
    assert 'value="woman" required checked' in page

    assert profile(client, "man", ["woman"], "experimental").status_code == 303
    db.expire_all()
    user = db.scalars(select(User)).one()
    assert (user.gender, user.seeking, user.mode) == ("man", ["woman"], "experimental")


def test_profile_validation(client, db):
    register(client, db)
    assert profile(client, gender="robot").status_code == 400
    assert profile(client, seeking=()).status_code == 400
    assert profile(client, seeking=("man", "robot")).status_code == 400
    assert profile(client, mode="wild").status_code == 400
    user = db.scalars(select(User)).one()
    assert user.gender is None


def test_becomes_active_after_profile_and_scores(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    parsed = post(client, "/result/parse-text", {"text": full_result_text()})
    values = parse_text(full_result_text()).values
    assert parsed.status_code == 200
    post(client, "/result/save", score_form(values))
    db.expire_all()
    assert db.scalars(select(User)).one().is_active is True
    assert uk("index.active") in client.get("/").text


def test_dislikes(client, db):
    register(client, db)
    response = post(client, "/dislikes", {"category": ["brat", "pet"]}, follow_redirects=False)
    assert response.status_code == 303
    assert set(db.scalars(select(Dislike.category_key))) == {"brat", "pet"}
    assert 'value="brat" checked' in client.get("/dislikes").text

    post(client, "/dislikes", {"category": ["little"]})
    assert set(db.scalars(select(Dislike.category_key))) == {"little"}

    post(client, "/dislikes", {})
    assert list(db.scalars(select(Dislike.category_key))) == []


def test_dislikes_reject_unknown_key(client, db):
    register(client, db)
    post(client, "/dislikes", {"category": ["brat"]})
    response = post(client, "/dislikes", {"category": ["brat", "unicorn"]})
    assert response.status_code == 400
    assert set(db.scalars(select(Dislike.category_key))) == {"brat"}
