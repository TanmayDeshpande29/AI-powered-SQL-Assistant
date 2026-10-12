// SQL dialects offered in every dropdown. The values must be labels the backend
// understands (DIALECT_ALIASES in backend/app/sql_tools/validation.py): they choose the
// parser for uploaded schemas and the syntax check of generated SQL.
export const SQL_DIALECTS = [
  { value: "PostgreSQL", label: "PostgreSQL", icon: "🐘" },
  { value: "MySQL", label: "MySQL", icon: "🐬" },
  { value: "SQLite", label: "SQLite", icon: "🪶" },
  { value: "SQL Server", label: "SQL Server", icon: "🏢" },
  { value: "Oracle", label: "Oracle", icon: "🔴" },
  { value: "Snowflake", label: "Snowflake", icon: "❄️" },
  { value: "BigQuery", label: "BigQuery", icon: "🔎" },
  { value: "Trino", label: "Trino", icon: "⚡" },
  { value: "Spark SQL", label: "Spark SQL", icon: "✨" },
]

export const isKnownDialect = (value) => SQL_DIALECTS.some((d) => d.value === value)
