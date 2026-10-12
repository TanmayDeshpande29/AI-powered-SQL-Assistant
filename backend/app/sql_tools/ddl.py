"""Turn SQL text into a normalized schema: tables, columns, keys and comments.

It accepts what people actually have:
  * DDL dumps: pg_dump --schema-only, mysqldump --no-data, SSMS "Script table as"
  * loose CREATE TABLE / ALTER TABLE / COMMENT ON statements
  * plain queries (SELECT ... JOIN ...): tables, columns and joins are *inferred*

Pipeline: preprocess -> split into statements -> parse each one with sqlglot -> walk
the AST (abstract syntax tree). A statement that fails to parse only adds a warning;
everything else still counts.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import ParseError, TokenError
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.tokens import TokenType

from app.sql_tools.catalog import table_key
from app.sql_tools.validation import to_sqlglot_dialect

MAX_WARNINGS = 25

# Statements we recognise by their first keyword and skip without parsing.
DATA_KEYWORDS = {"INSERT", "COPY", "REPLACE", "LOAD", "MERGE", "UPDATE", "DELETE"}
SKIP_KEYWORDS = {
    "SET", "USE", "BEGIN", "COMMIT", "ROLLBACK", "START", "LOCK", "UNLOCK", "GRANT",
    "REVOKE", "ANALYZE", "VACUUM", "SELECT_SETVAL", "DROP", "PRINT", "DECLARE", "EXEC",
}  # fmt: skip

_GO = re.compile(r"^\s*GO\s*\d*\s*$", re.IGNORECASE | re.MULTILINE)  # SQL Server batch end
_COPY_DATA = re.compile(r"^COPY\b[^\n]*FROM stdin;\n.*?^\\\.[ \t]*$", re.MULTILINE | re.DOTALL)
_DELIMITER = re.compile(r"^\s*DELIMITER\s+\S+\s*$", re.IGNORECASE | re.MULTILINE)  # mysql CLI
_LEADING_COMMENTS = re.compile(r"^\s*(?:(?:--[^\n]*|#[^\n]*)\n|/\*.*?\*/)\s*", re.DOTALL)


@dataclass
class ExtractedColumn:
    name: str
    data_type: str | None = None
    nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default: str | None = None
    comment: str | None = None
    inferred: bool = False


@dataclass
class ExtractedForeignKey:
    columns: list[str]
    ref_db_schema: str | None
    ref_table: str
    ref_columns: list[str]
    name: str | None = None
    inferred: bool = False

    @property
    def ref_key(self) -> str:
        return table_key(self.ref_db_schema, self.ref_table)

    @property
    def ref_display(self) -> str:
        return f"{self.ref_db_schema}.{self.ref_table}" if self.ref_db_schema else self.ref_table

    def signature(self) -> tuple:
        return (tuple(c.lower() for c in self.columns), self.ref_key)


@dataclass
class ExtractedTable:
    name: str
    db_schema: str | None = None
    columns: dict[str, ExtractedColumn] = field(default_factory=dict)  # lower name -> column
    foreign_keys: list[ExtractedForeignKey] = field(default_factory=list)
    comment: str | None = None
    # How we know about the table:
    #   "declared" - from its CREATE TABLE: authoritative, replaces what we had before
    #   "altered"  - only ALTER TABLE / COMMENT ON statements: adds to an existing table
    #   "inferred" - only seen inside queries: columns guessed, types unknown
    origin: str = "declared"

    @property
    def key(self) -> str:
        return table_key(self.db_schema, self.name)

    @property
    def display_name(self) -> str:
        return f"{self.db_schema}.{self.name}" if self.db_schema else self.name

    def column(self, name: str, *, inferred: bool = False) -> ExtractedColumn:
        col = self.columns.get(name.lower())
        if col is None:
            col = self.columns[name.lower()] = ExtractedColumn(name=name, inferred=inferred)
        return col

    def add_foreign_key(self, fk: ExtractedForeignKey) -> None:
        if all(existing.signature() != fk.signature() for existing in self.foreign_keys):
            self.foreign_keys.append(fk)


@dataclass
class ExtractionResult:
    tables: dict[str, ExtractedTable] = field(default_factory=dict)  # key -> table
    warnings: list[str] = field(default_factory=list)
    statements: Counter = field(default_factory=Counter)
    _suppressed_warnings: int = 0

    def warn(self, message: str) -> None:
        if len(self.warnings) < MAX_WARNINGS:
            self.warnings.append(message)
        else:
            self._suppressed_warnings += 1

    def final_warnings(self) -> list[str]:
        extra = (
            [f"... and {self._suppressed_warnings} more warnings."]
            if self._suppressed_warnings
            else []
        )
        return self.warnings + extra

    def table(self, db_schema: str | None, name: str, *, origin: str) -> ExtractedTable:
        """Get or create a table entry. A CREATE TABLE ("declared") replaces an earlier
        definition of the same table, keeping foreign keys and comments that ALTER /
        COMMENT statements attached before it."""
        key = table_key(db_schema, name)
        existing = self.tables.get(key)
        if origin == "declared":
            fresh = ExtractedTable(name=name, db_schema=db_schema or None)
            if existing and existing.origin != "declared":
                fresh.comment = existing.comment
                for fk in existing.foreign_keys:
                    fresh.add_foreign_key(fk)
            self.tables[key] = fresh
            return fresh
        if existing is None:
            existing = self.tables[key] = ExtractedTable(
                name=name, db_schema=db_schema or None, origin=origin
            )
        return existing

    def stats(self) -> dict[str, Any]:
        tables = list(self.tables.values())
        return {
            "tables": sum(t.origin == "declared" for t in tables),
            "altered_tables": sum(t.origin == "altered" for t in tables),
            "inferred_tables": sum(t.origin == "inferred" for t in tables),
            "columns": sum(len(t.columns) for t in tables),
            "foreign_keys": sum(len(t.foreign_keys) for t in tables),
            "statements": dict(self.statements),
        }


# --- Preprocessing and splitting ------------------------------------------------


def preprocess(sql: str) -> str:
    sql = sql.lstrip("﻿").replace("\r\n", "\n")  # BOM, Windows line endings
    sql = _COPY_DATA.sub("", sql)  # pg_dump data blocks are not SQL
    sql = _GO.sub(";", sql)  # "GO" separates SQL Server batches
    return _DELIMITER.sub("", sql)


def split_statements(sql: str, dialect: str | None) -> list[str]:
    """Split on real semicolons only: the tokenizer knows which ones sit inside
    strings, comments or quoted names."""
    try:
        tokens = Dialect.get_or_raise(dialect).tokenize(sql)
    except TokenError:
        return [part.strip() for part in sql.split(";") if part.strip()]
    parts, start = [], 0
    for token in tokens:
        if token.token_type == TokenType.SEMICOLON:
            parts.append(sql[start : token.start])
            start = token.end + 1
    parts.append(sql[start:])
    return [part.strip() for part in parts if part.strip()]


def _first_keyword(statement: str) -> str:
    text = statement
    while True:
        stripped = _LEADING_COMMENTS.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    match = re.match(r"\s*([A-Za-z_]+)", text)
    return match.group(1).upper() if match else ""


def _parse(statement: str, dialect: str | None) -> exp.Expression | None:
    """Parse with the schema's dialect, then with generic SQL as a fallback."""
    for candidate in dict.fromkeys([dialect, None]):
        try:
            parsed = sqlglot.parse_one(statement, read=candidate)
        except (ParseError, TokenError):
            continue
        if parsed is not None and not isinstance(parsed, exp.Command):
            return parsed
    return None


