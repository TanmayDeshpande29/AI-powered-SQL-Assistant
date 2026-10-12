"""Schemas API: CRUD, background ingestion of text / files / screenshots, merging,
idempotency, ownership, and schema-grounded generation."""

from sqlalchemy import update

from app.core.config import settings
from app.llm.output_schemas import SQLAnswer
from app.models import SchemaSource
from app.services.ingestion import recover_interrupted
from tests.conftest import rate_limit_error, signup_and_login

DDL = """
CREATE TABLE customers (id INT PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(255) UNIQUE);
CREATE TABLE orders (
  id INT PRIMARY KEY,
  customer_id INT REFERENCES customers(id),
  total DECIMAL(10,2)
);
COMMENT ON COLUMN orders.total IS 'Order value incl. tax';
"""
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # the magic bytes are all classify_upload looks at


async def make_schema(client, headers, name="Shop", dialect="PostgreSQL"):
    res = await client.post(
        "/api/v1/schemas", json={"name": name, "dialect": dialect}, headers=headers
    )
    assert res.status_code == 201
    return res.json()


async def test_create_list_and_duplicate_name(client):
    _, headers = await signup_and_login(client)
    created = await make_schema(client, headers)
    assert created["status"] == "empty" and created["table_count"] == 0
    duplicate = await client.post("/api/v1/schemas", json={"name": "Shop"}, headers=headers)
    assert duplicate.status_code == 409
    listing = (await client.get("/api/v1/schemas", headers=headers)).json()
    assert [s["name"] for s in listing] == ["Shop"]


async def test_paste_sql_is_processed_in_background(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    assert res.status_code == 202  # accepted: work happens after the response
    source_id = res.json()["id"]

    # The background task has run by now (the test client waits for it).
    source = (
        await client.get(f"/api/v1/schemas/{schema['id']}/sources/{source_id}", headers=headers)
    ).json()
    assert source["status"] == "ready"
    assert source["stats"]["tables"] == 2 and source["stats"]["foreign_keys"] == 1

    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert detail["status"] == "ready" and detail["table_count"] == 2
    tables = {t["name"]: t for t in detail["tables"]}
    [rel] = tables["orders"]["relationships"]
    assert rel["to_table"] == "customers" and rel["to_table_id"] == tables["customers"]["id"]
    total = next(c for c in tables["orders"]["columns"] if c["name"] == "total")
    assert total["comment"] == "Order value incl. tax"


async def test_same_upload_twice_is_idempotent(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    url = f"/api/v1/schemas/{schema['id']}/sources/text"
    first = await client.post(url, json={"sql": DDL}, headers=headers)
    second = await client.post(url, json={"sql": DDL}, headers=headers)
    assert (first.status_code, second.status_code) == (202, 200)
    assert first.json()["id"] == second.json()["id"]


async def test_upload_without_tables_fails_with_a_helpful_message(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text",
        json={"sql": "SELECT 1;"},
        headers=headers,
    )
    source = (
        await client.get(
            f"/api/v1/schemas/{schema['id']}/sources/{res.json()['id']}", headers=headers
        )
    ).json()
    assert source["status"] == "failed"
    assert source["error"].startswith("No tables were found")


async def test_later_upload_replaces_a_table_and_alter_adds_to_it(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    url = f"/api/v1/schemas/{schema['id']}/sources/text"
    await client.post(url, json={"sql": DDL}, headers=headers)
    # New definition of orders (total renamed to amount, status added) ...
    await client.post(
        url,
        json={
            "sql": "CREATE TABLE orders (id INT PRIMARY KEY, amount DECIMAL(10,2), status TEXT);"
        },
        headers=headers,
    )
    # ... then an ALTER that only adds a foreign key to the existing table.
    await client.post(
        url,
        json={
            "sql": "ALTER TABLE orders ADD CONSTRAINT fk FOREIGN KEY (status) "
            "REFERENCES statuses(code);"
        },
        headers=headers,
    )
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    orders = next(t for t in detail["tables"] if t["name"] == "orders")
    assert [c["name"] for c in orders["columns"]] == ["id", "amount", "status"]
    [rel] = orders["relationships"]  # the old customers FK went with the replaced definition
    assert rel["to_table"] == "statuses" and rel["to_table_id"] is None  # not uploaded (yet)


async def test_sql_file_upload_and_unsupported_file(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    url = f"/api/v1/schemas/{schema['id']}/sources/file"
    ok = await client.post(
        url, files={"file": ("dump.sql", DDL.encode(), "application/sql")}, headers=headers
    )
    assert ok.status_code == 202 and ok.json()["kind"] == "sql_file"
    bad = await client.post(
        url, files={"file": ("notes.pdf", b"%PDF-1.7", "application/pdf")}, headers=headers
    )
    assert bad.status_code == 415


async def test_too_large_upload_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "max_sql_upload_bytes", 100)
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/file",
        files={"file": ("big.sql", DDL.encode(), "text/plain")},
        headers=headers,
    )
    assert res.status_code == 413


async def test_screenshot_is_transcribed_by_the_vision_model(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/file",
        files={"file": ("erd.png", PNG, "image/png")},
        headers=headers,
    )
    assert res.status_code == 202 and res.json()["kind"] == "image"
    source = (
        await client.get(
            f"/api/v1/schemas/{schema['id']}/sources/{res.json()['id']}", headers=headers
        )
    ).json()
    assert source["status"] == "ready" and source["model"] == "fake-vision"
    assert source["transcription"].startswith("CREATE TABLE customers")
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert {t["name"] for t in detail["tables"]} == {"customers", "orders"}


async def test_vision_rate_limit_marks_the_upload_failed(client, fake_llm):
    fake_llm.vision.errors = [rate_limit_error("30")]
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/file",
        files={"file": ("erd.png", PNG, "image/png")},
        headers=headers,
    )
    source = (
        await client.get(
            f"/api/v1/schemas/{schema['id']}/sources/{res.json()['id']}", headers=headers
        )
    ).json()
    assert source["status"] == "failed" and "30 s" in source["error"]


async def test_other_users_cannot_see_or_use_a_schema(client):
    _, alice = await signup_and_login(client, "alice@example.com")
    _, bob = await signup_and_login(client, "bob@example.com")
    schema = await make_schema(client, alice)
    assert (await client.get(f"/api/v1/schemas/{schema['id']}", headers=bob)).status_code == 404
    upload = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=bob
    )
    assert upload.status_code == 404
    generate = await client.post(
        "/api/v1/sql/generate",
        json={"question": "all customers", "schema_id": schema["id"]},
        headers=bob,
    )
    assert generate.status_code == 404


