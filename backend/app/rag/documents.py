"""The "search document" of a table: the text we turn into vectors.

One table = one document (structure-aware chunking: never split a table in half).
It is written for retrieval, not for the SQL prompt:
  * names first, then the LLM-written description and synonyms (meaning)
  * every identifier also spelled out as words: the BM25 tokenizer keeps "customer_id"
    as ONE token, so a question about "customer" would never match it otherwise
  * relationships in both directions ("References" / "Referenced by"), so a question
    about orders can also surface the tables joined to them
  * no data types: they add little meaning and waste the model's 512-token window

    Table: sales.orders (orders)
    About: One row per customer order, with its status and total amount.
    Synonyms: purchases, sales, transactions
    Columns: id, customer_id (customer id), ordered_at (ordered at), total -- Gross amount incl. tax
    References: sales.customers
    Referenced by: sales.order_items, sales.payments
"""

import hashlib
import re

from app.models import SchemaTable

# Bump when the document format changes: every table's fingerprint changes with it,
# so the next indexing run re-embeds everything.
DOC_FORMAT_VERSION = 1
# bge-small reads at most 512 tokens (~2,000 characters of this text); the rest is cut.
MAX_DOC_CHARS = 2_000

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[_\W\d]+")


def identifier_words(name: str) -> str:
    """'customer_id' -> 'customer id', 'unitPrice' -> 'unit price', 'orders' -> ''.

    Empty when the words add nothing beyond the name itself.
    """
    words = " ".join(w for w in _SEPARATORS.split(_CAMEL.sub(" ", name).lower()) if w)
    return "" if words == name.lower() else words


def qualified_name(table: SchemaTable) -> str:
    return f"{table.db_schema}.{table.name}" if table.db_schema else table.name


def _named(name: str) -> str:
    words = identifier_words(name)
    return f"{name} ({words})" if words else name


def table_document(table: SchemaTable, referenced_by: list[str]) -> str:
    lines = [f"Table: {qualified_name(table)}"]
    words = identifier_words(table.name)
    if words:
        lines[0] += f" ({words})"
    if table.description:
        lines.append(f"About: {table.description}")
    if table.comment:
        lines.append(f"Comment: {table.comment}")
    if table.synonyms:
        lines.append(f"Synonyms: {', '.join(table.synonyms)}")
    if table.inferred:
        lines.append("Note: seen only in queries, columns are partial")

    columns = []
    for col in table.columns:
        entry = _named(col.name)
        columns.append(f"{entry} -- {col.comment}" if col.comment else entry)
    references = sorted({rel.to_table_name for rel in table.relationships})
    tail = []
    if references:
        tail.append(f"References: {', '.join(references)}")
    if referenced_by:
        tail.append(f"Referenced by: {', '.join(sorted(referenced_by))}")

    # Keep the start (name + meaning) and the relationships; trim columns to fit,
    # reserving room for the "... and N more columns" marker itself.
    marker_room = len(", ... and 99999 more columns")
    budget = (
        MAX_DOC_CHARS
        - sum(len(line) + 1 for line in lines + tail)
        - len("Columns: ")
        - marker_room
    )
    kept, used = [], 0
    for i, entry in enumerate(columns):
        if used + len(entry) + 2 > budget:
            kept.append(f"... and {len(columns) - i} more columns")
            break
        kept.append(entry)
        used += len(entry) + 2
    if kept:
        lines.append(f"Columns: {', '.join(kept)}")
    return "\n".join(lines + tail)


def fingerprint(*parts: str) -> str:
    """sha256 of the parts: equal fingerprints = nothing to redo."""
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def index_fingerprint(document: str, dense_model: str, sparse_model: str) -> str:
    # The models are part of it: switching models must re-embed everything.
    return fingerprint(f"doc-v{DOC_FORMAT_VERSION}", dense_model, sparse_model, document)
