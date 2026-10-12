"""Phase 3: the search index. Enrichment, incremental embedding into Qdrant, search,
tenant isolation, cleanup on delete, and graceful degradation when parts fail."""

import uuid

from sqlalchemy import update

from app.core.exceptions import VectorStoreError
from app.models import DbSchema
from app.rag.documents import identifier_words, table_document
from app.services.ingestion import recover_interrupted
from tests.conftest import rate_limit_error, signup_and_login
from tests.test_schemas_api import DDL, make_schema

PAYMENTS = (
    "CREATE TABLE payments "
    "(id INT PRIMARY KEY, order_id INT REFERENCES orders(id), method VARCHAR(20));"
)


async def upload(client, headers, schema_id, sql=DDL):
    res = await client.post(
        f"/api/v1/schemas/{schema_id}/sources/text", json={"sql": sql}, headers=headers
    )
    assert res.status_code == 202
    # The background job (merge + indexing) has finished when the test client returns.
    return (await client.get(f"/api/v1/schemas/{schema_id}", headers=headers)).json()


async def search(client, headers, schema_id, q, mode="dense", limit=5):
    return await client.get(
        f"/api/v1/schemas/{schema_id}/search",
        params={"q": q, "mode": mode, "limit": limit},
        headers=headers,
    )


async def test_upload_builds_the_index_with_descriptions(client, fake_llm, vector_index):
    fake_llm.models["fast"].synonyms = {"customers": ["clients", "buyers"]}
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    detail = await upload(client, headers, schema["id"])

    assert detail["index_status"] == "ready" and detail["index_error"] is None
    stats = detail["index_stats"]
    assert (stats["tables"], stats["embedded"], stats["enriched"]) == (2, 2, 2)
    customers = next(t for t in detail["tables"] if t["name"] == "customers")
    assert customers["indexed"] is True
    assert customers["description"] == "One row per customers record."
    assert customers["synonyms"] == ["clients", "buyers"]
    assert await vector_index.count(uuid.UUID(schema["id"])) == 2


async def test_reindexing_only_embeds_what_changed(client, fake_embedder):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await upload(client, headers, schema["id"])
    assert fake_embedder.documents_embedded == 2

    # Nothing changed: the fingerprints match, so nothing is described or embedded again.
    res = await client.post(f"/api/v1/schemas/{schema['id']}/index", headers=headers)
    assert res.status_code == 202 and res.json()["index_status"] == "pending"
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert detail["index_status"] == "ready"
    assert (detail["index_stats"]["embedded"], detail["index_stats"]["unchanged"]) == (0, 2)
    assert fake_embedder.documents_embedded == 2

    # A new table that references orders: payments is new, and orders' document gains
    # "Referenced by: payments", so exactly those two are embedded; customers is skipped.
    detail = await upload(client, headers, schema["id"], PAYMENTS)
    assert (detail["index_stats"]["embedded"], detail["index_stats"]["unchanged"]) == (2, 1)
    assert fake_embedder.documents_embedded == 4


async def test_dense_and_keyword_search(client, fake_llm):
    fake_llm.models["fast"].synonyms = {"customers": ["clients", "buyers"]}
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    await upload(client, headers, schema["id"], DDL + PAYMENTS)

    # Keyword search finds a synonym the LLM added: "clients" is in no table or column name.
    res = await search(client, headers, schema["id"], "clients", mode="sparse")
    body = res.json()
    assert res.status_code == 200 and body["mode"] == "sparse" and body["model"] == "fake-bm25"
    assert body["results"][0]["name"] == "customers"
    assert "Synonyms: clients, buyers" in body["results"][0]["document"]

    dense = (await search(client, headers, schema["id"], "payment method of each order")).json()
    assert dense["results"][0]["name"] == "payments"
    assert [r["rank"] for r in dense["results"]] == list(range(1, len(dense["results"]) + 1))
    assert (
        len((await search(client, headers, schema["id"], "order", limit=1)).json()["results"]) == 1
    )


async def test_search_is_scoped_to_the_owner_and_schema(client):
    _, ada = await signup_and_login(client)
    _, bob = await signup_and_login(client, email="bob@example.com")
    ada_schema = await make_schema(client, ada)
    bob_schema = await make_schema(client, bob)
    await upload(client, ada, ada_schema["id"])
    bob_tables = await upload(client, bob, bob_schema["id"], PAYMENTS)

    # Bob can't search Ada's schema (404, like every other foreign object)...
    assert (await search(client, bob, ada_schema["id"], "customers")).status_code == 404
    # ...and his own results only contain his own tables, though both share one collection.
    results = (await search(client, bob, bob_schema["id"], "customers orders", limit=10)).json()
    assert {r["table_id"] for r in results["results"]} <= {t["id"] for t in bob_tables["tables"]}


