"""Background processing of schema uploads: the "job" half of Phase 2.

The API stores the upload, answers 202 Accepted at once, and this code runs after the
response (FastAPI BackgroundTasks, same process). The client polls the source's status.
A database row is the job record:  pending -> processing -> ready | failed.

Why not a real queue yet? A Redis-backed worker (arq / Celery) survives restarts and
scales out, but needs Redis running. The client contract (202 + polling) is the same
either way, so only the executor changes when we add one in the SaaS phase.

Phase 3: after a successful merge, the same job refreshes the schema's search index
(services/indexing.py), so new tables become searchable without an extra click.
"""

import asyncio
import logging
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AppError
from app.db.base import utcnow
from app.llm.vision import transcribe_schema_image
from app.models import DbSchema, SchemaSource
from app.services import indexing
from app.services import schemas as schema_service
from app.services.jobs import JobDeps, schema_lock
from app.sql_tools.ddl import extract_schema

logger = logging.getLogger(__name__)

NO_TABLES = (
    "No tables were found. Upload CREATE TABLE statements (e.g. pg_dump --schema-only, "
    "mysqldump --no-data), queries that use your tables, or a screenshot of the schema."
)


class IngestionError(Exception):
    """An expected failure with a message for the user."""


async def process_source(source_id: uuid.UUID, deps: JobDeps) -> None:
    async with deps.session_factory() as db:
        source = await db.get(SchemaSource, source_id)
        if source is None:
            return  # the schema was deleted meanwhile
        schema = await db.get(DbSchema, source.schema_id)
        async with schema_lock(schema.id):
            # Check the status only once we hold the lock: two tasks for the same upload
            # may both have seen "pending" before one of them got the lock.
            await db.refresh(source)
            if source.status != "pending":
                return  # already handled: calling this twice is safe (idempotent)
            source.status = "processing"
            await db.commit()
            error, extra_stats = None, {}
            try:
                if source.kind == "image":
                    transcription = await transcribe_schema_image(
                        deps.llm, source.raw, source.content_type or "image/png", schema.dialect
                    )
                    source.text, source.model = transcription.sql, transcription.model
                    extra_stats["vision"] = {
                        "latency_ms": transcription.latency_ms,
                        "usage": transcription.usage.model_dump() if transcription.usage else None,
                        "cost_usd": transcription.cost_usd,
                    }
                    await db.commit()  # keep the transcription even if parsing fails below
                    if not transcription.sql.strip():
                        raise IngestionError("No database schema was found in the image.")
                # Parsing is CPU work (a big dump can take seconds): run it in a thread so
                # the event loop keeps serving other requests meanwhile.
                result = await asyncio.to_thread(extract_schema, source.text or "", schema.dialect)
                if not result.tables:
                    warnings = result.final_warnings()
                    raise IngestionError(NO_TABLES + (f" ({warnings[0]})" if warnings else ""))
                stats = await schema_service.merge_extraction(db, schema, source, result)
                source.status = "ready"
                source.stats = {**stats, **extra_stats}
                source.warnings = result.final_warnings() or None
            except (IngestionError, AppError) as exc:
                error = getattr(exc, "message", None) or str(exc)
            except Exception:
                logger.exception("Processing schema upload %s failed", source_id)
                error = "Unexpected error while processing this upload."
            if error is not None:
                await db.rollback()
                source = await db.get(SchemaSource, source_id)
                source.status, source.error = "failed", error
                source.stats = extra_stats or None
            source.processed_at = utcnow()
            await db.commit()
            if error is None:
                # Still under the lock: no other upload can change the tables meanwhile.
                # The upload is already "ready"; the index has its own status.
                await indexing.index_schema(db, schema.id, deps)


async def recover_interrupted(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """At startup: jobs that were pending/processing when the server stopped will never
    finish (the in-process queue died with it). Mark them failed so the UI stops waiting."""
    async with session_factory() as db:
        result = await db.execute(
            update(SchemaSource)
            .where(SchemaSource.status.in_(("pending", "processing")))
            .values(
                status="failed",
                error="Interrupted by a server restart. Upload it again.",
                processed_at=utcnow(),
            )
        )
        indexes = await db.execute(
            update(DbSchema)
            .where(DbSchema.index_status.in_(indexing.INDEX_ACTIVE))
            .values(
                index_status="failed",
                index_error="Interrupted by a server restart. Click Rebuild index.",
            )
        )
        await db.commit()
        if result.rowcount:
            logger.warning("Marked %s interrupted schema upload(s) as failed.", result.rowcount)
        if indexes.rowcount:
            logger.warning("Marked %s interrupted index build(s) as failed.", indexes.rowcount)
        return result.rowcount
