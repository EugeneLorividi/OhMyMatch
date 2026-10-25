"""Admin CLI.

Usage:
    python -m app.cli invite --count N --ttl-days 7
    python -m app.cli delete-user <handle>
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import INVITE_MAX_COUNT, INVITE_MAX_TTL_DAYS
from app.models import Invite, User
from app.security import generate_code, hash_invite_code


def create_invites(db: Session, count: int, ttl_days: int) -> list[str]:
    expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
    codes = [generate_code() for _ in range(count)]
    db.add_all(Invite(code_hash=hash_invite_code(code), expires_at=expires_at) for code in codes)
    db.commit()
    return codes


def find_user(db: Session, handle: str) -> User | None:
    return db.scalars(select(User).where(User.handle == handle.strip().lower())).first()


def delete_user(db: Session, user: User) -> None:
    # Hard delete, as on the settings page: every other table cascades from users.
    db.execute(delete(User).where(User.id == user.id))
    db.commit()


def _delete_user_command(db: Session, handle: str) -> int:
    user = find_user(db, handle)
    if user is None:
        sys.stderr.write("No such user.\n")
        return 1
    sys.stdout.write(
        f"User {user.handle}, created {user.created_at:%Y-%m-%d}. This deletes the account\n"
        "and everything linked to it, for good. Type the nickname again to confirm: "
    )
    sys.stdout.flush()
    try:
        answer = input()
    except EOFError:
        answer = ""
    if answer.strip().lower() != user.handle:
        sys.stderr.write("\nNot confirmed, nothing deleted.\n")
        return 1
    delete_user(db, user)
    sys.stdout.write("Deleted.\n")
    return 0


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
    remove = commands.add_parser("delete-user", help="delete an account and all its data")
    remove.add_argument("handle")
    args = parser.parse_args(argv)

    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        if args.command == "delete-user":
            return _delete_user_command(db, args.handle)
        codes = create_invites(db, args.count, args.ttl_days)
    for code in codes:
        sys.stdout.write(code + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