# --- AST helpers ----------------------------------------------------------------


def _names(nodes: list[exp.Expression]) -> list[str]:
    names = []
    for node in nodes or []:
        if isinstance(node, exp.Ordered):
            node = node.this
        names.append(node.name)
    return [n for n in names if n]


def _string(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    return node.this if isinstance(node, exp.Literal) else node.sql()


def _reference(ref: exp.Reference, columns: list[str], name: str | None) -> ExtractedForeignKey:
    target = ref.this
    if isinstance(target, exp.Schema):
        table_node, ref_columns = target.this, _names(target.expressions)
    else:
        table_node, ref_columns = target, []
    return ExtractedForeignKey(
        columns=columns,
        ref_db_schema=table_node.db or None,
        ref_table=table_node.name,
        ref_columns=ref_columns,
        name=name,
    )


# --- Statement readers ----------------------------------------------------------


class _Reader:
    def __init__(self, result: ExtractionResult, dialect: str | None) -> None:
        self.result = result
        self.dialect = dialect

    def create_table(self, stmt: exp.Create) -> None:
        target = stmt.this
        if not isinstance(target, exp.Schema):  # CREATE TABLE x AS SELECT ... / LIKE
            table_node = target if isinstance(target, exp.Table) else stmt.find(exp.Table)
            if table_node is not None:
                self.result.table(table_node.db, table_node.name, origin="declared")
                self.result.warn(
                    f"{table_node.name}: created from a query (CREATE TABLE ... AS), "
                    "so its columns are unknown."
                )
            return
        table_node = target.this
        table = self.result.table(table_node.db, table_node.name, origin="declared")
        for item in target.expressions:
            if isinstance(item, exp.ColumnDef):
                self.column(table, item)
            else:
                self.table_constraint(table, item)
        properties = stmt.args.get("properties")
        for prop in properties.expressions if properties else []:
            if isinstance(prop, exp.SchemaCommentProperty):  # MySQL: COMMENT='...'
                table.comment = _string(prop.this)
        self.result.statements["create_table"] += 1

    def column(self, table: ExtractedTable, coldef: exp.ColumnDef) -> None:
        col = table.column(coldef.name)
        kind = coldef.args.get("kind")
        col.data_type = kind.sql(dialect=self.dialect) if kind else None
        for constraint in coldef.args.get("constraints") or []:
            c = constraint.args.get("kind")
            if isinstance(c, exp.NotNullColumnConstraint):
                col.nullable = bool(c.args.get("allow_null"))  # "NULL" is allow_null=True
            elif isinstance(c, exp.PrimaryKeyColumnConstraint):
                col.is_primary_key, col.nullable = True, False
            elif isinstance(c, exp.UniqueColumnConstraint):
                col.is_unique = True
            elif isinstance(c, exp.DefaultColumnConstraint):
                if not isinstance(c.this, exp.Null):  # MySQL dumps write "DEFAULT NULL"
                    col.default = c.this.sql(dialect=self.dialect)
            elif isinstance(c, exp.CommentColumnConstraint):
                col.comment = _string(c.this)
            elif isinstance(c, exp.Reference):  # inline: customer_id INT REFERENCES customers(id)
                table.add_foreign_key(_reference(c, [coldef.name], None))
            elif isinstance(
                c, exp.GeneratedAsIdentityColumnConstraint | exp.AutoIncrementColumnConstraint
            ):
                col.default = col.default or "auto-generated"

    def table_constraint(
        self, table: ExtractedTable, item: exp.Expression, name: str | None = None
    ) -> None:
        if isinstance(item, exp.Constraint):  # CONSTRAINT <name> PRIMARY KEY / FOREIGN KEY ...
            for inner in item.expressions:
                self.table_constraint(table, inner, item.this.name if item.this else None)
        elif isinstance(item, exp.PrimaryKey):
            for column_name in _names(item.expressions):
                col = table.column(column_name)
                col.is_primary_key, col.nullable = True, False
        elif isinstance(item, exp.ForeignKey):
            reference = item.args.get("reference")
            if reference is not None:
                table.add_foreign_key(_reference(reference, _names(item.expressions), name))
        elif isinstance(item, exp.UniqueColumnConstraint):
            columns = _names(item.this.expressions) if isinstance(item.this, exp.Schema) else []
            if len(columns) == 1:  # a multi-column UNIQUE doesn't make each column unique
                table.column(columns[0]).is_unique = True

    def alter_table(self, stmt: exp.Alter) -> None:
        table_node = stmt.this
        table = self.result.table(table_node.db, table_node.name, origin="altered")
        for action in stmt.args.get("actions") or []:
            if isinstance(action, exp.AddConstraint):
                for constraint in action.expressions:
                    self.table_constraint(table, constraint)
            elif isinstance(action, exp.ColumnDef):  # ALTER TABLE ... ADD COLUMN
                self.column(table, action)
        self.result.statements["alter_table"] += 1

    def comment(self, stmt: exp.Comment) -> None:
        kind = (stmt.args.get("kind") or "").upper()
        text = _string(stmt.args.get("expression"))
        target = stmt.this
        if kind == "TABLE" and isinstance(target, exp.Table):
            self.result.table(target.db, target.name, origin="altered").comment = text
        elif kind == "COLUMN" and isinstance(target, exp.Column) and target.table:
            table = self.result.table(target.db or None, target.table, origin="altered")
            table.column(target.name).comment = text
        self.result.statements["comment"] += 1

    def query(self, stmt: exp.Expression) -> None:
        """Infer tables, columns and joins from a query (sqlglot "scopes" map each
        alias in a SELECT to its real table and leave CTEs/subqueries out)."""
        try:
            scopes = list(traverse_scope(stmt))
        except Exception:  # noqa: BLE001 - unusual SQL: inference is best effort
            self.result.warn("A query could not be analysed for tables and columns.")
            return
        self.result.statements["query"] += 1
        for scope in scopes:
            real = {a: s for a, s in scope.sources.items() if isinstance(s, exp.Table)}
            tables = {
                a: self.result.table(s.db, s.name, origin="inferred") for a, s in real.items()
            }
            projection_aliases = set()
            if isinstance(scope.expression, exp.Select):
                projection_aliases = {
                    e.alias.lower()
                    for e in scope.expression.expressions
                    if isinstance(e, exp.Alias)
                }
            for col in scope.columns:
                if col.table:
                    table = tables.get(col.table)
                elif len(scope.sources) == 1 and len(tables) == 1:
                    table = next(iter(tables.values()))
                else:
                    table = None  # unqualified column with several tables in scope: ambiguous
                if table is not None and col.name.lower() not in projection_aliases:
                    self._inferred_column(table, col.name)
            self._joins(scope, tables)

    def _inferred_column(self, table: ExtractedTable, name: str) -> None:
        if table.origin == "inferred":  # never add guesses to a table we have DDL for
            table.column(name, inferred=True)

    def _joins(self, scope, tables: dict[str, ExtractedTable]) -> None:
        conditions = [j.args.get("on") for j in scope.expression.args.get("joins") or []]
        conditions.append(scope.expression.args.get("where"))
        for condition in filter(None, conditions):
            for eq in condition.find_all(exp.EQ):
                left, right = eq.left, eq.right
                if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                    continue
                a, b = tables.get(left.table), tables.get(right.table)
                if a is None or b is None or a is b:
                    continue
                # Direction guess: the side named "id" is the referenced (parent) key.
                if left.name.lower() == "id" and right.name.lower() != "id":
                    (a, left), (b, right) = (b, right), (a, left)
                a.add_foreign_key(
                    ExtractedForeignKey(
                        columns=[left.name],
                        ref_db_schema=b.db_schema,
                        ref_table=b.name,
                        ref_columns=[right.name],
                        inferred=True,
                    )
                )
                self._inferred_column(a, left.name)
                self._inferred_column(b, right.name)


def extract_schema(sql: str, dialect_label: str) -> ExtractionResult:
    dialect = to_sqlglot_dialect(dialect_label)
    result = ExtractionResult()
    reader = _Reader(result, dialect)
    for statement in split_statements(preprocess(sql), dialect):
        keyword = _first_keyword(statement)
        if not keyword:
            continue  # only comments
        if keyword in DATA_KEYWORDS:
            result.statements["data_skipped"] += 1
            continue
        if keyword in SKIP_KEYWORDS:
            result.statements["ignored"] += 1
            continue
        parsed = _parse(statement, dialect)
        if parsed is None:
            preview = " ".join(statement.split())[:70]
            result.warn(f"Skipped a statement that could not be parsed: {preview}...")
            result.statements["failed"] += 1
        elif isinstance(parsed, exp.Create) and (parsed.args.get("kind") or "").upper() == "TABLE":
            reader.create_table(parsed)
        elif isinstance(parsed, exp.Alter):
            reader.alter_table(parsed)
        elif isinstance(parsed, exp.Comment):
            reader.comment(parsed)
        elif isinstance(parsed, exp.Query):  # SELECT, UNION, WITH ... SELECT
            reader.query(parsed)
        elif isinstance(parsed, exp.Create) and (parsed.args.get("kind") or "").upper() == "VIEW":
            result.statements["view"] += 1
            result.warn(f"View {parsed.this.sql()} is not imported yet (views come later).")
        else:
            result.statements["ignored"] += 1
    return result