async def test_deleting_removes_vectors(client, vector_index):
    _, headers = await signup_and_login(client)
    first = await make_schema(client, headers)
    second = await make_schema(client, headers, name="Second")
    detail = await upload(client, headers, first["id"])
    await upload(client, headers, second["id"], PAYMENTS)
    first_id, second_id = uuid.UUID(first["id"]), uuid.UUID(second["id"])

    orders = next(t for t in detail["tables"] if t["name"] == "orders")
    await client.delete(f"/api/v1/schemas/{first['id']}/tables/{orders['id']}", headers=headers)
    assert await vector_index.count(first_id) == 1  # the re-index job pruned its point
    results = (await search(client, headers, first["id"], "orders total", limit=10)).json()
    assert "orders" not in [r["name"] for r in results["results"]]

    await client.delete(f"/api/v1/schemas/{first['id']}", headers=headers)
    assert await vector_index.count(first_id) == 0

    await client.delete("/api/v1/users/me", headers=headers)  # account deletion
    assert await vector_index.count(second_id) == 0


async def test_rate_limited_descriptions_degrade_gracefully(client, fake_llm):
    # Both tiers are rate-limited: the descriptions are skipped, the index still builds.
    fake_llm.models["fast"].errors = [rate_limit_error()]
    fake_llm.models["primary"].errors = [rate_limit_error()]
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    detail = await upload(client, headers, schema["id"])
    assert detail["index_status"] == "ready"
    assert "rate limit" in detail["index_stats"]["enrichment_error"]
    assert all(t["indexed"] and t["description"] is None for t in detail["tables"])

    # Next run (no more errors): the missing descriptions are added and re-embedded.
    await client.post(f"/api/v1/schemas/{schema['id']}/index", headers=headers)
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert detail["index_stats"]["enriched"] == 2 and detail["index_stats"]["embedded"] == 2
    assert all(t["description"] for t in detail["tables"])


async def test_vector_store_outage_fails_the_index_not_the_upload(client, vector_index):
    async def broken(points):
        raise VectorStoreError("The search index (Qdrant) is unavailable: ConnectError.")

    vector_index.upsert = broken
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    detail = await upload(client, headers, schema["id"])
    assert detail["table_count"] == 2  # the upload itself worked
    assert detail["index_status"] == "failed" and "unavailable" in detail["index_error"]
    sources = (await client.get(f"/api/v1/schemas/{schema['id']}/sources", headers=headers)).json()
    assert sources[0]["status"] == "ready"


async def test_startup_recovery_fails_interrupted_index_builds(client, session_factory):
    _, headers = await signup_and_login(client)
    schema = await make_schema(client, headers)
    async with session_factory() as db:  # simulate a crash while indexing
        await db.execute(update(DbSchema).values(index_status="indexing"))
        await db.commit()
    await recover_interrupted(session_factory)
    detail = (await client.get(f"/api/v1/schemas/{schema['id']}", headers=headers)).json()
    assert detail["index_status"] == "failed" and "Rebuild" in detail["index_error"]


def test_identifier_words_split_names_for_keyword_search():
    assert identifier_words("customer_id") == "customer id"
    assert identifier_words("unitPrice") == "unit price"
    assert identifier_words("orders") == ""  # nothing to add


def test_table_document_lists_meaning_columns_and_relationships():
    from app.models import SchemaColumn, SchemaRelationship, SchemaTable

    table = SchemaTable(
        name="orders",
        db_schema="sales",
        description="One row per order.",
        synonyms=["purchases"],
        inferred=False,
        columns=[
            SchemaColumn(name="id"),
            SchemaColumn(name="customer_id", comment="who ordered"),
        ]
        + [SchemaColumn(name=f"metric_{i:03d}") for i in range(300)],
        relationships=[
            SchemaRelationship(
                from_columns=["customer_id"],
                to_table_key="sales.customers",
                to_table_name="sales.customers",
                to_columns=["id"],
            )
        ],
    )
    doc = table_document(table, ["sales.payments"])
    assert doc.startswith("Table: sales.orders\nAbout: One row per order.\nSynonyms: purchases")
    assert "customer_id (customer id) -- who ordered" in doc
    assert "References: sales.customers" in doc and "Referenced by: sales.payments" in doc
    assert "more columns" in doc and len(doc) <= 2_000  # wide tables are trimmed to fit
