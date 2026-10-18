from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.cli import main
from app.models import Invite
from app.security import hash_invite_code


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
