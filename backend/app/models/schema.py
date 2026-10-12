"""A user's database schemas, as SQLAssist understands them (Phase 2).

    DbSchema            one "database" the user describes (e.g. "Shop production")
      ├─ SchemaSource   every upload: pasted SQL, a .sql file or a screenshot (a job)
      └─ SchemaTable    normalized tables, merged from all sources
           ├─ SchemaColumn        name, type, nullability, keys, comment
           └─ SchemaRelationship  foreign keys (declared, or inferred from joins)

Relationships point at their target by *key* ("sales.customers"), not by row id, so
uploads can arrive in any order: a FK may reference a table that a later upload adds.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User

# JSONB on PostgreSQL, plain JSON elsewhere (the SQLite test database).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class DbSchema(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "db_schemas"
    __table_args__ = (UniqueConstraint("user_id", "name"),)  # names are unique per user

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    dialect: Mapped[str] = mapped_column(String(40))  # UI label, e.g. "PostgreSQL"
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship()
    sources: Mapped[list["SchemaSource"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan", passive_deletes=True
    )
    tables: Mapped[list["SchemaTable"]] = relationship(
        back_populates="schema",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SchemaTable.name",
    )


class SchemaSource(UUIDPrimaryKeyMixin, Base):
    """One upload, processed in the background: pending -> processing -> ready | failed."""

    __tablename__ = "schema_sources"
    __table_args__ = (
        # Idempotency: uploading the exact same bytes twice returns the first upload.
        UniqueConstraint("schema_id", "content_hash"),
        Index("ix_schema_sources_schema_id_created_at", "schema_id", "created_at"),
    )

    schema_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("db_schemas.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # sql_text | sql_file | image
    filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex of the uploaded bytes
    # SQL text: what was pasted / the decoded file / the vision model's transcription.
    text: Mapped[str | None] = mapped_column(Text)
    # Original image bytes, kept so a better vision model can re-read them later.
    # (Fine at this scale; object storage such as S3/MinIO is the production answer.)
    raw: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list[str] | None] = mapped_column(JSONType)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    model: Mapped[str | None] = mapped_column(String(100))  # vision model, for images
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schema: Mapped["DbSchema"] = relationship(back_populates="sources")


class SchemaTable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schema_tables"
    __table_args__ = (UniqueConstraint("schema_id", "key"),)

    schema_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("db_schemas.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schema_sources.id", ondelete="SET NULL")
    )
    db_schema: Mapped[str | None] = mapped_column(String(128))  # namespace: "sales", "dbo"...
    name: Mapped[str] = mapped_column(String(128))
    # Lower-cased lookup key, "sales.orders" or "orders" (default namespaces dropped).
    key: Mapped[str] = mapped_column(String(260))
    comment: Mapped[str | None] = mapped_column(Text)
    # True when we only saw the table used in queries (types unknown), not its CREATE TABLE.
    inferred: Mapped[bool] = mapped_column(Boolean, default=False)

    schema: Mapped["DbSchema"] = relationship(back_populates="tables")
    columns: Mapped[list["SchemaColumn"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SchemaColumn.position",
    )
    relationships: Mapped[list["SchemaRelationship"]] = relationship(
        back_populates="from_table", cascade="all, delete-orphan", passive_deletes=True
    )


class SchemaColumn(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "schema_columns"
    __table_args__ = (UniqueConstraint("table_id", "name"),)

    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schema_tables.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str | None] = mapped_column(String(128))  # None when inferred
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    default: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    inferred: Mapped[bool] = mapped_column(Boolean, default=False)

    table: Mapped["SchemaTable"] = relationship(back_populates="columns")


class SchemaRelationship(UUIDPrimaryKeyMixin, Base):
    """A foreign key: from_table(from_columns) -> to_table_key(to_columns)."""

    __tablename__ = "schema_relationships"

    from_table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schema_tables.id", ondelete="CASCADE"), index=True
    )
    from_columns: Mapped[list[str]] = mapped_column(JSONType)
    to_table_key: Mapped[str] = mapped_column(String(260))
    to_table_name: Mapped[str] = mapped_column(String(260))  # as written, for display
    to_columns: Mapped[list[str]] = mapped_column(JSONType)
    name: Mapped[str | None] = mapped_column(String(128))
    inferred: Mapped[bool] = mapped_column(Boolean, default=False)  # guessed from a JOIN

    from_table: Mapped["SchemaTable"] = relationship(back_populates="relationships")
