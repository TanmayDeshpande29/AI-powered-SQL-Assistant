"""The DDL extractor (app/sql_tools/ddl.py) on realistic inputs, and reference checks."""

from app.sql_tools.catalog import SchemaCatalog, table_key
from app.sql_tools.ddl import extract_schema
from app.sql_tools.validation import validate_sql

PG_DUMP = r"""
SET statement_timeout = 0;
CREATE SCHEMA sales;
CREATE TABLE sales.customers (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    country char(2) DEFAULT 'IN',
    CONSTRAINT customers_pkey PRIMARY KEY (id),
    UNIQUE (email)
);
CREATE TABLE sales.orders (id bigserial PRIMARY KEY, customer_id integer, total numeric(10,2));
COPY sales.customers (id, email, country) FROM stdin;
1	a@b.c	IN
2	semi;colon@x.io	US
\.
ALTER TABLE ONLY sales.orders ADD CONSTRAINT orders_customer_fk
    FOREIGN KEY (customer_id) REFERENCES sales.customers(id) ON DELETE CASCADE;
ALTER TABLE sales.orders ADD COLUMN note text;
COMMENT ON TABLE sales.orders IS 'One row per order';
COMMENT ON COLUMN sales.orders.total IS 'Gross amount incl. tax';
CREATE INDEX ix_orders_customer ON sales.orders (customer_id);
INSERT INTO sales.customers VALUES (3, 'q@w.e', 'IN');
"""

MYSQL_DUMP = """
-- MySQL dump 10.13
/*!40101 SET NAMES utf8mb4 */;
CREATE TABLE `products` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT 'display name',
  `sku` varchar(40) NOT NULL,
  `category_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sku` (`sku`),
  CONSTRAINT `fk_cat` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='catalog';
"""

SSMS_SCRIPT = """
CREATE TABLE [dbo].[Invoices] (
  [InvoiceID] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
  [CustomerID] INT NOT NULL,
  [Amount] DECIMAL(12,2) NULL
)
GO
CREATE TABLEE oops (x int)
GO
ALTER TABLE [dbo].[Invoices] ADD CONSTRAINT [FK_Inv_Cust] FOREIGN KEY ([CustomerID])
  REFERENCES [dbo].[Customers]([CustomerID])
GO
"""


def test_pg_dump_tables_keys_comments_and_skipped_statements():
    result = extract_schema(PG_DUMP, "PostgreSQL")
    customers = result.tables["sales.customers"]
    orders = result.tables["sales.orders"]
    assert list(customers.columns) == ["id", "email", "country"]
    assert customers.columns["id"].is_primary_key and not customers.columns["id"].nullable
    assert customers.columns["email"].is_unique
    assert customers.columns["country"].default == "'IN'"
    # FK added later by ALTER TABLE, column added by ALTER, comments by COMMENT ON
    [fk] = orders.foreign_keys
    assert (fk.columns, fk.ref_key, fk.ref_columns, fk.name) == (
        ["customer_id"],
        "sales.customers",
        ["id"],
        "orders_customer_fk",
    )
    assert "note" in orders.columns
    assert orders.comment == "One row per order"
    assert orders.columns["total"].comment == "Gross amount incl. tax"
    # COPY data (with a ';' inside it!) and INSERT are skipped, not parsed or failed
    assert result.statements["data_skipped"] == 1
    assert result.statements.get("failed", 0) == 0


def test_mysql_dump_backticks_inline_comment_and_unique_key():
    products = extract_schema(MYSQL_DUMP, "MySQL").tables["products"]
    assert products.comment == "catalog"
    assert products.columns["name"].comment == "display name"
    assert products.columns["sku"].is_unique
    assert products.columns["category_id"].default is None  # "DEFAULT NULL" = no default
    assert products.foreign_keys[0].ref_key == "categories"


def test_sql_server_go_batches_and_one_broken_statement():
    result = extract_schema(SSMS_SCRIPT, "SQL Server")
    invoices = result.tables["invoices"]  # "dbo" is a default namespace
    assert invoices.columns["invoiceid"].is_primary_key
    assert invoices.foreign_keys[0].ref_display == "dbo.Customers"
    assert result.statements["failed"] == 1  # the typo costs one statement, not the file
    assert result.warnings[0].startswith("Skipped a statement that could not be parsed")


def test_queries_infer_tables_columns_and_joins():
    sql = """
    WITH recent AS (SELECT o.customer_id, SUM(o.total) AS spent FROM orders o GROUP BY 1)
    SELECT c.name, r.spent FROM customers c JOIN recent r ON r.customer_id = c.id;
    SELECT p.method FROM payments p JOIN orders o ON p.order_id = o.id;
    """
    result = extract_schema(sql, "PostgreSQL")
    assert set(result.tables) == {"orders", "customers", "payments"}  # CTE "recent" excluded
    assert all(t.origin == "inferred" for t in result.tables.values())
    assert {"customer_id", "total", "id"} <= set(result.tables["orders"].columns)
    [fk] = result.tables["payments"].foreign_keys
    assert (fk.columns, fk.ref_key, fk.ref_columns, fk.inferred) == (
        ["order_id"],
        "orders",
        ["id"],
        True,
    )


def test_queries_never_add_guesses_to_declared_tables():
    sql = "CREATE TABLE orders (id INT PRIMARY KEY); SELECT o.ghost FROM orders o;"
    orders = extract_schema(sql, "PostgreSQL").tables["orders"]
    assert list(orders.columns) == ["id"]


def test_no_tables_found():
    result = extract_schema("-- just a comment\nSELECT 1;", "PostgreSQL")
    assert result.tables == {}


def test_table_key_normalizes_case_and_default_namespaces():
    assert table_key("public", "Users") == "users"
    assert table_key("dbo", "Orders") == "orders"
    assert table_key("Sales", "Orders") == "sales.orders"


def test_validation_flags_unknown_tables_and_columns():
    catalog = SchemaCatalog()
    catalog.add("sales", "orders", {"id", "customer_id", "total"})
    catalog.add("sales", "customers", {"id", "name"})
    good = validate_sql(
        "SELECT c.name, SUM(o.total) AS revenue FROM customers c "
        "JOIN orders o ON o.customer_id = c.id GROUP BY c.name ORDER BY revenue",
        "PostgreSQL",
        catalog,
    )
    assert good.schema_checked and good.schema_issues == []
    bad = validate_sql(
        "SELECT o.amount, x.y FROM orders o JOIN payments x ON x.order_id = o.id",
        "PostgreSQL",
        catalog,
    )
    assert bad.schema_issues == ["Unknown column: o.amount", "Unknown table: payments"]
    unqualified = validate_sql("SELECT name, phone FROM customers", "PostgreSQL", catalog)
    assert unqualified.schema_issues == ["Unknown column: phone"]
