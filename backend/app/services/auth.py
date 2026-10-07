"""Business logic for accounts. Knows nothing about HTTP: routes call these functions,
and tests (or future agents/MCP tools) can call them directly too."""

import uuid

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, BadRequestError, ConflictError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import SignupRequest, TokenPair

INVALID_CREDENTIALS = "Invalid email or password."


def issue_tokens(user: User) -> TokenPair:
    subject = str(user.id)
    return TokenPair(
        access_token=create_token(subject, "access"),
        refresh_token=create_token(subject, "refresh"),
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def register_user(db: AsyncSession, data: SignupRequest) -> User:
    if await get_user_by_email(db, data.email):
        raise ConflictError("An account with this email already exists.")

    user = User(name=data.name, email=data.email, hashed_password=hash_password(data.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:  # two signups for the same email racing each other
        await db.rollback()
        raise ConflictError("An account with this email already exists.") from exc
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    # verify_password runs even when user is None, so both failure paths take equally long.
    password_ok = verify_password(password, user.hashed_password if user else None)
    if not user or not password_ok or not user.is_active:
        raise AuthenticationError(INVALID_CREDENTIALS)
    return user


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token, "refresh")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired refresh token.") from exc
    if not user or not user.is_active:
        raise AuthenticationError("Invalid or expired refresh token.")
    return issue_tokens(user)


async def change_password(db: AsyncSession, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        # 400, not 401: the session is valid, only the form input is wrong. A 401 here
        # would make the frontend treat it as an expired session and log the user out.
        raise BadRequestError("Current password is incorrect.")
    user.hashed_password = hash_password(new)
    await db.commit()