async def test_generation_is_grounded_in_the_schema_and_checked(client, fake_llm):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    # The (fake) model answers with a column that doesn't exist: o.amount.
    fake_llm.models["primary"].answer = SQLAnswer(
        sql="SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o "
        "ON o.customer_id = c.id GROUP BY c.name",
        explanation="Revenue per customer.",
        assumptions=[],
        tables_used=["customers", "orders"],
    )
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "revenue per customer", "schema_id": schema["id"]},
        headers=headers,
    )
    body = res.json()
    assert res.status_code == 200
    assert body["schema_tables"] == ["customers", "orders"] and not body["schema_truncated"]
    assert body["validation"]["schema_checked"] is True
    assert body["validation"]["schema_issues"] == ["Unknown column: o.amount"]

    # The prompt contained the schema, inside <schema> tags in the human message.
    system, human = fake_llm.models["primary"].last_messages
    assert "Use ONLY tables and columns" in system.content
    assert "<schema>" in human.content and "TABLE orders" in human.content
    assert "total DECIMAL(10, 2)  -- Order value incl. tax" in human.content

    history = (await client.get("/api/v1/history", headers=headers)).json()["items"][0]
    assert history["schema_id"] == schema["id"]


async def test_selected_tables_only_and_unknown_table_names(client, fake_llm):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "customer names", "schema_id": schema["id"], "tables": ["customers"]},
        headers=headers,
    )
    assert res.json()["schema_tables"] == ["customers"]
    _, human = fake_llm.models["primary"].last_messages
    assert "TABLE customers" in human.content and "TABLE orders" not in human.content

    unknown = await client.post(
        "/api/v1/sql/generate",
        json={"question": "any question", "schema_id": schema["id"], "tables": ["nope"]},
        headers=headers,
    )
    assert unknown.status_code == 400 and "nope" in unknown.json()["error"]["message"]


async def test_large_schema_is_truncated_to_the_prompt_budget(client, monkeypatch):
    monkeypatch.setattr(settings, "schema_context_max_chars", 120)
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "any question", "schema_id": schema["id"]},
        headers=headers,
    )
    assert res.json()["schema_truncated"] is True and len(res.json()["schema_tables"]) == 1


async def test_delete_table_and_schema(client):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    orders_id = next(t["id"] for t in detail["tables"] if t["name"] == "orders")
    gone = await client.delete(
        f"/api/v1/schemas/{schema['id']}/tables/{orders_id}", headers=headers
    )
    assert gone.status_code == 204
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert [t["name"] for t in detail["tables"]] == ["customers"]
    assert (
        await client.delete(f"/api/v1/schemas/{schema['id']}", headers=headers)
    ).status_code == 204
    assert (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).status_code == 404


async def test_startup_recovery_fails_interrupted_uploads(client, session_factory):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    res = await client.post(
        f"/api/v1/schemas/{schema['id']}/sources/text", json={"sql": DDL}, headers=headers
    )
    async with session_factory() as db:  # simulate a crash mid-job
        await db.execute(update(SchemaSource).values(status="processing"))
        await db.commit()
    assert await recover_interrupted(session_factory) == 1
    source = (
        await client.get(
            f"/api/v1/schemas/{schema['id']}/sources/{res.json()['id']}", headers=headers
        )
    ).json()
    assert source["status"] == "failed" and "restart" in source["error"]
