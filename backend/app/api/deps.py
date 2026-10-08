"""Reusable FastAPI dependencies.

`Annotated[Type, Depends(fn)]` aliases let routes declare what they need
(`db: DbSession, user: CurrentUser`) and FastAPI resolves it per request.
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db
from app.llm.client import LLMProvider, get_llm_provider
from app.models import User

# auto_error=False: we raise our own 401 in the standard error envelope instead of
# FastAPI's default 403. It also adds the "Authorize" button to Swagger UI.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
LLM = Annotated[LLMProvider, Depends(get_llm_provider)]


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
