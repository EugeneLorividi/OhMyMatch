import re

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.categories import CATEGORY_KEYS
from app.config import PASTE_MAX_CHARS
from app.models import TestScore, User
from app.parsing.text_parser import parse_text
from tests.helpers import full_result_text, post, register, score_form

ALL_FIFTY = dict.fromkeys(CATEGORY_KEYS, 50)


def test_parse_text_fills_form_and_stores_nothing(client, db):
    register(client, db)
    paste = full_result_text({"rigger": 92}) + "\nprivate note that must not come back"
    response = post(client, "/result/parse-text", {"text": paste})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'name="score_rigger" type="number"' in response.text
    assert 'value="92"' in response.text
    assert "Найдено 25 из 25" in response.text
    assert "private note" not in response.text
    assert "bdsmtest.org/r/synthetic" not in response.text
    assert db.scalars(select(TestScore)).first() is None


def test_parse_text_highlights_missing_and_errors(client, db):
    register(client, db)
    response = post(client, "/result/parse-text", {"text": "92% Rigger\n120% Switch\n5% Unicorn"})
    assert response.status_code == 200
    assert "Найдено 1 из 25" in response.text
    assert "вне диапазона" in response.text
    assert "неизвестная категория «Unicorn»" in response.text
    assert response.text.count("score flagged") == 24


def test_parse_text_limits(client, db):
    register(client, db)
    assert post(client, "/result/parse-text", {"text": "  "}).status_code == 400
    too_long = "x" * (PASTE_MAX_CHARS + 1)
    assert post(client, "/result/parse-text", {"text": too_long}).status_code == 400


def test_save_and_resave(client, db):
    register(client, db)
    values = parse_text(full_result_text()).values
    response = post(client, "/result/save", score_form(values), follow_redirects=False)
    assert response.status_code == 303
    saved = db.scalars(select(TestScore)).one()
    assert saved.scores == values
    assert saved.user_id == db.scalars(select(User.id)).one()

    page = client.get("/result")
    assert page.headers["cache-control"] == "no-store"
    assert re.search(r'name="score_rigger"[^>]*value="8"', page.text)

    post(client, "/result/save", score_form(ALL_FIFTY))
    db.expire_all()
    assert db.scalars(select(TestScore)).one().scores == ALL_FIFTY


@pytest.mark.parametrize("bad", ["", "-1", "101", "50.5", "abc", "٥٠"])
def test_save_rejects_bad_values(client, db, bad):
    register(client, db)
    response = post(client, "/result/save", score_form({**ALL_FIFTY, "rigger": bad}))
    assert response.status_code == 400
    assert response.text.count("score flagged") == 1
    assert db.scalars(select(TestScore)).first() is None


def test_save_rejects_missing_field(client, db):
    register(client, db)
    values = {k: v for k, v in ALL_FIFTY.items() if k != "little"}
    assert post(client, "/result/save", score_form(values)).status_code == 400


def test_save_ignores_extra_fields(client, db):
    register(client, db)
    data = {**score_form(ALL_FIFTY), "score_unicorn": "77"}
    post(client, "/result/save", data)
    assert set(db.scalars(select(TestScore)).one().scores) == set(CATEGORY_KEYS)


@pytest.mark.parametrize(
    "scores", ['{"switch": 101}', '{"switch": -1}', '{"switch": 1.5}', '{"switch": "5"}', "[1]"]
)
def test_db_check_constraint(client, db, scores):
    register(client, db)
    user_id = db.scalars(select(User.id)).one()
    with pytest.raises(IntegrityError):
        db.execute(
            text("INSERT INTO test_scores (user_id, scores) VALUES (:id, CAST(:s AS jsonb))"),
            {"id": user_id, "s": scores},
        )
    db.rollback()
