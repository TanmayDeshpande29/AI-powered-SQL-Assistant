"""Phase 3: keep each schema's search index (Qdrant) in sync with its tables.

    tables (PostgreSQL)
      -> enrich   LLM writes a description + synonyms per table   (optional, batched)
      -> document one search text per table                        (rag/documents.py)
      -> embed    dense meaning vector + sparse BM25 vector        (rag/embeddings.py)
      -> upsert   one Qdrant point per table, id = table id        (rag/vector_store.py)
      -> prune    delete points of tables that no longer exist

Incremental: every table stores fingerprints of what was last described and embedded.
A re-run only pays (LLM tokens, CPU) for tables whose text actually changed, so it is
cheap to call after every upload. Upserts by table id are idempotent: a crash between
Qdrant and PostgreSQL just means the next run embeds that table again.

PostgreSQL stays the source of truth; Qdrant is a derived index that can always be
rebuilt from it (POST /schemas/{id}/index).
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppError, LLMServiceError, RateLimitedError, VectorStoreError
from app.db.base import utcnow
from app.llm.client import LLMProvider
from app.llm.enrichment import describe_tables
from app.llm.prompts import DESCRIBE_TABLES
from app.models import DbSchema, SchemaTable
from app.rag.documents import fingerprint, index_fingerprint, qualified_name, table_document
from app.rag.embeddings import Embedder
from app.rag.vector_store import SchemaIndex, SearchMode, TablePoint
from app.schemas.db_schema import SearchHit, SearchResponse
from app.services.jobs import JobDeps, schema_lock
from app.services.schemas import TableResolver, render_table_card

logger = logging.getLogger(__name__)

INDEX_ACTIVE = ("pending", "indexing")
MAX_SYNONYMS = 8


async def _load(db: AsyncSession, schema_id: uuid.UUID) -> DbSchema | None:
    return await db.scalar(
        select(DbSchema)
        .where(DbSchema.id == schema_id)
        .options(
            selectinload(DbSchema.tables).selectinload(SchemaTable.columns),
            selectinload(DbSchema.tables).selectinload(SchemaTable.relationships),
        )
        # The session may hold older copies (e.g. right after a merge): reload them.
        .execution_options(populate_existing=True)
    )


def _clean_synonyms(synonyms: list[str], table_name: str) -> list[str] | None:
    seen: dict[str, None] = {}
    for word in synonyms:
        word = " ".join(word.lower().split())
        if word and word != table_name.lower():
            seen.setdefault(word, None)
    return list(seen)[:MAX_SYNONYMS] or None


async def _enrich(
    db: AsyncSession, tables: list[SchemaTable], llm: LLMProvider, report: dict[str, Any]
) -> None:
    """Describe the tables whose structure changed since they were last described."""
    pending = []
    for table in tables:
        card = render_table_card(table)
        # The prompt id is part of the fingerprint: a new prompt version re-describes all.
        card_hash = fingerprint(DESCRIBE_TABLES.id, card)
        if table.enrichment_hash != card_hash:
            pending.append((table, card, card_hash))
    size = max(1, settings.schema_enrichment_batch_size)
    for start in range(0, len(pending), size):
        batch = pending[start : start + size]
        try:
            result = await describe_tables(llm, [card for _, card, _ in batch])
        except (RateLimitedError, LLMServiceError) as exc:
            # Degrade, don't fail: tables are still indexed by their names and columns,
            # and the next run retries the descriptions that are missing.
            report["enrichment_error"] = exc.message
            logger.warning("Table descriptions skipped: %s", exc.message)
            return
        by_name = {d.table.strip().lower(): d for d in result.descriptions}
        for table, _, card_hash in batch:
            found = by_name.get(qualified_name(table).lower()) or by_name.get(table.name.lower())
            if found is None:
                continue  # the model skipped it: it stays pending for the next run
            table.description = found.description.strip() or None
            table.synonyms = _clean_synonyms(found.synonyms, table.name)
            table.enrichment_hash = card_hash
            report["enriched"] += 1
        report["enrichment_model"] = result.model
        report["enrichment_cost_usd"] = round(
            report["enrichment_cost_usd"] + (result.cost_usd or 0.0), 8
        )
        # Save each batch: progress survives a later failure, and the connection goes
        # back to the pool while the next LLM call runs.
        await db.commit()


def _incoming(tables: list[SchemaTable]) -> dict[uuid.UUID, list[SchemaTable]]:
    """For every table, the tables whose foreign keys point at it."""
    resolver = TableResolver(tables)
    incoming: dict[uuid.UUID, list[SchemaTable]] = defaultdict(list)
    for table in tables:
        for rel in table.relationships:
            target = resolver.find(rel.to_table_key)
            if target is not None and target.id != table.id and table not in incoming[target.id]:
                incoming[target.id].append(table)
    return incoming


def _payload(schema: DbSchema, table: SchemaTable, document: str, referrers: list[SchemaTable]):
    # Stored next to the vectors: used to filter (tenant), to show results, and in
    # Phase 4 to walk foreign keys from a hit to its neighbours (FK-graph expansion).
    return {
        "user_id": str(schema.user_id),
        "schema_id": str(schema.id),
        "table_id": str(table.id),
        "key": table.key,
        "table": table.name,
        "db_schema": table.db_schema,
        "columns": [c.name for c in table.columns],
        "references": sorted({rel.to_table_key for rel in table.relationships}),
        "referenced_by": sorted({t.key for t in referrers}),
        "inferred": table.inferred,
        "document": document,
    }


async def _embed_and_store(
    schema: DbSchema,
    tables: list[SchemaTable],
    embedder: Embedder,
    index: SchemaIndex,
    report: dict[str, Any],
) -> None:
    incoming = _incoming(tables)
    documents = {
        t.id: table_document(t, [qualified_name(r) for r in incoming[t.id]]) for t in tables
    }
    hashes = {
        t.id: index_fingerprint(documents[t.id], embedder.dense_model, embedder.sparse_model)
        for t in tables
    }
    changed = [t for t in tables if t.index_hash != hashes[t.id]]
    if changed:
        started = time.perf_counter()
        # CPU-bound (ONNX inference): a worker thread keeps the event loop free.
        embeddings = await asyncio.to_thread(
            embedder.embed_documents, [documents[t.id] for t in changed]
        )
        report["embed_ms"] = int((time.perf_counter() - started) * 1000)
        await index.upsert(
            [
                TablePoint(t.id, emb, _payload(schema, t, documents[t.id], incoming[t.id]))
                for t, emb in zip(changed, embeddings, strict=True)
            ]
        )
    await index.delete_missing(schema.id, keep=[t.id for t in tables])
    now = utcnow()
    for table in changed:
        table.index_hash, table.indexed_at = hashes[table.id], now
    report["embedded"] = len(changed)
    report["unchanged"] = len(tables) - len(changed)


async def index_schema(db: AsyncSession, schema_id: uuid.UUID, deps: JobDeps) -> None:
    """(Re)build one schema's search index. The caller holds schema_lock(schema_id)."""
    schema = await _load(db, schema_id)
    if schema is None:
        return  # deleted meanwhile
    schema.index_status, schema.index_error = "indexing", None
    await db.commit()
    started = time.perf_counter()
    tables = list(schema.tables)
    report: dict[str, Any] = {
        "tables": len(tables),
        "embedded": 0,
        "unchanged": 0,
        "enriched": 0,
        "enrichment_cost_usd": 0.0,
        "enrichment_model": None,
        "enrichment_error": None,
        "embed_ms": 0,
        "dense_model": deps.embedder.dense_model,
        "sparse_model": deps.embedder.sparse_model,
    }
    try:
        if settings.schema_enrichment and tables:
            await _enrich(db, tables, deps.llm, report)
        await _embed_and_store(schema, tables, deps.embedder, deps.index, report)
        report["seconds"] = round(time.perf_counter() - started, 2)
        schema.index_status, schema.index_stats, schema.indexed_at = "ready", report, utcnow()
        await db.commit()
        logger.info("Indexed schema %s: %s", schema_id, report)
    except Exception as exc:
        if isinstance(exc, AppError):
            message = exc.message
        else:
            logger.exception("Indexing schema %s failed", schema_id)
            message = "Unexpected error while building the search index."
        await db.rollback()
        schema = await db.get(DbSchema, schema_id)
        if schema is not None:
            schema.index_status, schema.index_error = "failed", message
            await db.commit()


