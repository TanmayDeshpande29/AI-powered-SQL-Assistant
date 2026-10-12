"""API shapes for uploaded database schemas (Phase 2)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourceKind = Literal["sql_text", "sql_file", "image"]
SourceStatus = Literal["pending", "processing", "ready", "failed"]
SchemaStatus = Literal["empty", "processing", "ready"]

MAX_PASTED_SQL_CHARS = 1_000_000


class SchemaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dialect: str = Field(default="PostgreSQL", max_length=40)
    description: str | None = Field(default=None, max_length=2000)


class SchemaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    dialect: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)


class SourceTextCreate(BaseModel):
    sql: str = Field(min_length=1, max_length=MAX_PASTED_SQL_CHARS)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    filename: str | None
    status: SourceStatus
    error: str | None
    warnings: list[str] | None
    stats: dict[str, Any] | None
    model: str | None  # the vision model, for images
    transcription: str | None = None  # what the vision model read (images only)
    created_at: datetime
    processed_at: datetime | None


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    data_type: str | None
    nullable: bool
    is_primary_key: bool
    is_unique: bool
    default: str | None
    comment: str | None
    inferred: bool


class RelationshipRead(BaseModel):
    columns: list[str]
    to_table: str  # as written in the DDL
    to_columns: list[str]
    to_table_id: uuid.UUID | None  # None if the target table hasn't been uploaded (yet)
    name: str | None
    inferred: bool


class TableRead(BaseModel):
    id: uuid.UUID
    name: str
    db_schema: str | None
    comment: str | None
    inferred: bool
    columns: list[ColumnRead]
    relationships: list[RelationshipRead]


class SchemaSummary(BaseModel):
    id: uuid.UUID
    name: str
    dialect: str
    description: str | None
    status: SchemaStatus
    table_count: int
    column_count: int
    created_at: datetime
    updated_at: datetime


class SchemaDetail(SchemaSummary):
    tables: list[TableRead]
