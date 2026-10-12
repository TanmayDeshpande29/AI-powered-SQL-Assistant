"""Reusable FastAPI dependencies.

`Annotated[Type, Depends(fn)]` aliases let routes declare what they need
(`db: DbSession, user: CurrentUser`) and FastAPI resolves it per request.
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db, get_session_factory
from app.llm.client import LLMProvider, get_llm_provider
from app.models import User
from app.rag.embeddings import Embedder, get_embedder
from app.rag.vector_store import SchemaIndex, get_schema_index
from app.services.jobs import JobDeps

# auto_error=False: we raise our own 401 in the standard error envelope instead of
# FastAPI's default 403. It also adds the "Authorize" button to Swagger UI.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
LLM = Annotated[LLMProvider, Depends(get_llm_provider)]
Embeddings = Annotated[Embedder, Depends(get_embedder)]
VectorIndex = Annotated[SchemaIndex, Depends(get_schema_index)]


def get_job_deps(
    session_factory: SessionFactory, llm: LLM, embedder: Embeddings, index: VectorIndex
) -> JobDeps:
    """Everything a background job needs, bundled (each part stays overridable in tests)."""
    return JobDeps(session_factory=session_factory, llm=llm, embedder=embedder, index=index)


Jobs = Annotated[JobDeps, Depends(get_job_deps)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise AuthenticationError()
    try:
        payload = decode_token(credentials.credentials, "access")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid or expired access token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
