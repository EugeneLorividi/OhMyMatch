"""Section 11 integration path: invite, profile, result, feed, mutual like, match, deletion."""

import re

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.categories import CATEGORY_KEYS
from app.db.base import Base
from app.main import app
from tests.helpers import PASSWORD, full_result_text, post, register, score_form


def person(db, gender, seeking, **scores):
    client = TestClient(app, base_url="https://testserver")
    handle, _, _ = register(client, db)
    post(client, "/profile", {"gender": gender, "seeking": [seeking], "mode": "normal"})
    parsed = post(client, "/result/parse-text", {"text": full_result_text()})
    assert parsed.status_code == 200
    post(client, "/result/save", score_form({**dict.fromkeys(CATEGORY_KEYS, 5), **scores}))
    return client, handle


def target_on_feed(client):
    return re.search(r'name="target" value="([0-9a-f-]+)"', client.get("/feed").text).group(1)


def test_full_path_and_deletion(db):
    alice, alice_handle = person(db, "woman", "man", submissive=90, rope_bunny=80)
    bob, bob_handle = person(db, "man", "woman", dominant=85, rigger=75)

    assert bob_handle in alice.get("/feed").text
    assert alice_handle in bob.get("/feed").text
    post(alice, "/react", {"target": target_on_feed(alice), "kind": "like"})
    response = post(
        bob, "/react", {"target": target_on_feed(bob), "kind": "like"}, follow_redirects=False
    )
    assert response.headers["location"] == "/matches"
    assert alice_handle in bob.get("/matches").text
    assert bob_handle in alice.get("/matches").text

    assert post(alice, "/account/delete", {"password": PASSWORD}).status_code == 200
    assert alice_handle not in bob.get("/matches").text
    # Not a single row anywhere still mentions the deleted account.
    for table in Base.metadata.sorted_tables:
        text_columns = [c for c in table.c if c.type.python_type is str]
        for column in text_columns:
            count = db.scalar(select(func.count()).select_from(table).where(column == alice_handle))
            assert count == 0, (table.name, column.name)
