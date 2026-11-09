"""Admin CLI.

Usage:
    python -m app.cli invite --count N --ttl-days 7
    python -m app.cli delete-user <handle>
    python -m app.cli seed-demo --target <handle> --out <file>
    python -m app.cli delete-demo
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import INVITE_MAX_COUNT, INVITE_MAX_TTL_DAYS
from app.demo import DEMO_SPECS, delete_demo, demo_handles, new_passwords, seed_demo
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


def _confirmed(prompt: str, word: str) -> bool:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        answer = input()
    except EOFError:
        answer = ""
    return answer.strip().lower() == word


def _seed_demo_command(db: Session, target_handle: str, out: str) -> int:
    target = find_user(db, target_handle)
    if target is None:
        sys.stderr.write("No such user.\n")
        return 1
    if demo_handles(db):
        sys.stderr.write("Demo users already exist. Run delete-demo first.\n")
        return 1
    count = len(DEMO_SPECS)
    prompt = (
        f"This creates {count} synthetic demo users, visible in other people's feeds until\n"
        "delete-demo is run. Type the word demo to confirm: "
    )
    if not _confirmed(prompt, "demo"):
        sys.stderr.write("\nNot confirmed, nothing created.\n")
        return 1
    passwords = new_passwords()
    try:
        # The file is created first, exclusively and with mode 600, and removed if the
        # database step fails, so passwords never sit in a file that is world-readable.
        with os.fdopen(os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.writelines(f"{name} {password}\n" for name, password in passwords.items())
    except OSError as exc:
        sys.stderr.write(f"Cannot create the password file: {exc.strerror}.\n")
        return 1
    try:
        created = seed_demo(db, passwords, target)
    except Exception:
        db.rollback()
        os.unlink(out)
        raise
    sys.stdout.write(f"Created {created} demo users.\n")
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
    seed = commands.add_parser("seed-demo", help="create synthetic demo users for a manual test")
    seed.add_argument("--target", required=True, help="nickname that demo_1 likes")
    seed.add_argument("--out", required=True, help="new file (mode 600) for the demo passwords")
    commands.add_parser("delete-demo", help="delete every demo_ user and what is linked to it")
    args = parser.parse_args(argv)

    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        if args.command == "delete-user":
            return _delete_user_command(db, args.handle)
        if args.command == "seed-demo":
            return _seed_demo_command(db, args.target, args.out)
        if args.command == "delete-demo":
            sys.stdout.write(f"Deleted {delete_demo(db)} demo users.\n")
            return 0
        codes = create_invites(db, args.count, args.ttl_days)
    for code in codes:
        sys.stdout.write(code + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
