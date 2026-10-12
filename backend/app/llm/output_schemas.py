"""What the LLM must return: structured-output contracts.

Not to be confused with app/schemas/, which describe our HTTP API. These classes are
converted to JSON Schema and sent to the model; with Groq's strict mode the decoder
can only produce JSON that matches them. The class docstring and every Field
description are part of that schema, so they double as instructions to the model.
Strict mode also requires every field to be required (no defaults).
"""

from pydantic import BaseModel, Field


class SQLAnswer(BaseModel):
    """SQL produced for the user's request, plus what a reviewer needs to trust it."""

    sql: str = Field(description="The complete SQL, ready to run. Plain SQL, no markdown fences.")
    explanation: str = Field(
        description="One to three sentences: what the query does, or what was fixed or changed."
    )
    assumptions: list[str] = Field(
        description="Every guess about table names, column names or data meaning. Empty if none."
    )
    tables_used: list[str] = Field(description="Every table the SQL reads from or writes to.")


class TableDescription(BaseModel):
    """Search-index metadata for one table."""

    table: str = Field(description="The table name exactly as written after TABLE.")
    description: str = Field(
        description="One plain-English sentence: what one row represents and what the "
        "table is used for, naming its key measures or dates."
    )
    synonyms: list[str] = Field(
        description="2 to 6 other words or short phrases business users would use for this "
        "data (e.g. 'purchases' for orders). Lowercase; not just the table name again."
    )


class TableDescriptions(BaseModel):
    """One entry for every table in the schema block, in the same order."""

    tables: list[TableDescription]
