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
from app.core.tracing import configure_tracing
from app.db.session import SessionLocal, check_database, engine
from app.services.ingestion import recover_interrupted


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Code before `yield` runs once at startup, code after it once at shutdown.
    configure_logging()
    configure_tracing(settings)  # before any LLM call: LangSmith caches its env vars
    # Logs a clear hint if PostgreSQL is unreachable or unmigrated. If it is fine, fail any
    # schema uploads a previous run left half-done (the in-process job queue died with it).
    if await check_database():
        await recover_interrupted(SessionLocal)
    yield
    await engine.dispose()  # close pooled DB connections cleanly


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

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
