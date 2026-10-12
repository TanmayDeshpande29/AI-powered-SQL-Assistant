"""Uploaded database schemas: CRUD, idempotent uploads, merging parsed DDL into the
database, and turning a schema into prompt context.

Merge rules (one schema can receive many uploads, in any order):
  * a CREATE TABLE ("declared") replaces the table's columns and foreign keys
  * ALTER TABLE / COMMENT ON ("altered") only add to an existing table
  * tables seen only in queries ("inferred") never overwrite declared ones
"""

import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.db.base import utcnow
from app.models import DbSchema, SchemaColumn, SchemaRelationship, SchemaSource, SchemaTable
from app.schemas.db_schema import (
    RelationshipRead,
    SchemaCreate,
    SchemaDetail,
    SchemaSummary,
    SchemaUpdate,
    SourceRead,
    TableRead,
)
from app.sql_tools.catalog import SchemaCatalog, table_key
from app.sql_tools.ddl import ExtractedTable, ExtractionResult

ACTIVE_STATUSES = ("pending", "processing")
_IMAGE_SIGNATURES = {  # "magic bytes": trust the file's content, not its name
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}
SQL_EXTENSIONS = (".sql", ".txt", ".ddl")


# --- CRUD -----------------------------------------------------------------------


async def get_owned(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID, *, with_tables: bool = False
) -> DbSchema:
    query = select(DbSchema).where(DbSchema.id == schema_id, DbSchema.user_id == user_id)
    if with_tables:
        query = query.options(
            selectinload(DbSchema.tables).selectinload(SchemaTable.columns),
            selectinload(DbSchema.tables).selectinload(SchemaTable.relationships),
        )
    schema = await db.scalar(query)
    if schema is None:  # missing and not-yours look the same (no IDOR leaks)
        raise NotFoundError("Schema not found.")
    return schema


async def create_schema(db: AsyncSession, user_id: uuid.UUID, data: SchemaCreate) -> DbSchema:
    schema = DbSchema(
        user_id=user_id, name=data.name.strip(), dialect=data.dialect, description=data.description
    )
    db.add(schema)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"You already have a schema named '{data.name}'.") from exc
    return schema


async def update_schema(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID, data: SchemaUpdate
) -> DbSchema:
    schema = await get_owned(db, user_id, schema_id)
    for field_name, value in data.model_dump(exclude_unset=True).items():
        setattr(schema, field_name, value.strip() if isinstance(value, str) else value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"You already have a schema named '{data.name}'.") from exc
    return schema


async def delete_schema(db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID) -> None:
    schema = await get_owned(db, user_id, schema_id)
    await db.delete(schema)  # sources, tables, columns, relationships: ON DELETE CASCADE
    await db.commit()


async def delete_table(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID, table_id: uuid.UUID
) -> None:
    await get_owned(db, user_id, schema_id)
    table = await db.scalar(
        select(SchemaTable).where(SchemaTable.id == table_id, SchemaTable.schema_id == schema_id)
    )
    if table is None:
        raise NotFoundError("Table not found.")
    await db.delete(table)
    await db.commit()


# --- Read models ------------------------------------------------------------------


