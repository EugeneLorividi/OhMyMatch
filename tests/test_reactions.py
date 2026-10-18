import re
import threading
import uuid

import pytest
from sqlalchemy import func, select

from app import contact
from app.categories import CATEGORIES, CATEGORY_KEYS
from app.db.session import get_sessionmaker
from app.matching.feed import build_feed
from app.models import Match, Reaction, User
from app.reactions import Outcome, Unavailable, react, remove_match
from tests.helpers import post, register, score_form, uk
from tests.test_feed import add_user


@pytest.fixture
def calls(monkeypatch):
    seen: list[uuid.UUID] = []

    class Recorder(contact.ContactGateway):
        def on_match(self, match_id):
            seen.append(match_id)

    monkeypatch.setattr(contact, "gateway", Recorder())
    return seen


def pair(db):
    him = add_user(db, gender="man", seeking=("woman",), dominant=90)
    her = add_user(db, gender="woman", seeking=("man",), submissive=85)
    return him, her


def feed_handles(db, user):
    db.expire_all()
    return [card.handle for card in build_feed(db, user, 1).cards]


def reaction(db, a, b):
    db.expire_all()
    found = db.get(Reaction, (a.id, b.id))
    return found.kind if found else None


def match_count(db):
    return db.scalar(select(func.count()).select_from(Match))


def test_mutual_like_makes_one_match(db, calls):
    him, her = pair(db)
    assert react(db, him, her.id, "like") is Outcome.LIKED
    assert match_count(db) == 0
    assert calls == []
    assert react(db, her, him.id, "like") is Outcome.MATCHED
    match = db.scalars(select(Match)).one()
    assert (match.user_a, match.user_b) == tuple(sorted([him.id, her.id]))
    assert calls == [match.id]


def test_like_and_pass_hide_only_for_the_viewer(db):
    him, her = pair(db)
    assert feed_handles(db, him) == [her.handle]
    react(db, him, her.id, "like")
    assert feed_handles(db, him) == []
    assert feed_handles(db, her) == [him.handle]

    other = add_user(db, gender="woman", seeking=("man",), submissive=70)
    react(db, him, other.id, "pass")
    assert other.handle not in feed_handles(db, him)
    assert him.handle in feed_handles(db, other)


def test_block_hides_both_ways_and_removes_match(db):
    him, her = pair(db)
    react(db, him, her.id, "like")
    react(db, her, him.id, "like")
    assert match_count(db) == 1
    assert react(db, her, him.id, "block") is Outcome.BLOCKED
    assert match_count(db) == 0
    assert feed_handles(db, him) == []
    assert feed_handles(db, her) == []


def test_only_block_replaces_an_earlier_reaction(db):
    him, her = pair(db)
    react(db, him, her.id, "like")
    assert react(db, him, her.id, "pass") is Outcome.UNCHANGED
    assert reaction(db, him, her) == "like"

    react(db, her, him.id, "pass")
    assert react(db, her, him.id, "like") is Outcome.UNCHANGED
    assert reaction(db, her, him) == "pass"
    assert match_count(db) == 0

    assert react(db, him, her.id, "block") is Outcome.BLOCKED
    assert reaction(db, him, her) == "block"
    assert react(db, him, her.id, "like") is Outcome.UNCHANGED
    assert reaction(db, him, her) == "block"


def test_like_needs_feed_eligibility(db):
    him = add_user(db, gender="man", seeking=("woman",), dominant=90, dislikes=("pet",))
    pet = add_user(db, gender="woman", seeking=("man",), submissive=90, pet=80)
    wrong_gender = add_user(db, gender="man", seeking=("man",), submissive=90)
    no_overlap = add_user(db, gender="woman", seeking=("man",), dominant=90)
    for target in (pet, wrong_gender, no_overlap):
        with pytest.raises(Unavailable):
            react(db, him, target.id, "like")
    blocker = add_user(db, gender="woman", seeking=("man",), submissive=90)
    react(db, blocker, him.id, "block")
    with pytest.raises(Unavailable):
        react(db, him, blocker.id, "like")
    assert (
        db.scalar(select(func.count()).select_from(Reaction).where(Reaction.from_user == him.id))
        == 0
    )


def test_self_and_unknown_targets(db):
    him, _ = pair(db)
    for target in (him.id, uuid.uuid4()):
        for kind in ("like", "pass", "block"):
            with pytest.raises(Unavailable):
                react(db, him, target, kind)


