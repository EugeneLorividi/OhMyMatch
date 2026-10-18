"""Admin CLI. Usage: python -m app.cli invite --count N --ttl-days 7"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import INVITE_MAX_COUNT, INVITE_MAX_TTL_DAYS
from app.models import Invite
from app.security import generate_code, hash_invite_code


def create_invites(db: Session, count: int, ttl_days: int) -> list[str]:
    expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
    codes = [generate_code() for _ in range(count)]
    db.add_all(Invite(code_hash=hash_invite_code(code), expires_at=expires_at) for code in codes)
    db.commit()
    return codes


def _bounded(maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not 1 <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between 1 and {maximum}")
        return number

    return parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("invite", help="create one-time invite codes")
    invite.add_argument("--count", type=_bounded(INVITE_MAX_COUNT), default=1)
    invite.add_argument("--ttl-days", type=_bounded(INVITE_MAX_TTL_DAYS), default=7)
    args = parser.parse_args(argv)

    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        codes = create_invites(db, args.count, args.ttl_days)
    for code in codes:
        sys.stdout.write(code + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
