"""Test fixtures: in-memory SQLite instead of PostgreSQL, fake LLMs instead of Groq.

Environment variables are set BEFORE `app` is imported, because app.core.config
reads them at import time (real env vars take priority over the .env file).
"""

import os

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL="sqlite+aiosqlite://",
    JWT_SECRET_KEY="test-secret-key-that-is-at-least-32-chars",
    GROQ_API_KEY="test-key-not-used",
    LANGSMITH_TRACING="false",  # never send test runs to LangSmith
)

from collections.abc import AsyncIterator  # noqa: E402
from typing import Any  # noqa: E402

import groq  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402
from langchain_core.messages import AIMessage, AIMessageChunk  # noqa: E402
from langchain_core.outputs import ChatGenerationChunk  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.llm.client import get_llm_provider  # noqa: E402
from app.llm.output_schemas import SQLAnswer  # noqa: E402
from app.main import app  # noqa: E402

FAKE_ANSWER = SQLAnswer(
    sql="```sql\nSELECT id, email FROM users;\n```",  # fenced on purpose: must be stripped
    explanation="Lists every user's id and email.",
    assumptions=["The table is called users."],
    tables_used=["users"],
)
FAKE_EXPLANATION = "Counts rows per department and keeps the large ones."
FAKE_USAGE = {
    "input_tokens": 120,
    "output_tokens": 80,
    "total_tokens": 200,
    "output_token_details": {"reasoning": 30},
}


class FakeChatModel(FakeListChatModel):
    """Stand-in for ChatGroq.

    * structured output -> returns `answer` (as with include_raw=True), with usage
    * streaming -> yields `responses[0]` word by word; usage on the last chunk
    * `errors` -> exceptions raised by the next calls, one per call (simulate outages)
    """

    model_name: str = "fake-primary"
    answer: SQLAnswer | None = FAKE_ANSWER
    errors: list[Any] = []
    calls: int = 0

    def _maybe_fail(self) -> None:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)

    def _raw(self) -> AIMessage:
        return AIMessage(
            content="", usage_metadata=FAKE_USAGE, response_metadata={"model_name": self.model_name}
        )

    def with_structured_output(self, schema, **kwargs):
        def respond(_messages):
            self._maybe_fail()
            parsing_error = None if self.answer else ValueError("not valid JSON")
            return {"raw": self._raw(), "parsed": self.answer, "parsing_error": parsing_error}

        return RunnableLambda(respond)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs) -> AsyncIterator:
        self._maybe_fail()
        words = self.responses[0].split(" ")
        for i, word in enumerate(words):
            last = i == len(words) - 1
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=word if last else word + " ",
                    usage_metadata=FAKE_USAGE if last else None,
                    response_metadata={"model_name": self.model_name} if last else {},
                )
            )


class FakeLLMProvider:
    """Mimics app.llm.client.LLMProvider and records the requested reasoning efforts."""

    def __init__(self) -> None:
        self.models = {
            "primary": FakeChatModel(responses=[FAKE_EXPLANATION], model_name="fake-primary"),
            "fast": FakeChatModel(responses=[FAKE_EXPLANATION], model_name="fake-fast"),
        }
        self.efforts: list[str | None] = []

    def chat_model(self, tier="primary", reasoning_effort=None):
        self.efforts.append(reasoning_effort)
        return self.models[tier]

    def model_name(self, tier):
        return self.models[tier].model_name


def rate_limit_error(retry_after: str = "7") -> groq.RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, headers={"retry-after": retry_after}, request=request)
    return groq.RateLimitError("Rate limit reached", response=response, body=None)


def connection_error() -> groq.APIConnectionError:
    return groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))


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
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
async def client(session_factory, fake_llm):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    # Dependency overrides: same routes, swapped infrastructure.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
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
