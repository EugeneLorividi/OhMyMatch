from sqlalchemy import delete, func, or_, select

from app.categories import CATEGORY_KEYS
from app.db.base import Base
from app.models import User
from app.reactions import react
from tests.helpers import post, register, score_form
from tests.test_feed import add_user

# Columns that point at users.id, per table.
USER_COLUMNS = {
    "users": ("id",),
    "invites": ("used_by",),
    "sessions": ("user_id",),
    "test_scores": ("user_id",),
    "dislikes": ("user_id",),
    "reactions": ("from_user", "to_user"),
    "matches": ("user_a", "user_b"),
}


def test_every_table_is_covered():
    assert set(Base.metadata.tables) == set(USER_COLUMNS)


def test_deleting_user_removes_every_row(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    post(client, "/result/save", score_form({**dict.fromkeys(CATEGORY_KEYS, 40), "dominant": 90}))
    post(client, "/dislikes", {"category": ["brat"]})
    user = db.scalars(select(User)).one()
    user_id = user.id
    partner = add_user(db, gender="woman", seeking=("man",), submissive=80)
    react(db, partner, user_id, "like")
    react(db, user, partner.id, "like")

    def rows() -> dict[str, int]:
        counts = {}
        for name, columns in USER_COLUMNS.items():
            table = Base.metadata.tables[name]
            condition = or_(*(table.c[column] == user_id for column in columns))
            counts[name] = db.scalar(select(func.count()).select_from(table).where(condition))
        return counts

    assert all(count >= 1 for count in rows().values())
    assert rows()["matches"] == 1
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    assert all(count == 0 for count in rows().values())
