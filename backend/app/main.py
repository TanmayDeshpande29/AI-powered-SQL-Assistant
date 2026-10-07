"""Application entrypoint (run from backend/):

    uv run uvicorn app.main:app --reload --reload-include .env

`--reload-include .env` restarts the server when .env changes too; by default only
*.py files are watched, and settings are read once at startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import check_database, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Code before `yield` runs once at startup, code after it once at shutdown.
    configure_logging()
    await check_database()  # logs a clear hint if PostgreSQL is unreachable or unmigrated
    yield
    await engine.dispose()  # close pooled DB connections cleanly


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
