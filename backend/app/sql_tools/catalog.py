"""How table names are matched, shared by the parser, the database merge and validation.

SQL identifiers are case-insensitive unless quoted, and a table may be written with or
without its namespace ("sales.orders" vs "orders"; "public.users" vs "users"). One key
function keeps every part of the app matching names the same way.
"""

from dataclasses import dataclass, field

# Namespaces that are implied when omitted, so "public.users" and "users" match.
DEFAULT_NAMESPACES = {"public", "dbo", "main"}


def table_key(db_schema: str | None, name: str) -> str:
    namespace = (db_schema or "").strip().lower()
    if namespace in DEFAULT_NAMESPACES:
        namespace = ""
    bare = name.strip().lower()
    return f"{namespace}.{bare}" if namespace else bare


@dataclass
class SchemaCatalog:
    """Which tables and columns exist: lower-cased names, for reference checks."""

    tables: dict[str, set[str]] = field(default_factory=dict)  # key -> column names
    _by_name: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def add(self, db_schema: str | None, name: str, columns: set[str]) -> None:
        key = table_key(db_schema, name)
        self.tables[key] = {c.lower() for c in columns}
        self._by_name.setdefault(name.strip().lower(), []).append(key)

    def lookup(self, db_schema: str | None, name: str) -> set[str] | None:
        """Columns of the table, or None if no such table. Without a namespace, a
        bare name matches when exactly one table has it (e.g. "orders" -> "sales.orders")."""
        key = table_key(db_schema, name)
        if key in self.tables:
            return self.tables[key]
        if not db_schema:
            candidates = self._by_name.get(name.strip().lower(), [])
            if len(candidates) == 1:
                return self.tables[candidates[0]]
        return None
