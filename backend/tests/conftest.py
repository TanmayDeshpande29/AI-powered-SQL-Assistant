"""Test fixtures: in-memory SQLite instead of Postgres, a fake LLM instead of Groq.

Environment variables are set BEFORE `app` is imported, because app.core.config
reads them at import time (real env vars take priority over the .env file).
"""

import os

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL="sqlite+aiosqlite://",
    JWT_SECRET_KEY="test-secret-key-that-is-at-least-32-chars",
    GROQ_API_KEY="test-key-not-used",
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.llm.client import get_primary_llm  # noqa: E402
from app.main import app  # noqa: E402

FAKE_SQL = "```sql\nSELECT id, email FROM users;\n```"


@pytest.fixture
async def session_factory():
    # StaticPool keeps ONE connection, so every session sees the same in-memory DB.
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def fake_llm():
    return FakeListChatModel(responses=[FAKE_SQL] * 10)


@pytest.fixture
async def client(session_factory, fake_llm):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    # Dependency overrides: same routes, swapped infrastructure.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_primary_llm] = lambda: fake_llm
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def signup_and_login(client: AsyncClient, email="ada@example.com", password="s3cret-pass"):
    await client.post(
        "/api/v1/auth/signup", json={"name": "Ada", "email": email, "password": password}
    )
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).json()
    return tokens, {"Authorization": f"Bearer {tokens['access_token']}"}
