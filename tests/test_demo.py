import stat

import pytest
from sqlalchemy import func, select

from app.categories import CATEGORY_KEYS
from app.cli import main
from app.db.base import Base
from app.demo import DEMO_PREFIX, DEMO_SPECS, FILLER_MAX, full_scores
from app.handles import ADJECTIVES, NOUNS, is_generated_handle
from app.matching.feed import build_feed
from app.models import Match, Reaction, User
from app.reactions import Outcome, react
from app.security import verify_secret
from tests.helpers import post, register
from tests.test_feed import add_user, handles


def run(monkeypatch, argv: list[str], answer: str | None = "demo") -> int:
    def fake_input() -> str:
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    return main(argv)


def seed(monkeypatch, tmp_path, target: User, answer: str | None = "demo") -> int:
    out = str(tmp_path / "demo-users.txt")
    return run(monkeypatch, ["seed-demo", "--target", target.handle, "--out", out], answer)


def invented_viewer(db, **kwargs):
    """A made-up profile, not anybody's real result."""
    values = {"switch": 90, "dominant": 90, "degrader": 85, "rigger": 80, "exhibitionist": 80}
    return add_user(db, gender="man", seeking=("woman",), **{**values, **kwargs})


def table_counts(db) -> dict[str, int]:
    return {
        name: db.scalar(select(func.count()).select_from(table))
        for name, table in Base.metadata.tables.items()
    }


def test_specs_are_complete_and_stable():
    assert [spec.handle for spec in DEMO_SPECS] == [f"demo_{n}" for n in range(1, 7)]
    for spec in DEMO_SPECS:
        scores = full_scores(spec)
        assert set(scores) == set(CATEGORY_KEYS)
        assert scores == full_scores(spec)
        assert all(
            0 <= value <= FILLER_MAX for key, value in scores.items() if key not in spec.scores
        )
        assert all(scores[key] == value for key, value in spec.scores.items())


def test_seed_writes_a_private_file_and_prints_only_the_count(db, monkeypatch, tmp_path, capsys):
    target = invented_viewer(db)
    assert seed(monkeypatch, tmp_path, target) == 0
    out = capsys.readouterr().out
    assert "Created 6 demo users." in out
    path = tmp_path / "demo-users.txt"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    passwords = dict(line.split() for line in path.read_text().splitlines())
    assert list(passwords) == [spec.handle for spec in DEMO_SPECS]
    assert len(set(passwords.values())) == 6
    assert not any(password in out for password in passwords.values())
    for user in db.scalars(select(User).where(User.handle.like("demo\\_%", escape="\\"))):
        assert user.is_active
        assert verify_secret(user.password_hash, passwords[user.handle])


@pytest.mark.parametrize("answer", [None, "", "yes", "y", "no"])
def test_seed_needs_the_word_typed(db, monkeypatch, tmp_path, answer):
    target = invented_viewer(db)
    before = table_counts(db)
    assert seed(monkeypatch, tmp_path, target, answer) == 1
    assert table_counts(db) == before
    assert not (tmp_path / "demo-users.txt").exists()


def test_seed_refuses_unknown_target_existing_file_and_second_run(db, monkeypatch, tmp_path):
    target = invented_viewer(db)
    out = str(tmp_path / "demo-users.txt")
    assert run(monkeypatch, ["seed-demo", "--target", "nobody-here-00", "--out", out]) == 1
    (tmp_path / "demo-users.txt").write_text("keep me")
    assert seed(monkeypatch, tmp_path, target) == 1
    assert (tmp_path / "demo-users.txt").read_text() == "keep me"
    assert db.scalar(select(func.count()).select_from(User)) == 1
    (tmp_path / "demo-users.txt").unlink()
    assert seed(monkeypatch, tmp_path, target) == 0
    (tmp_path / "demo-users.txt").unlink()
    assert seed(monkeypatch, tmp_path, target) == 1
    assert db.scalar(select(func.count()).select_from(User)) == 7


