import os

# Settings are required env vars with no defaults (see app/config.py) — set
# dummy values before anything imports app.config, so tests don't need a
# real .env file or a live database just to exercise routes like /health.
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("HH_CLIENT_ID", "test-hh-client-id")
os.environ.setdefault("HH_CLIENT_SECRET", "test-hh-client-secret")
os.environ.setdefault("HH_REDIRECT_URI", "https://example.invalid/providers/hh/callback")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
async def db_engine():
    """Fresh in-memory SQLite DB per test — no Postgres/Docker required.

    Models use cross-dialect types (sqlalchemy.Uuid/JSON) precisely so this
    works; the real deployment still runs the Alembic migration against
    Postgres (that migration is Postgres-specific and untouched by this).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {settings.INTERNAL_SERVICE_TOKEN}"}
