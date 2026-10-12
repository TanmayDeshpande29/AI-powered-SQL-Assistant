"""Validation of SQL with sqlglot, in two layers.

1. Syntax: sqlglot parses SQL text into an AST (abstract syntax tree), a tree of typed
   nodes (Select -> From -> Table ...). If the text cannot be parsed, it is not valid
   SQL for that dialect, and we can say where it broke.
2. Schema references (Phase 2): when we know the user's schema, every table and column
   the query uses is looked up in it. "Unknown column orders.amount" is exactly the
   hallucination that schema grounding is meant to prevent, so we check, not hope.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError
from sqlglot.optimizer.scope import traverse_scope

from app.schemas.llm import SQLValidation
from app.sql_tools.catalog import SchemaCatalog

# UI dialect labels -> sqlglot dialect names (unknown labels fall back to generic SQL).
DIALECT_ALIASES = {
    "postgresql": "postgres",
    "postgres": "postgres",
    "mysql": "mysql",
    "mariadb": "mysql",
    "sqlite": "sqlite",
    "sql server": "tsql",
    "mssql": "tsql",
    "t-sql": "tsql",
    "oracle": "oracle",
    "trino": "trino",
    "trino sql": "trino",
    "presto": "presto",
    "spark sql": "spark",
    "spark": "spark",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "redshift": "redshift",
    "duckdb": "duckdb",
}

MAX_ERRORS = 5


def to_sqlglot_dialect(label: str) -> str | None:
    return DIALECT_ALIASES.get(label.strip().lower())


def validate_sql(
    sql: str, dialect_label: str, catalog: SchemaCatalog | None = None
) -> SQLValidation:
    dialect = to_sqlglot_dialect(dialect_label)
    try:
        expressions = [e for e in sqlglot.parse(sql, read=dialect) if e is not None]
    except ParseError as exc:
        errors = [
            f"Line {err.get('line')}, column {err.get('col')}: {err.get('description')}"
            for err in exc.errors[:MAX_ERRORS]
        ] or [str(exc)]
        return SQLValidation(valid=False, dialect=dialect, errors=errors)
    except TokenError as exc:  # e.g. an unterminated string literal
        return SQLValidation(valid=False, dialect=dialect, errors=[str(exc)])

    if not expressions:
        return SQLValidation(valid=False, dialect=dialect, errors=["No SQL statement found."])
    issues: list[str] = []
    if catalog is not None:
        for expression in expressions:
            issues.extend(check_schema_references(expression, catalog))
    # node.key is the statement kind: "select", "union", "insert", "delete", "create"...
    return SQLValidation(
        valid=True,
        dialect=dialect,
        statement_types=[e.key.upper() for e in expressions],
        schema_checked=catalog is not None,
        schema_issues=sorted(set(issues)),
    )


def check_schema_references(expression: exp.Expression, catalog: SchemaCatalog) -> list[str]:
    """Tables and columns used by a parsed query that the schema doesn't have.

    Uses sqlglot scopes: each SELECT (and each CTE / subquery) is a scope whose
    `sources` map aliases to real tables or to derived tables. Only real tables are
    checked. Columns of CTEs/subqueries and SELECT aliases are left alone.
    """
    issues: list[str] = []
    try:
        scopes = list(traverse_scope(expression))
    except Exception:  # noqa: BLE001 - unusual statements (e.g. DDL): nothing to check
        return issues
    for scope in scopes:
        known: dict[str, set[str] | None] = {}  # alias -> columns (None = unknown table)
        for alias, source in scope.sources.items():
            if isinstance(source, exp.Table):
                columns = catalog.lookup(source.db or None, source.name)
                if columns is None:
                    issues.append(f"Unknown table: {source.name}")
                known[alias] = columns
        aliases = set()
        if isinstance(scope.expression, exp.Select):
            aliases = {
                e.alias.lower() for e in scope.expression.expressions if isinstance(e, exp.Alias)
            }
        for col in scope.columns:
            name = col.name.lower()
            if col.table:
                columns = known.get(col.table)
                if columns is not None and name not in columns:
                    issues.append(f"Unknown column: {col.table}.{col.name}")
            elif name not in aliases and known and len(known) == len(scope.sources):
                # Unqualified, and every source is a real table we know: it must exist in one.
                tables_columns = [c for c in known.values() if c is not None]
                if len(tables_columns) == len(known) and not any(name in c for c in tables_columns):
                    issues.append(f"Unknown column: {col.name}")
    return issues
