# Import every model here so `Base.metadata` knows all tables
# (Alembic autogenerate and test create_all rely on this).
from app.models.query_history import QueryHistory
from app.models.user import User

__all__ = ["QueryHistory", "User"]
