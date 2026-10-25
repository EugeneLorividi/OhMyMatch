from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.cli import main
from app.models import Invite, User
from app.security import hash_invite_code
from tests.test_cascade import user_rows, user_with_rows_everywhere


def test_invite_command_prints_codes_and_stores_only_hashes(db, capsys):
    assert main(["invite", "--count", "3", "--ttl-days", "7"]) == 0
    codes = capsys.readouterr().out.split()
    assert len(codes) == 3
    invites = db.scalars(select(Invite)).all()
    assert {invite.code_hash for invite in invites} == {hash_invite_code(c) for c in codes}
    for invite in invites:
        assert invite.used_by is None
        assert invite.used_at is None
        expected = datetime.now(UTC) + timedelta(days=7)
        assert abs(invite.expires_at - expected) < timedelta(minutes=1)


@pytest.mark.parametrize("args", [["--count", "0"], ["--count", "1001"], ["--ttl-days", "0"]])
def test_invite_command_rejects_bad_bounds(args):
    with pytest.raises(SystemExit):
        main(["invite", *args])


def run_delete(monkeypatch, handle: str, answer: str | None) -> int:
    def fake_input() -> str:
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    return main(["delete-user", handle])


def test_delete_user_removes_every_row(client, db, monkeypatch, capsys):
    user = user_with_rows_everywhere(client, db)
    user_id, handle = user.id, user.handle
    others = db.scalar(select(func.count()).select_from(User)) - 1
    assert run_delete(monkeypatch, f"  {handle.upper()} ", handle) == 0
    assert "Deleted." in capsys.readouterr().out
    db.expire_all()
    assert all(count == 0 for count in user_rows(db, user_id).values())
    assert db.scalar(select(func.count()).select_from(User)) == others  # partner kept
    assert client.get("/feed", follow_redirects=False).status_code == 303  # session gone


@pytest.mark.parametrize("answer", [None, "", "no", "yes", "y"])
def test_delete_user_needs_the_nickname_typed_again(client, db, monkeypatch, answer):
    user = user_with_rows_everywhere(client, db)
    before = user_rows(db, user.id)
    assert run_delete(monkeypatch, user.handle, answer) == 1
    db.expire_all()
    assert user_rows(db, user.id) == before


def test_delete_user_unknown_handle(db, monkeypatch, capsys):
    assert run_delete(monkeypatch, "brave-fox-11", "brave-fox-11") == 1
    assert "No such user." in capsys.readouterr().err
