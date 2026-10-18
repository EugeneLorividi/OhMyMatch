import os

import pytest

# Synthetic key for tests only; must be set before app.config is imported.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-" + "x" * 32)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise pytest.UsageError(
        "TEST_DATABASE_URL is not set. Start a test database with "
        "`docker compose -f compose.test.yml up -d` and set "
        "TEST_DATABASE_URL=postgresql+psycopg://test:test@127.0.0.1:55432/test"
    )
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest.fixture(autouse=True)
def clean_tables(database):
    limiter.reset()
    yield
    limiter.reset()
    names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with get_sessionmaker()() as db:
        db.execute(text(f"TRUNCATE {names} CASCADE"))
        db.commit()


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def client():
    # https base URL so the Secure __Host- cookies are sent back.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
