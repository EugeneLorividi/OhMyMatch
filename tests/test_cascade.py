from sqlalchemy import delete, func, select

from app.categories import CATEGORY_KEYS
from app.db.base import Base
from app.models import User
from tests.helpers import post, register, score_form

# Column that points at users.id, per table.
USER_COLUMNS = {
    "users": "id",
    "invites": "used_by",
    "sessions": "user_id",
    "test_scores": "user_id",
    "dislikes": "user_id",
}


def test_every_table_is_covered():
    assert set(Base.metadata.tables) == set(USER_COLUMNS)


def test_deleting_user_removes_every_row(client, db):
    register(client, db)
    post(client, "/profile", {"gender": "man", "seeking": ["woman"], "mode": "normal"})
    post(client, "/result/save", score_form(dict.fromkeys(CATEGORY_KEYS, 40)))
    post(client, "/dislikes", {"category": ["brat"]})
    user_id = db.scalars(select(User.id)).one()

    def rows() -> dict[str, int]:
        return {
            name: db.scalar(
                select(func.count())
                .select_from(Base.metadata.tables[name])
                .where(Base.metadata.tables[name].c[column] == user_id)
            )
            for name, column in USER_COLUMNS.items()
        }

    assert all(count >= 1 for count in rows().values())
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    assert all(count == 0 for count in rows().values())
