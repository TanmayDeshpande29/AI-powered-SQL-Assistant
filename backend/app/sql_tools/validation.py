"""Syntax validation of SQL with sqlglot.

sqlglot parses SQL text into an AST (abstract syntax tree): a tree of typed nodes
(Select -> From -> Table ...). If the text cannot be parsed, it is not valid SQL for
that dialect, and we can say where it broke.

This is a SYNTAX check only. sqlglot does not know your tables, so a query on a table
that doesn't exist still "passes". Checking names against the real schema arrives
with schema ingestion (Phase 2) and the Validator agent (Phase 6).
"""

import sqlglot
from sqlglot.errors import ParseError, TokenError

from app.schemas.llm import SQLValidation

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


def validate_sql(sql: str, dialect_label: str) -> SQLValidation:
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
    # node.key is the statement kind: "select", "union", "insert", "delete", "create"...
    return SQLValidation(
        valid=True, dialect=dialect, statement_types=[e.key.upper() for e in expressions]
    )