def test_demo_1_likes_the_target_so_the_return_like_matches(db, monkeypatch, tmp_path):
    target = invented_viewer(db)
    seed(monkeypatch, tmp_path, target)
    demo_1 = db.scalars(select(User).where(User.handle == "demo_1")).one()
    like = db.get(Reaction, (demo_1.id, target.id))
    assert like is not None and like.kind == "like"
    assert db.scalars(select(Reaction)).all() == [like]
    assert react(db, target, demo_1.id, "like") is Outcome.MATCHED
    assert db.scalars(select(Match)).one()


@pytest.mark.parametrize("mode", ["normal", "experimental"])
def test_feed_shows_exactly_demo_1_5_6_and_ranks_by_score(db, monkeypatch, tmp_path, mode):
    me = invented_viewer(db, mode=mode)
    seed(monkeypatch, tmp_path, me)
    cards = build_feed(db, me, 1).cards
    assert {card.handle for card in cards} == {"demo_1", "demo_5", "demo_6"}
    assert cards[0].handle == "demo_1"
    # Section 7 step 6: demo_6 outranks demo_5 for this viewer. Two of the five pairs in play
    # work at 90 and 80 through the viewer's Switch; demo_5 has one working pair out of four.
    if mode == "normal":
        assert handles(build_feed(db, me, 1)) == ["demo_1", "demo_6", "demo_5"]


def test_demo_6_is_visible_only_through_the_viewers_switch(db, monkeypatch, tmp_path):
    me = invented_viewer(db, switch=0)
    seed(monkeypatch, tmp_path, me)
    assert "demo_6" not in handles(build_feed(db, me, 1))


def test_demo_1_caption_and_demo_5_depend_on_the_viewer_mode(db, monkeypatch, tmp_path):
    me = invented_viewer(db)
    seed(monkeypatch, tmp_path, me)
    cards = {card.handle: card for card in build_feed(db, me, 1).cards}
    assert set(cards["demo_1"].matched) == {"power", "humiliation", "rope", "display"}
    assert cards["demo_5"].matched == ("display",)
    assert cards["demo_5"].curious == ()
    me.mode = "experimental"
    db.commit()
    cards = {card.handle: card for card in build_feed(db, me, 1).cards}
    assert cards["demo_5"].matched == ("display",)
    assert cards["demo_5"].curious


def test_delete_demo_leaves_no_row_and_keeps_everyone_else(db, monkeypatch, tmp_path, capsys):
    me = invented_viewer(db)
    bystander = add_user(db, gender="woman", seeking=("man",), submissive=80)
    lookalike = add_user(db, gender="woman", seeking=("man",))
    lookalike.handle = "demoa1"  # "_" must not act as a LIKE wildcard
    db.commit()
    before = table_counts(db)
    seed(monkeypatch, tmp_path, me)
    demo_1 = db.scalars(select(User).where(User.handle == "demo_1")).one()
    react(db, me, demo_1.id, "like")  # match, so matches and reactions have demo rows too
    assert table_counts(db)["matches"] == 1
    capsys.readouterr()
    assert main(["delete-demo"]) == 0
    assert capsys.readouterr().out.strip() == "Deleted 6 demo users."
    db.expire_all()
    assert table_counts(db) == before
    assert {u.id for u in db.scalars(select(User))} == {me.id, bystander.id, lookalike.id}
    assert main(["delete-demo"]) == 0
    assert capsys.readouterr().out.strip() == "Deleted 0 demo users."


def test_registration_cannot_take_a_demo_nickname(client, db):
    from tests.helpers import make_invite

    code = make_invite(db)
    post(client, "/register", {"step": "code", "invite_code": code})
    response = post(
        client,
        "/register",
        {
            "step": "details",
            "invite_code": code,
            "handle": "demo_1",
            "age_confirmed": "yes",
            "consent": "yes",
            "password": "synthetic-password-1",
            "password_confirm": "synthetic-password-1",
        },
    )
    assert response.status_code == 400
    assert db.scalars(select(User)).first() is None
    handle, done = register(client, db)
    assert not handle.startswith(DEMO_PREFIX)


def test_generated_handles_can_never_look_like_demo():
    assert not is_generated_handle("demo_1")
    assert not any(word.startswith("demo") for word in ADJECTIVES + NOUNS)