async def summaries(db: AsyncSession, schemas: list[DbSchema]) -> list[SchemaSummary]:
    """Counts and status for several schemas in 3 queries (not 3 per schema)."""
    ids = [s.id for s in schemas]
    if not ids:
        return []
    table_counts = dict(
        (
            await db.execute(
                select(SchemaTable.schema_id, func.count(SchemaTable.id))
                .where(SchemaTable.schema_id.in_(ids))
                .group_by(SchemaTable.schema_id)
            )
        ).all()
    )
    column_counts = dict(
        (
            await db.execute(
                select(SchemaTable.schema_id, func.count(SchemaColumn.id))
                .join(SchemaColumn, SchemaColumn.table_id == SchemaTable.id)
                .where(SchemaTable.schema_id.in_(ids))
                .group_by(SchemaTable.schema_id)
            )
        ).all()
    )
    busy = set(
        await db.scalars(
            select(SchemaSource.schema_id)
            .where(SchemaSource.schema_id.in_(ids), SchemaSource.status.in_(ACTIVE_STATUSES))
            .distinct()
        )
    )
    result = []
    for s in schemas:
        tables = table_counts.get(s.id, 0)
        status = "processing" if s.id in busy else ("ready" if tables else "empty")
        result.append(
            SchemaSummary(
                id=s.id,
                name=s.name,
                dialect=s.dialect,
                description=s.description,
                status=status,
                table_count=tables,
                column_count=column_counts.get(s.id, 0),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return result


async def list_schemas(db: AsyncSession, user_id: uuid.UUID) -> list[SchemaSummary]:
    schemas = list(
        await db.scalars(
            select(DbSchema).where(DbSchema.user_id == user_id).order_by(DbSchema.name)
        )
    )
    return await summaries(db, schemas)


class _Resolver:
    """Finds tables by key, or by bare name when that name is unique."""

    def __init__(self, tables: list[SchemaTable]) -> None:
        self.by_key = {t.key: t for t in tables}
        self.by_name: dict[str, list[SchemaTable]] = {}
        for t in tables:
            self.by_name.setdefault(t.name.lower(), []).append(t)

    def find(self, key_or_name: str) -> SchemaTable | None:
        lowered = key_or_name.strip().lower()
        if lowered in self.by_key:
            return self.by_key[lowered]
        if "." in lowered:
            namespace, _, name = lowered.rpartition(".")
            found = self.by_key.get(table_key(namespace, name))
            if found:
                return found
            lowered = name
        candidates = self.by_name.get(lowered, [])
        return candidates[0] if len(candidates) == 1 else None


def _table_read(table: SchemaTable, resolver: _Resolver) -> TableRead:
    return TableRead(
        id=table.id,
        name=table.name,
        db_schema=table.db_schema,
        comment=table.comment,
        inferred=table.inferred,
        columns=table.columns,
        relationships=[
            RelationshipRead(
                columns=rel.from_columns,
                to_table=rel.to_table_name,
                to_columns=rel.to_columns,
                to_table_id=(target.id if (target := resolver.find(rel.to_table_key)) else None),
                name=rel.name,
                inferred=rel.inferred,
            )
            for rel in table.relationships
        ],
    )


async def schema_detail(db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID) -> SchemaDetail:
    schema = await get_owned(db, user_id, schema_id, with_tables=True)
    [summary] = await summaries(db, [schema])
    resolver = _Resolver(schema.tables)
    return SchemaDetail(
        **summary.model_dump(), tables=[_table_read(t, resolver) for t in schema.tables]
    )


def source_read(source: SchemaSource) -> SourceRead:
    read = SourceRead.model_validate(source)
    if source.kind == "image":
        read.transcription = source.text
    return read


async def list_sources(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID
) -> list[SourceRead]:
    await get_owned(db, user_id, schema_id)
    sources = await db.scalars(
        select(SchemaSource)
        .where(SchemaSource.schema_id == schema_id)
        .order_by(SchemaSource.created_at.desc())
        .limit(50)
    )
    return [source_read(s) for s in sources]


async def get_source(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID, source_id: uuid.UUID
) -> SourceRead:
    await get_owned(db, user_id, schema_id)
    source = await db.scalar(
        select(SchemaSource).where(
            SchemaSource.id == source_id, SchemaSource.schema_id == schema_id
        )
    )
    if source is None:
        raise NotFoundError("Upload not found.")
    return source_read(source)


# --- Uploads (idempotent) -----------------------------------------------------------


def classify_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    """(kind, content_type) from the file's content first, its name second."""
    for signature, content_type in _IMAGE_SIGNATURES.items():
        if data.startswith(signature):
            return "image", content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if (filename or "").lower().endswith(SQL_EXTENSIONS):
        return "sql_file", "text/plain"
    raise UnsupportedMediaTypeError(
        "Upload a .sql / .txt / .ddl file, or a PNG, JPEG or WebP screenshot."
    )


def decode_sql_file(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):  # SSMS often saves UTF-16
        return data.decode("utf-16")
    if b"\x00" in data:
        raise UnsupportedMediaTypeError("This file looks binary, not like SQL text.")
    try:
        return data.decode("utf-8-sig")  # -sig also strips a UTF-8 byte-order mark
    except UnicodeDecodeError:
        return data.decode("latin-1")  # never fails: every byte is a valid character


def check_size(kind: str, size: int) -> None:
    limit = settings.max_image_upload_bytes if kind == "image" else settings.max_sql_upload_bytes
    if size > limit:
        raise PayloadTooLargeError(f"The file is too large (limit {limit // 1_000_000} MB).")


async def add_source(
    db: AsyncSession,
    schema: DbSchema,
    *,
    kind: str,
    text: str | None = None,
    raw: bytes | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[SchemaSource, bool]:
    """Store an upload. Returns (source, needs_processing).

    Idempotent: the same bytes uploaded twice to the same schema return the first upload
    instead of creating (and paying to process) a duplicate. A failed upload is retried.
    """
    payload = raw if raw is not None else (text or "").encode()
    digest = hashlib.sha256(payload).hexdigest()
    existing = await db.scalar(
        select(SchemaSource).where(
            SchemaSource.schema_id == schema.id, SchemaSource.content_hash == digest
        )
    )
    if existing is not None:
        if existing.status != "failed":
            return existing, False
        existing.status, existing.error, existing.processed_at = "pending", None, None
        await db.commit()
        return existing, True
    source = SchemaSource(
        schema_id=schema.id,
        kind=kind,
        filename=filename,
        content_type=content_type,
        content_hash=digest,
        text=text,
        raw=raw,
        status="pending",
    )
    db.add(source)
    try:
        await db.commit()
    except IntegrityError:  # the same file uploaded twice at the same moment
        await db.rollback()
        source = await db.scalar(
            select(SchemaSource).where(
                SchemaSource.schema_id == schema.id, SchemaSource.content_hash == digest
            )
        )
        return source, False
    return source, True


# --- Merging parsed DDL into the database ------------------------------------------


def _apply_column(col: SchemaColumn, ext, *, replace: bool) -> None:
    if replace:  # a CREATE TABLE describes the column completely
        col.name, col.data_type, col.nullable = ext.name, ext.data_type, ext.nullable
        col.is_primary_key, col.is_unique = ext.is_primary_key, ext.is_unique
        col.default, col.comment, col.inferred = ext.default, ext.comment, ext.inferred
        return
    # ALTER / COMMENT statements: only apply what they actually state
    if ext.data_type:
        col.data_type = ext.data_type
    if ext.is_primary_key:
        col.is_primary_key, col.nullable = True, False
    if ext.is_unique:
        col.is_unique = True
    if ext.default is not None:
        col.default = ext.default
    if ext.comment:
        col.comment = ext.comment


def _sync_columns(table: SchemaTable, extracted: ExtractedTable, *, replace: bool) -> None:
    """Update columns in place, matched by name. Reusing the row (instead of deleting it
    and inserting a new one with the same name) avoids tripping UNIQUE(table_id, name):
    within one flush SQLAlchemy runs INSERTs before DELETEs."""
    current = {c.name.lower(): c for c in table.columns}
    if replace:
        ordered = []
        for ext in extracted.columns.values():
            col = current.get(ext.name.lower()) or SchemaColumn()
            _apply_column(col, ext, replace=True)
            ordered.append(col)
    else:
        ordered = list(table.columns)
        for ext in extracted.columns.values():
            col = current.get(ext.name.lower())
            if col is None:  # a column we didn't know: take everything the statement says
                col = SchemaColumn()
                _apply_column(col, ext, replace=True)
                ordered.append(col)
                current[ext.name.lower()] = col
            elif not ext.inferred:  # never overwrite a known column with a guess
                _apply_column(col, ext, replace=False)
    for position, col in enumerate(ordered):
        col.position = position
    table.columns = ordered  # columns no longer listed are deleted (delete-orphan)


def _sync_relationships(table: SchemaTable, extracted: ExtractedTable, *, replace: bool) -> None:
    def signature(cols: list[str], key: str) -> tuple:
        return (tuple(c.lower() for c in cols), key)

    existing = [] if replace else list(table.relationships)
    seen = {signature(r.from_columns, r.to_table_key) for r in existing}
    for fk in extracted.foreign_keys:
        if signature(fk.columns, fk.ref_key) in seen:
            continue
        seen.add(signature(fk.columns, fk.ref_key))
        existing.append(
            SchemaRelationship(
                from_columns=fk.columns,
                to_table_key=fk.ref_key,
                to_table_name=fk.ref_display,
                to_columns=fk.ref_columns,
                name=fk.name,
                inferred=fk.inferred,
            )
        )
    table.relationships = existing


async def merge_extraction(
    db: AsyncSession, schema: DbSchema, source: SchemaSource, result: ExtractionResult
) -> dict:
    tables = list(
        await db.scalars(
            select(SchemaTable)
            .where(SchemaTable.schema_id == schema.id)
            .options(selectinload(SchemaTable.columns), selectinload(SchemaTable.relationships))
        )
    )
    by_key = {t.key: t for t in tables}
    created = updated = 0
    for extracted in result.tables.values():
        table = by_key.get(extracted.key)
        if table is not None and extracted.origin == "inferred" and not table.inferred:
            _sync_relationships(table, extracted, replace=False)  # keep DDL, add join hints
            continue
        if table is None:
            table = SchemaTable(
                schema_id=schema.id,
                key=extracted.key,
                name=extracted.name,
                db_schema=extracted.db_schema,
                inferred=extracted.origin != "declared",
                columns=[],
                relationships=[],
            )
            db.add(table)
            by_key[extracted.key] = table
            created += 1
        else:
            updated += 1
        replace = extracted.origin == "declared"
        if replace:
            table.name, table.db_schema = extracted.name, extracted.db_schema
            table.comment, table.inferred = extracted.comment, False
        elif extracted.comment:
            table.comment = extracted.comment
        table.source_id = source.id
        _sync_columns(table, extracted, replace=replace)
        _sync_relationships(table, extracted, replace=replace)
    schema.updated_at = utcnow()
    await db.commit()
    return {**result.stats(), "tables_created": created, "tables_updated": updated}


# --- Prompt context -------------------------------------------------------------------


@dataclass
class SchemaContext:
    """The part of a schema we show the LLM, plus what we need to check its answer."""

    schema_id: uuid.UUID
    schema_name: str
    text: str
    tables: list[str]  # table names included in `text`
    truncated: bool
    catalog: SchemaCatalog = field(repr=False)


def render_table_card(table: SchemaTable) -> str:
    """A compact, DDL-like description of one table: what the model reads."""
    name = f"{table.db_schema}.{table.name}" if table.db_schema else table.name
    header = f"TABLE {name}"
    if table.inferred:
        header += "  -- inferred from queries: column types unknown"
    if table.comment:
        header += f"  -- {table.comment}"
    single_fks = {
        rel.from_columns[0].lower(): f"-> {rel.to_table_name}({', '.join(rel.to_columns)})"
        for rel in table.relationships
        if len(rel.from_columns) == 1
    }
    lines = [header]
    for col in table.columns:
        parts = [f"  {col.name}", col.data_type or "?"]
        if col.is_primary_key:
            parts.append("PRIMARY KEY")
        elif not col.nullable:
            parts.append("NOT NULL")
        if col.is_unique and not col.is_primary_key:
            parts.append("UNIQUE")
        if col.name.lower() in single_fks:
            parts.append(single_fks[col.name.lower()])
        line = " ".join(parts)
        lines.append(f"{line}  -- {col.comment}" if col.comment else line)
    for rel in table.relationships:
        if len(rel.from_columns) > 1:
            lines.append(
                f"  FOREIGN KEY ({', '.join(rel.from_columns)}) -> "
                f"{rel.to_table_name}({', '.join(rel.to_columns)})"
            )
    return "\n".join(lines)


async def build_context(
    db: AsyncSession, user_id: uuid.UUID, schema_id: uuid.UUID, table_names: list[str] | None
) -> SchemaContext:
    schema = await get_owned(db, user_id, schema_id, with_tables=True)
    if not schema.tables:
        raise BadRequestError("This schema has no tables yet. Upload its DDL first.")
    catalog = SchemaCatalog()
    for t in schema.tables:
        catalog.add(t.db_schema, t.name, {c.name for c in t.columns})

    if table_names:
        resolver = _Resolver(schema.tables)
        wanted, unknown = [], []
        for name in dict.fromkeys(table_names):
            table = resolver.find(name)
            (wanted.append(table) if table else unknown.append(name))
        if unknown:
            raise BadRequestError(f"Unknown tables in this schema: {', '.join(unknown)}.")
    else:
        wanted = list(schema.tables)

    cards, used = [], 0
    for table in wanted:  # stop when the character budget is spent
        card = render_table_card(table)
        if cards and used + len(card) > settings.schema_context_max_chars:
            break
        cards.append(card)
        used += len(card) + 2
    omitted = len(wanted) - len(cards)
    text = "\n\n".join(cards)
    if omitted:
        text += f"\n\n-- {omitted} more tables not shown (the user can select the ones needed)."
    return SchemaContext(
        schema_id=schema.id,
        schema_name=schema.name,
        text=text,
        tables=[t.name for t in wanted[: len(cards)]],
        truncated=omitted > 0,
        catalog=catalog,
    )
