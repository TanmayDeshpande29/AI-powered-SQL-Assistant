# Import every model here so `Base.metadata` knows all tables
# (Alembic autogenerate and test create_all rely on this).
from app.models.query_history import QueryHistory
from app.models.schema import (
    DbSchema,
    SchemaColumn,
    SchemaRelationship,
    SchemaSource,
    SchemaTable,
)
from app.models.user import User

__all__ = [
    "DbSchema",
    "QueryHistory",
    "SchemaColumn",
    "SchemaRelationship",
    "SchemaSource",
    "SchemaTable",
    "User",
]
