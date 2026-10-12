"""Async engine + session factory, and the FastAPI dependency that hands out sessions.

engine           : owns the connection pool (one per process)
SessionLocal     : factory producing AsyncSession objects (one per request)
get_db()         : FastAPI dependency; opens a session, yields it, always closes it
check_database() : startup self-check that explains connection problems in plain words
"""

import logging
from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableError

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.sqlalchemy_url,  # built from POSTGRES_* (or DATABASE_URL) in core/config.py
    echo=settings.db_echo,  # set DB_ECHO=true to print every SQL statement
    pool_pre_ping=True,  # detect connections dropped by the server before using them
)

# expire_on_commit=False: objects stay readable after commit. With async sessions,
# touching an expired attribute would trigger implicit IO and raise an error.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Errors that mean "could not reach / log into the database at all": wrong password,
# unknown database, server down (connection refused / timeout are OSErrors).
CONNECTION_ERRORS = (DBAPIError, OSError)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """FastAPI dependency for code that outlives the request (background jobs open their
    own sessions; the request's session is closed by then). Tests override it."""
    return SessionLocal


def _target() -> str:
    """Where we connect, with the password masked: safe to print in logs."""
    return make_url(settings.sqlalchemy_url).render_as_string(hide_password=True)


def _reason(exc: Exception) -> str:
    """The driver's own message (e.g. 'password authentication failed for user ...')."""
    return str(getattr(exc, "orig", None) or exc).splitlines()[0]


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            # Borrow a pooled connection now, so a broken database configuration
            # becomes one clear 503 here instead of a 500 deep inside a query.
            await session.connection()
        except CONNECTION_ERRORS as exc:
            logger.error("Database connection failed (%s): %s", _target(), _reason(exc))
            raise DatabaseUnavailableError() from exc
        yield session


async def release_connection(session: AsyncSession) -> None:
    """End the current transaction so its connection goes back to the pool.

    Call this before slow work that doesn't touch the database (an LLM call takes
    seconds). Otherwise the connection sits idle but reserved for the whole call, and a
    burst of concurrent requests can exhaust the pool. Loaded objects stay readable
    (expire_on_commit=False); the next query simply borrows a connection again.
    """
    await session.commit()


async def check_database() -> bool:
    """Run once at startup: log whether the database is reachable and migrated.

    It never crashes the app (so /docs and /health still work); it only tells you,
    in plain words, what to fix. Returns True when the database is ready to use.
    """
    try:
        async with engine.connect() as conn:
            migrated = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).has_table("alembic_version")
            )
    except CONNECTION_ERRORS as exc:
        logger.error(
            "Cannot connect to the database %s: %s. Check the POSTGRES_* values in "
            "backend/.env (the server re-reads .env only when it restarts).",
            _target(),
            _reason(exc),
        )
        return False
    if not migrated:
        logger.warning(
            "Connected to %s, but it has no tables yet. Run: uv run alembic upgrade head",
            _target(),
        )
        return False
    logger.info("Database ready: %s", _target())
    return True