async def run_index_job(schema_id: uuid.UUID, deps: JobDeps) -> None:
    """Background entry point (POST /schemas/{id}/index, after deleting a table)."""
    async with schema_lock(schema_id):
        async with deps.session_factory() as db:
            await index_schema(db, schema_id, deps)


async def mark_pending(db: AsyncSession, schema: DbSchema) -> None:
    schema.index_status, schema.index_error = "pending", None
    await db.commit()


# --- Search (Phase 3: one method at a time; Phase 4 fuses them) --------------------


async def search_tables(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    schema: DbSchema,
    query: str,
    mode: SearchMode,
    limit: int,
    embedder: Embedder,
    index: SchemaIndex,
) -> SearchResponse:
    """`schema` must already be ownership-checked (get_owned) by the caller."""
    started = time.perf_counter()
    embedding = await asyncio.to_thread(embedder.embed_query, query)
    embed_ms = int((time.perf_counter() - started) * 1000)
    hits = await index.search(
        user_id=user_id, schema_id=schema.id, mode=mode, query=embedding, limit=limit
    )
    search_ms = int((time.perf_counter() - started) * 1000) - embed_ms
    # Join back to PostgreSQL (the source of truth): drop points of deleted tables.
    rows = (
        await db.execute(
            select(
                SchemaTable.id, SchemaTable.name, SchemaTable.db_schema, SchemaTable.description
            ).where(SchemaTable.schema_id == schema.id)
        )
    ).all()
    tables = {row.id: row for row in rows}
    results = []
    for hit in hits:
        row = tables.get(hit.table_id)
        if row is None:
            continue
        results.append(
            SearchHit(
                rank=len(results) + 1,
                table_id=row.id,
                name=row.name,
                db_schema=row.db_schema,
                description=row.description,
                score=round(hit.score, 4),
                document=hit.payload.get("document", ""),
            )
        )
    return SearchResponse(
        query=query,
        mode=mode,
        model=embedder.dense_model if mode == "dense" else embedder.sparse_model,
        index_status=schema.index_status,
        embed_ms=embed_ms,
        search_ms=search_ms,
        results=results,
    )


# --- Cleanup when data is deleted ----------------------------------------------------


async def forget_schema(index: SchemaIndex, schema_id: uuid.UUID) -> None:
    try:
        await index.delete_schema(schema_id)
    except VectorStoreError:
        # Orphaned points can't leak: every search is filtered by an existing schema.
        logger.warning("Could not delete the search index of schema %s", schema_id)


async def forget_user(index: SchemaIndex, user_id: uuid.UUID) -> None:
    try:
        await index.delete_user(user_id)
    except VectorStoreError:
        logger.warning("Could not delete the search index of user %s", user_id)
