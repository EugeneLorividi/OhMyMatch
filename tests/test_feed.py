import re
import time
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import insert, select

from app.categories import CATEGORIES, CATEGORY_KEYS
from app.config import FEED_PAGE_SIZE
from app.handles import generate_handle
from app.matching.feed import build_feed
from app.models import Dislike, TestScore, User
from tests.helpers import post, register, score_form, uk, without_random_values

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def add_user(
    db, gender="woman", seeking=("man",), mode="normal", dislikes=(), active=True, **scores
):
    values = dict.fromkeys(CATEGORY_KEYS, 0)
    values.update({k.replace("_", "-"): v for k, v in scores.items()})
    user = User(
        handle=f"{generate_handle()}-{uuid.uuid4().hex[:6]}",
        password_hash="x",
        recovery_code_hash="x",
        gender=gender,
        seeking=list(seeking),
        mode=mode,
        is_active=active,
        consent_version="test",
        consent_at=NOW,
        age_confirmed_at=NOW,
    )
    db.add(user)
    db.flush()
    db.add(TestScore(user_id=user.id, scores=values))
    db.add_all(Dislike(user_id=user.id, category_key=key) for key in dislikes)
    db.commit()
    return user


def viewer(db, **kwargs):
    kwargs.setdefault("gender", "man")
    kwargs.setdefault("seeking", ("woman",))
    kwargs.setdefault("dominant", 90)
    return add_user(db, **kwargs)


def handles(feed_page):
    return [card.handle for card in feed_page.cards]


def test_inactive_viewer_gets_no_feed(db):
    me = viewer(db, active=False)
    assert build_feed(db, me, 1) is None


def test_feed_applies_filters_and_ranks(db):
    me = viewer(db, sadist=70, dislikes=("pet",))
    best = add_user(db, submissive=95, masochist=90)
    good = add_user(db, submissive=70)
    add_user(db, submissive=95, seeking=("woman",))  # does not seek men
    add_user(db, gender="man", seeking=("man",), submissive=95)  # wrong gender
    add_user(db, submissive=95, pet=80)  # in viewer's "no" list
    add_user(db, submissive=95, active=False)
    add_user(db, dominant=95)  # no working direction
    add_user(db, submissive=95, dislikes=("dominant",))  # candidate says no to the viewer
    feed = build_feed(db, me, 1)
    assert handles(feed) == [best.handle, good.handle]
    assert feed.cards[0].matched == ("power", "pain")
    assert not feed.has_next


def test_feed_is_mutual(db):
    a = viewer(db)
    b = add_user(db, submissive=80)
    assert handles(build_feed(db, a, 1)) == [b.handle]
    assert handles(build_feed(db, b, 1)) == [a.handle]


def test_paging_and_stable_daily_ties(db):
    me = viewer(db)
    for _ in range(FEED_PAGE_SIZE + 5):
        add_user(db, submissive=80)  # identical scores: order decided by the daily tie key
    day = date(2026, 10, 18)
    first = build_feed(db, me, 1, day)
    second = build_feed(db, me, 2, day)
    assert len(first.cards) == FEED_PAGE_SIZE and first.has_next
    assert len(second.cards) == 5 and not second.has_next
    assert not set(handles(first)) & set(handles(second))
    assert handles(build_feed(db, me, 1, day)) == handles(first)
    assert handles(build_feed(db, me, 1, date(2026, 10, 19))) != handles(first)


def test_feed_page_html_has_no_private_data(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "experimental"})
    post(client, "/result/save", score_form({**dict.fromkeys(CATEGORY_KEYS, 13), "dominant": 91}))
    add_user(db, submissive=87, masochist=77, brat=44, pet=66, dislikes=("little", "slave"))
    for path in ("/feed", "/feed?page=1"):
        for headers in ({}, {"HX-Request": "true"}):
            response = client.get(path, headers=headers)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            handles = db.scalars(select(User.handle)).all()
            html = without_random_values(response.text, client, *handles)
            assert uk("feed.matched_on", axes=uk("axis.power")) in html
            for category in CATEGORIES:
                assert not re.search(rf"\b{re.escape(category.name)}\b", html, re.IGNORECASE), (
                    category
                )
            assert "%" not in html
            for number in ("87", "77", "44", "66", "91"):
                assert not re.search(rf"\b{number}\b", html), number


def test_htmx_request_returns_fragment(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    post(client, "/result/save", score_form({**dict.fromkeys(CATEGORY_KEYS, 0), "dominant": 90}))
    for _ in range(FEED_PAGE_SIZE + 1):
        add_user(db, submissive=80)
    full = client.get("/feed").text
    fragment = client.get("/feed?page=2", headers={"HX-Request": "true"}).text
    assert "<html" in full and 'hx-get="/feed?page=2"' in full
    assert "<html" not in fragment
    assert fragment.count('class="card"') == 1


def test_feed_requires_login_and_valid_page(client, db):
    assert client.get("/feed", follow_redirects=False).status_code == 303
    register(client, db)
    assert client.get("/feed?page=0").status_code == 422
    assert uk("feed.not_ready") in client.get("/feed").text


@pytest.mark.slow
def test_feed_speed_with_1000_active_users(db):
    """Section 11: feed in under 500 ms with 1000 active users."""
    import random

    rng = random.Random(1)
    me = viewer(db, sadist=70, rigger=80)
    rows, scores = [], []
    for index in range(1000):
        user_id = uuid.uuid4()
        rows.append(
            {
                "id": user_id,
                "handle": f"perf-{index}",
                "password_hash": "x",
                "recovery_code_hash": "x",
                "gender": rng.choice(["man", "woman", "other"]),
                "seeking": rng.sample(["man", "woman", "other"], rng.randint(1, 3)),
                "mode": rng.choice(["normal", "experimental"]),
                "is_active": True,
                "consent_version": "test",
                "consent_at": NOW,
                "age_confirmed_at": NOW,
            }
        )
        scores.append(
            {"user_id": user_id, "scores": {k: rng.randint(0, 100) for k in CATEGORY_KEYS}}
        )
    db.execute(insert(User), rows)
    db.execute(insert(TestScore), scores)
    db.commit()
    assert db.scalar(select(User.id).where(User.handle == "perf-999"))

    timings = []
    for _ in range(3):
        start = time.perf_counter()
        feed = build_feed(db, me, 1)
        timings.append(time.perf_counter() - start)
        db.expire_all()
    assert feed.cards
    print(f"feed timings, 1000 users: {[round(t * 1000) for t in timings]} ms")
    assert sorted(timings)[1] < 0.5, timings
