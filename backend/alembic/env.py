"""Alembic migration environment (async).

Alembic compares `target_metadata` (what the ORM models say the schema should be)
with the live database and writes/applies migration scripts for the difference.

    uv run alembic revision --autogenerate -m "describe change"   # create a script
    uv run alembic upgrade head                                    # apply all scripts
    uv run alembic downgrade -1                                    # undo the last one
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Same connection settings as the app (POSTGRES_* or DATABASE_URL), passed straight to
# SQLAlchemy. Not via config.set_main_option(): alembic.ini is parsed by ConfigParser,
# which treats "%" as interpolation syntax and would choke on URL-encoded passwords.
DB_URL = settings.sqlalchemy_url


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it (for DBA review)."""
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # also detect column type changes, not only added/removed columns
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite can't ALTER most things
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # A migration is a one-off script: no connection pooling needed.
    connectable = create_async_engine(DB_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