def test_remove_match_blocks_both_sides(db):
    him, her = pair(db)
    react(db, him, her.id, "like")
    react(db, her, him.id, "like")
    match_id = db.scalars(select(Match.id)).one()
    stranger = add_user(db, gender="woman", seeking=("man",))
    assert not remove_match(db, stranger, match_id)
    assert remove_match(db, her, match_id)
    assert match_count(db) == 0
    assert reaction(db, him, her) == "block"
    assert reaction(db, her, him) == "block"
    assert not remove_match(db, her, match_id)


def test_simultaneous_likes_make_exactly_one_match(db, calls):
    him, her = pair(db)
    barrier = threading.Barrier(2)
    outcomes = []

    def like(from_id, to_id):
        with get_sessionmaker()() as session:
            viewer = session.get(User, from_id)
            barrier.wait()
            outcomes.append(react(session, viewer, to_id, "like"))

    threads = [
        threading.Thread(target=like, args=(him.id, her.id)),
        threading.Thread(target=like, args=(her.id, him.id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(o.value for o in outcomes) == ["liked", "matched"]
    assert match_count(db) == 1
    assert len(calls) == 1


# Routes


def logged_in_viewer(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    post(client, "/result/save", score_form({**dict.fromkeys(CATEGORY_KEYS, 0), "dominant": 90}))
    return db.scalars(select(User).where(User.is_active.is_(True))).one()


def test_feed_cards_have_reaction_buttons(client, db):
    logged_in_viewer(client, db)
    her = add_user(db, submissive=88, masochist=71)
    page = client.get("/feed").text
    assert f'name="target" value="{her.id}"' in page
    for key in ("feed.like", "feed.pass", "feed.block"):
        assert uk(key) in page
    for category in CATEGORIES:
        assert not re.search(rf"\b{re.escape(category.name)}\b", page, re.IGNORECASE)


def test_react_route_plain_and_htmx(client, db, calls):
    me = logged_in_viewer(client, db)
    her = add_user(db, submissive=88)
    response = post(
        client, "/react", {"target": str(her.id), "kind": "like"}, follow_redirects=False
    )
    assert response.status_code == 303 and response.headers["location"] == "/feed"
    react(db, her, me.id, "like")
    assert match_count(db) == 1

    other = add_user(db, submissive=70)
    fragment = post(
        client, "/react", {"target": str(other.id), "kind": "pass"}, headers={"HX-Request": "true"}
    )
    assert fragment.status_code == 200
    assert "<html" not in fragment.text
    assert uk("react.passed") in fragment.text


def test_mutual_like_through_routes_redirects_to_matches(client, db, calls):
    me = logged_in_viewer(client, db)
    her = add_user(db, submissive=88)
    react(db, her, me.id, "like")
    response = post(
        client, "/react", {"target": str(her.id), "kind": "like"}, follow_redirects=False
    )
    assert response.headers["location"] == "/matches"
    page = client.get("/matches")
    assert page.headers["cache-control"] == "no-store"
    assert her.handle in page.text
    assert uk("matches.contact_stub") in page.text
    assert "88" not in page.text and "%" not in page.text
    assert len(calls) == 1


def test_react_route_errors(client, db):
    logged_in_viewer(client, db)
    her = add_user(db, submissive=88)
    assert post(client, "/react", {"target": str(her.id), "kind": "love"}).status_code == 400
    assert post(client, "/react", {"target": "not-a-uuid", "kind": "like"}).status_code == 404
    assert post(client, "/react", {"target": str(uuid.uuid4()), "kind": "block"}).status_code == 404
    unavailable = post(
        client,
        "/react",
        {"target": str(uuid.uuid4()), "kind": "like"},
        headers={"HX-Request": "true"},
    )
    assert unavailable.status_code == 200
    assert uk("error.candidate_unavailable") in unavailable.text


def test_remove_match_route(client, db):
    me = logged_in_viewer(client, db)
    her = add_user(db, submissive=88)
    react(db, her, me.id, "like")
    react(db, me, her.id, "like")
    match_id = db.scalars(select(Match.id)).one()
    assert post(client, f"/matches/{uuid.uuid4()}/remove").status_code == 404
    response = post(client, f"/matches/{match_id}/remove", follow_redirects=False)
    assert response.status_code == 303
    assert match_count(db) == 0
    assert her.handle not in client.get("/matches").text
