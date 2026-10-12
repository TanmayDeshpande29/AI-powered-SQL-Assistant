# Phase 3: embeddings + Qdrant (deep dive)

> **Goal:** turn every uploaded table into vectors in a real vector database, so that Phase 4 can *retrieve* the tables relevant to a question instead of stuffing the whole schema into the prompt.
> **Status:** done on 2026-10-12 · 84 tests passing · verified live (PostgreSQL → Groq enrichment → Hugging Face models on the CPU → Qdrant Cloud → browser UI).
> Concepts: notebook chapter 6 ([PDF](../notebook/SQLAssist-Notebook.pdf)). Previous phase: [Phase 2](phase-2-schema-ingestion.md).

---

## 0. TL;DR: what changed

| Area | Phase 2 | Phase 3 |
|---|---|---|
| What a table is to the AI | a card pasted into the prompt | also **a point in Qdrant**: a 384-d *dense* vector + a *sparse* BM25 vector + payload |
| Finding tables | user ticks them, or all tables up to a budget | **semantic search** (meaning) and **keyword search** (BM25), each callable separately |
| Table metadata | names, columns, keys, comments | + an **LLM-written description and synonyms** per table ("document expansion") |
| After an upload | merge into PostgreSQL | merge, then **index**: enrich → document → embed → upsert → prune (same background job) |
| Re-indexing cost | – | **incremental**: fingerprints skip unchanged tables (8 unchanged tables: 0.24 s, $0) |
| Deleting | rows cascade in PostgreSQL | + vectors deleted in Qdrant (table, schema, whole account) |
| Multi-tenancy | `user_id` on rows | + **one shared collection**, every search filtered by `user_id` + `schema_id` (tenant index) |
| Models | Groq LLMs | + `BAAI/bge-small-en-v1.5` and `Qdrant/bm25` from Hugging Face, **run locally via ONNX** |
| UI | schema workspace | + index status, Rebuild index, descriptions and synonyms, a **search playground** (dense vs BM25) |
| Tests | 74 | **84** |

---

## 1. What's new, at a glance

```
backend/app/
  core/config.py              + qdrant_url/api_key/path/collection, embedding models + cache, enrichment switch
  core/exceptions.py          + VectorStoreError (503), EmbeddingError (503)
  rag/                        NEW package
    documents.py              the text we embed per table + fingerprints
    embeddings.py             fastembed: dense (bge-small) + sparse (BM25) vectors, Embedder protocol
    vector_store.py           SchemaIndex: Qdrant collection, upsert, tenant-filtered search, deletes, retry
  llm/output_schemas.py       + TableDescription(s)
  llm/prompts.py              + DESCRIBE_TABLES (describe_tables@v1)
  llm/enrichment.py           NEW  describe_tables(): one structured call per batch of tables
  models/schema.py            + DbSchema.index_status/error/stats/indexed_at
                              + SchemaTable.description/synonyms/enrichment_hash/index_hash/indexed_at
  services/jobs.py            NEW  JobDeps bundle + per-schema locks (shared by uploads and indexing)
  services/indexing.py        NEW  the indexing pipeline, search, cleanup
  services/ingestion.py       uses JobDeps; indexes after every successful upload; recovers index jobs
  services/schemas.py         read models expose index fields; _Resolver -> TableResolver (public)
  schemas/db_schema.py        + IndexStatus, index fields, SearchHit, SearchResponse
  api/deps.py                 + Embeddings, VectorIndex, Jobs dependencies
  api/v1/routes/schemas.py    + POST /schemas/{id}/index, GET /schemas/{id}/search; deletes clean Qdrant
  api/v1/routes/users.py      account deletion also deletes the user's vectors
  api/v1/routes/health.py     readiness reports vector_store up/down
  main.py                     ensure the collection at startup, close the client at shutdown, v0.4.0
backend/alembic/versions/2026_10_12_0004-...  migration 4 (9 columns)
backend/tests/conftest.py     FakeEmbedder, in-memory Qdrant per test, fake table descriptions
backend/tests/test_indexing.py NEW  10 tests
frontend/src/
  components/SchemaSearch.jsx NEW  IndexStatusBar + SchemaSearchPanel (playground)
  DatabaseSetup.jsx           index status, rebuild, descriptions + synonyms, polling covers index jobs
  lib/api.js                  + reindexSchema, searchSchema
.gitignore                    + .qdrant/ and .cache/ (rebuildable local data)
```

---

## 2. Libraries and features we started using

| Tool | Where | Why |
|---|---|---|
| **qdrant-client** 1.19 (`AsyncQdrantClient`) | `rag/vector_store.py` | async client for Qdrant; the same API works against a server, Qdrant Cloud, or **embedded** (`path=` / `":memory:"`) |
| Qdrant **named vectors** | collection config | one point carries two vectors: `"dense"` (cosine) and `"bm25"` (sparse) |
| Qdrant **sparse vectors + `Modifier.IDF`** | collection config | BM25-style keyword search; Qdrant computes IDF ("how rare is this word") at query time |
| Qdrant **payload filter** + `is_tenant` keyword index | `search()` | multi-tenancy inside one collection; the filter is applied *during* the vector search |
| `query_points(query=..., using=..., query_filter=...)` | `search()` | Qdrant's universal query API (Phase 4 adds `prefetch` + RRF fusion to the same call) |
| `HasIdCondition` in `must_not` | `delete_missing()` | "delete this schema's points except these ids" in one request |
| **fastembed** 0.9 (`TextEmbedding`, `SparseTextEmbedding`) | `rag/embeddings.py` | Hugging Face models exported to **ONNX**, run on the CPU: no PyTorch, no GPU, no API key |
| **onnxruntime** (via fastembed) | – | the inference engine that executes the exported neural network |
| `BAAI/bge-small-en-v1.5` | dense model | 33M-parameter English embedding model, 384 dimensions, 67 MB (quantized ONNX), top-tier for its size |
| `Qdrant/bm25` | sparse model | BM25 tokenizer + English stemmer + stopwords: words → `{token_id: term frequency}` |
| `huggingface_hub` (via fastembed) | model download | fetches model files from the Hub once into `.cache/fastembed` |
| `asyncio.to_thread` | indexing + search | ONNX inference is CPU work: run it off the event loop |
| `hashlib.sha256` | `documents.fingerprint()` | content fingerprints for incremental re-indexing |

---

## 3. Backend, file by file

### 3.1 `core/config.py`
- **Qdrant location, in priority order:** `QDRANT_URL` (a server: Docker on `localhost:6333`, or Qdrant Cloud with `QDRANT_API_KEY`), else **embedded** mode in the folder `QDRANT_PATH` (default `.qdrant`).
  - Embedded = Qdrant's engine inside our Python process: nothing to install, but only **one process** may open the folder (it is file-locked), search is brute force (exact), and payload indexes are ignored.
- `qdrant_collection = "schema_tables"`.
- `embedding_model_dense = "BAAI/bge-small-en-v1.5"`, `embedding_model_sparse = "Qdrant/bm25"`, `embedding_cache_dir = ".cache/fastembed"`, `embedding_batch_size = 32`.
- `schema_enrichment = True`, `schema_enrichment_batch_size = 8` (tables per LLM call).

### 3.2 `rag/documents.py`: what we embed
A table's **search document** is written for retrieval, not for the SQL prompt:
```
Table: pmt
About: Each row represents a payment, recording the method, amount, and timestamp for payment reconciliation...
Synonyms: payment, transaction, settlement, revenue
Columns: id, ord_id (ord id), mthd, amt, paid_at (paid at)
References: ord_hdr
```
- **One table = one document** (structure-aware chunking). Splitting a table in half is how hallucinated columns start.
- **Meaning first:** name, LLM description, DDL comment, synonyms. Then columns, then relationships in **both** directions (`References`, `Referenced by`).
- **Identifiers spelled out as words.** We found in a probe that the BM25 tokenizer keeps `customer_id` and `unitPrice` as **single tokens**, so the word "customer" would never match them. `identifier_words()` adds `customer_id (customer id)`.
- **No data types.** They add almost no meaning and waste the model's window.
- **Size cap.** bge-small reads at most **512 tokens** (about 2,000 characters here); anything after that is silently cut. Columns are trimmed to fit, with "... and N more columns". A test caught the first version overflowing by 9 characters, because the marker itself wasn't budgeted.
- **`index_fingerprint(document, dense_model, sparse_model)`** = sha256 of the format version + both model names + the text. Change any of them and the table is re-embedded.

### 3.3 `rag/embeddings.py`: text → vectors
- `Embedding(dense: list[float], sparse: SparseVector(indices, values))`.
- `Embedder` is a **`Protocol`** (structural typing): anything with `dense_model`, `sparse_model`, `dense_dim`, `embed_documents()` and `embed_query()` fits. Tests plug in a fake without inheriting anything.
- `FastEmbedEmbedder`:
  - **Lazy loading:** models load on first use, behind a `threading.Lock`, so two simultaneous first requests don't both load them.
  - `dense_dim` comes from fastembed's model table (`TextEmbedding.get_embedding_size`), so creating the collection needs no download.
  - `embed_query()` uses `query_embed()`; some models encode questions differently from documents.
  - A failed first download becomes `EmbeddingError` with a hint ("check the internet connection").
- `get_embedder()` is `@lru_cache`d: **one instance per process**. The models (~80 MB) stay in memory.
- `HF_HUB_DISABLE_SYMLINKS_WARNING=1`: Windows without developer mode can't create symlinks, so the HF cache stores copies instead (harmless).

### 3.4 `rag/vector_store.py`: Qdrant
- **Collection layout (`ensure_collection`):**
  - `vectors_config = {"dense": VectorParams(size=384, distance=COSINE)}`
  - `sparse_vectors_config = {"bm25": SparseVectorParams(modifier=IDF)}`
  - On a server: payload indexes `user_id` (keyword, **`is_tenant=True`**) and `schema_id` (keyword). Embedded mode ignores payload indexes, so we skip them there.
  - On later starts it **checks** the existing collection. If its vector size differs from the model's (someone changed the model), it fails loudly with instructions instead of corrupting search.
- **Point = table:**
  - `id = table.id` (UUID), so re-indexing a table **overwrites** its point: upserts are idempotent;
  - payload = `user_id`, `schema_id`, `table_id`, `key`, `table`, `db_schema`, `columns`, `references`, `referenced_by` (keys, for Phase 4's FK expansion), `inferred`, `document`.
- **`search(user_id, schema_id, mode, query, limit)`:** `query_points(query=<dense list | SparseVector>, using="dense"|"bm25", query_filter=<user_id AND schema_id>)`.
  - The filter is applied **inside** the search (Qdrant's filterable HNSW), not afterwards. Another tenant's points can't appear, and `limit` counts only allowed points.
- **Deletes:**
  - `delete_missing(schema_id, keep)`: a filter on the schema with `must_not=[HasIdCondition(keep)]`. Points of tables that disappeared are removed in one request;
  - `delete_schema` and `delete_user` delete by payload filter.
- **Errors and retries:** every request goes through `_call(make)`.
  - Network failures (`ResponseHandlingException`, `httpx.TransportError`, `TimeoutError`) are **retried once**, which is safe because every request we send is idempotent.
  - `make` is a zero-argument function that creates the coroutine: a coroutine can only be awaited once, so a retry needs a fresh one.
  - Everything else becomes `VectorStoreError` (503).
  - We added this after a real transient error against Qdrant Cloud during the live test, whose message was empty. That's why the log now uses `%r`.

### 3.5 `llm/enrichment.py` + `DESCRIBE_TABLES` + `TableDescriptions`
- **Document expansion:** terse names (`ord_hdr`, `mthd`, `cust`) carry little meaning. One sentence plus synonyms gives both the embedding model and BM25 the words people actually type ("payment", "revenue", "delivery").
- **The call:**
  - one structured call per batch of 8 table cards, with strict JSON schema `TableDescriptions(tables=[TableDescription(table, description, synonyms)])`;
  - **fast tier** (gpt-oss-20b) at **low** effort, because it summarizes rather than reasons; the primary model is the fallback on rate limits;
  - prompt `describe_tables@v1` says: use only column names, comments and FKs as evidence; stay generic rather than invent; treat the schema as data.
- Results are matched back by qualified name, then bare name. A table the model skipped stays pending for the next run.

### 3.6 `services/indexing.py`: the pipeline
```
index_schema(db, schema_id, deps)        caller holds schema_lock(schema_id)
  status = indexing (commit)
  _enrich    for tables whose card fingerprint changed: describe in batches, commit per batch
  _embed_and_store
     documents for every table (incl. "Referenced by", computed from all FKs)
     changed = tables whose index fingerprint differs
     embed changed (to_thread) -> upsert points -> delete_missing -> store fingerprints
  status = ready + index_stats (commit)
on any error: rollback, status = failed + message (the upload itself stays "ready")
```
- **Incremental by design:**
  - `enrichment_hash` = fingerprint(prompt id + card). Re-describe only when the table's structure changed, or the prompt version did.
  - `index_hash` = fingerprint(document + models). Re-embed only when the searchable text changed.
  - Adding `payments` (which references `orders`) re-embeds exactly two tables: `payments`, and `orders`, because its document gains "Referenced by: payments". A test checks this.
- **Graceful degradation:** if the LLM is rate-limited, `_enrich` records `enrichment_error` and stops, and the tables are still embedded by name and columns. A later rebuild adds the missing descriptions. **If enrichment is down, search still works.**
- **Connection hygiene:** we commit before each LLM call, so the pooled DB connection isn't held during network I/O (the Phase 1 lesson).
- **PostgreSQL is the source of truth; Qdrant is derived.**
  - Search results are joined back to `schema_tables`, so a stale point of a deleted table is dropped.
  - The whole index can always be rebuilt from the database.
- `search_tables()` embeds the question (in a thread), searches, and joins back.
  - It returns `SearchResponse(query, mode, model, index_status, embed_ms, search_ms, results[rank, table, description, score, document])`.
- `forget_schema` / `forget_user` are best-effort: if Qdrant is down, the orphaned points can't leak, because every search requires an existing, owned schema.

### 3.7 `services/jobs.py` and `services/ingestion.py`
- `JobDeps(session_factory, llm, embedder, index)`: everything a background job needs in one bundle.
- `schema_lock()` moved here from `ingestion.py`, because uploads *and* indexing must not interleave on the same schema.
- `process_source(source_id, deps)`: after a successful merge (status `ready` committed), it calls `index_schema` **while still holding the lock**.
- `recover_interrupted` also fails index jobs left in `pending`/`indexing` by a restart.

### 3.8 Routes

| Method | Path | Notes |
|---|---|---|
| POST | `/schemas/{id}/index` | **202**; sets `index_status=pending`, runs the job in the background; unchanged tables are skipped |
| GET | `/schemas/{id}/search?q=&mode=dense\|sparse&limit=5` | ownership check (404), release the DB connection, embed + search; `limit` 1–20, `q` 2–500 chars |
| DELETE | `/schemas/{id}` | + deletes the schema's points |
| DELETE | `/schemas/{id}/tables/{table_id}` | + background re-index (prunes the point, refreshes "Referenced by" of others) |
| DELETE | `/users/me` | + deletes all the user's points (no foreign key cascades into another system) |
| GET | `/health/ready` | + `"vector_store": "up"\|"down"`. Only the DB is critical: without Qdrant, search is down but the rest works |

`SchemaSummary` gains `index_status`, `index_error`, `index_stats`, `indexed_at`; `TableRead` gains `description`, `synonyms`, `indexed`.

### 3.9 Migration 4
- 9 nullable columns, plus `index_status` (`NOT NULL`, `server_default='none'`, which fills existing rows).
- Autogenerated against PostgreSQL, reviewed, then verified with upgrade → `alembic check` → downgrade → upgrade → `alembic check`.

### 3.10 `main.py`
- At startup: `ensure_collection()`. A Qdrant failure is logged, not fatal.
- At shutdown: `index.close()`. Embedded Qdrant flushes and releases its folder lock.
- Version 0.4.0.

---

## 4. Frontend

- **`components/SchemaSearch.jsx`** (new):
  - **`IndexStatusBar`** shows "Building the search index…", "Search index ready · 6 tables · BAAI/bge-small-en-v1.5 + BM25", or the error.
    - It also shows last-run stats ("6 embedded, 0 unchanged, 6 described by openai/gpt-oss-20b ($0.00014) in 3.66 s"), a warning when descriptions were skipped, and a **Build / Rebuild / Retry** button.
  - **`SchemaSearchPanel`** (the playground):
    - **Meaning / Keywords / Compare** modes and example questions;
    - Compare runs both searches **in parallel** (`Promise.all`);
    - results show rank, score, a bar relative to the best hit *of that list* (dense and BM25 scores are on different scales), the description, and "what was indexed".
- **`DatabaseSetup.jsx`:**
  - polling continues while the index job is `pending`/`indexing`;
  - table cards show the description and synonym chips;
  - the playground appears once the schema has tables.
- **`lib/api.js`:** `reindexSchema(id)`, `searchSchema(id, {q, mode, limit})`.

---

## 5. Flows

**Upload → searchable:**
1. `POST /sources/text` → 202 → background `process_source`.
2. Parse, merge → `ready`.
3. `index_schema`: indexing → enrich (1 LLM call per 8 changed tables) → documents → embed changed (ONNX, thread) → upsert to Qdrant → prune → `ready`.
4. The page polls the schema; the badge flips to "Search index ready"; descriptions appear on the cards.

**Search:**
1. `GET /search?q=revenue&mode=dense`.
2. Ownership check, then release the DB connection.
3. `embed_query` (bge-small, ~6 ms on this CPU).
4. Qdrant `query_points(using="dense", filter=user+schema, limit=5)` (~250 ms to Qdrant Cloud, mostly network).
5. Join back to PostgreSQL → ranked tables.

---

## 6. Measured live (2026-10-12)

Setup:
- the API on port 8001 (port 8000 was taken by another project);
- **Qdrant Cloud** (from your `backend/.env`);
- Groq gpt-oss-20b for descriptions;
- 8 tables with deliberately terse names (`cust`, `prod`, `ord_hdr`, `ord_line`, `pmt`, `shpmt`, `emp`, `dept`).

| Step | Result |
|---|---|
| Very first index (models downloaded from Hugging Face, ~80 MB) | 56 s, of which embedding + download 49 s: a **one-time** cost |
| Index of 8 tables with cached models | job **4.5 s**: 1 LLM call ($0.00017) + embedding 1.5 s (incl. loading models from disk) + Qdrant Cloud writes |
| Rebuild with nothing changed | job **0.24 s**: 0 embedded, 8 unchanged, 0 LLM calls |
| Query embedding (bge-small + BM25) | **4–11 ms** |
| Qdrant Cloud search | **~235–300 ms** (network round trip to the hosted cluster) |
| UI run (6 tables) | 3.66 s, $0.00014; rebuild 0.74 s |

**Quality on 6 questions** (top 3; score = cosine for dense, BM25 for keywords):

| Question | Dense (meaning) | BM25 (keywords) |
|---|---|---|
| total revenue per customer | **cust** .631, ord_hdr .620, prod .610 | **ord_hdr** 4.90, pmt 3.81, cust 2.57 |
| which products are running out of stock | **prod** .635, ord_line, ord_hdr | **prod** 5.51, ord_line 2.02 |
| how long do deliveries take | **shpmt** .586, ord_hdr, cust | **shpmt** 2.99 (only hit) |
| average salary by department | **emp** .658, dept .642, pmt | **emp** 5.04, dept 2.46 |
| credit card payments | **pmt** .599, ord_hdr, cust | **pmt** 3.72 (only hit) |
| sku | **prod** .714, ord_hdr, ord_line | **prod** 3.69 (only hit) |

**What this teaches:**
- **Enrichment does the heavy lifting with terse names.**
  - "deliveries" matches `shpmt` only because the LLM wrote "delivery" in its synonyms; BM25's stemmer then maps deliveries → "deliveri" ← delivery.
  - "revenue" finds `pmt` because the LLM listed "revenue" as a synonym.
- **Dense always returns `limit` results** (cosine similarity is practically never zero), and its scores are compressed (0.50–0.71). The 5th dense hit is often irrelevant, so you need a cut-off or a reranker (Phase 4).
- **BM25 returns only tables that contain the words**, with spread-out scores. It is precise on exact terms (`sku`) but blind to meaning without the synonyms.
- **The two disagree on "total revenue per customer"** (cust vs ord_hdr), and both answers are partly right: the SQL needs both tables. That is exactly why Phase 4 **fuses** the two rankings (RRF) and expands along foreign keys.

---

## 7. Problems found and fixed

| Problem | How we found it | Fix / lesson |
|---|---|---|
| BM25 keeps `customer_id` / `unitPrice` as single tokens, so "customer" never matched them | a tokenizer probe before writing the code | spell identifiers out as words in the document |
| A trimmed document was 2,009 characters (> 2,000) | the new unit test | budget for the "... and N more columns" marker too |
| One search failed with an empty error message | live test against Qdrant Cloud (transient) | one retry for network errors (all our requests are idempotent); log with `%r` |
| Upload "took 2 s", rebuild "took 6 s" from the test script | comparing client vs server timings | Windows tries IPv6 `::1` for `localhost` first (uvicorn listens on IPv4), costing ~2 s per request in Python clients. Use `127.0.0.1`. Server times were 0.24 s |
| Payload-index warnings in embedded mode | probe | create payload indexes only on a server |
| The app used Qdrant Cloud, not embedded mode | collection named `sql_assistant` in the startup log | your `backend/.env` already had `QDRANT_URL/API_KEY/COLLECTION` from the prototype. `EMBEDDING_MODEL` there is unused (our settings are `EMBEDDING_MODEL_DENSE/SPARSE`) |
| Port 8000 already in use | `/health` returned 404 with version 0.1.0 | it was another local project (ai-career-mentor); our test servers used 8001/5174 |

---

## 8. Tests (84)

| File | Covers |
|---|---|
| `test_indexing.py` (10) | the upload builds the index with descriptions + synonyms (points in Qdrant); **incremental** re-index (0 re-embedded when unchanged; exactly 2 after adding a referencing table); dense and BM25 search (an LLM synonym found by keywords); **tenant isolation** (404 + results limited to own tables in a shared collection); vectors deleted for table / schema / account; **rate-limited enrichment degrades gracefully** and recovers on rebuild; **vector-store outage** fails the index but not the upload; startup recovery of index jobs; `identifier_words`; document format + trimming |
| Phases 0–2 (74) | unchanged; every upload test now also runs the indexing pipeline |

**How the fakes work:**
- **`FakeEmbedder`:** a deterministic hashed bag of words (dense) plus word counts (sparse). No downloads; similar words give similar vectors.
- **`vector_index`:** a **real** Qdrant, `AsyncQdrantClient(location=":memory:")`, fresh per test. Same filters, IDF and deletes as production.
- **`FakeChatModel`:** answers `TableDescriptions` by reading the `TABLE …` lines in the prompt.

---

## 9. Run it

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run pytest -q
```

`alembic upgrade head` applies migration 4; `pytest` should report 84 passed.

Choose where Qdrant runs (`backend/.env`):
- **Embedded (zero setup):** leave `QDRANT_URL` empty. Data goes to `backend/.qdrant/`. Only one process can use it, so stop the API before running scripts that open it.
- **Docker:** `docker compose up -d qdrant`, then `QDRANT_URL=http://localhost:6333`.
- **Qdrant Cloud:** `QDRANT_URL=https://…cloud.qdrant.io` + `QDRANT_API_KEY` (your current setup).

The first index downloads the two models (~80 MB) into `backend/.cache/fastembed/`. Existing schemas from Phase 2 show "Search index not built yet": click **Build index**.

---

## 10. Interview questions you can now answer

1. **What is an embedding?** A fixed-length vector a neural network produces for a text, positioned so that texts with similar meaning end up close together (here 384 numbers per table).
2. **Cosine similarity vs dot product vs Euclidean?**
   - Cosine compares directions and ignores length.
   - Dot product = cosine × lengths; it is identical to cosine for normalized vectors, which bge produces.
   - Euclidean measures straight-line distance.
   - Use whatever the model was trained with.
3. **Dense vs sparse vectors?**
   - Dense: few hundred dimensions, all non-zero, learned meaning (synonyms, paraphrases).
   - Sparse: vocabulary-sized, mostly zero, one weight per word present (exact terms, rare identifiers).
   - They fail in opposite ways, hence hybrid search.
4. **What is BM25?** A keyword ranking function: term frequency (with saturation) × inverse document frequency (rare words count more), normalized by document length. Ours runs as sparse vectors, with Qdrant applying IDF at query time.
5. **Why does stemming matter?** "deliveries", "delivered" and "delivery" all map to one stem, so different word forms match. Without it, BM25 would miss them.
6. **What is a vector database, and why not a list plus numpy?** It stores vectors with metadata, filters by metadata *during* search, builds ANN indexes (HNSW) for millions of points, persists, replicates and scales. Brute force (embedded mode) is fine for thousands.
7. **What is HNSW?** A layered proximity graph. Search starts in a sparse top layer and greedily moves closer layer by layer. It is approximate but sub-linear, tuned with `m` (links per node) and `ef` (search breadth).
8. **How do you do multi-tenancy in a vector DB?** Usually one collection with a tenant id in the payload, a **tenant index** (`is_tenant`), and a mandatory filter on every query, applied inside the search. Collection-per-tenant doesn't scale to many tenants.
9. **Why filter during search instead of after?** Post-filtering top-k can leave zero results if the top hits belong to others, and it risks leaking them. Filtered search only considers allowed points, and `limit` counts only those.
10. **How do you keep a vector index in sync with the database?**
    - The DB is the source of truth.
    - Deterministic point ids (the table id) make upserts idempotent.
    - Fingerprints decide what to re-embed.
    - Deletes are propagated explicitly (no foreign keys cross systems).
    - The index can always be rebuilt from the DB.
11. **What is chunking, and how did you chunk a schema?** Splitting knowledge into retrievable units. We chunk along the data's own structure: one table = one document, never half a table.
12. **What is document expansion?** Adding text to documents before indexing: here, LLM-written descriptions and synonyms, so queries in business language match terse technical names.
13. **Why do embedding models have a max length, and what happens beyond it?** Transformers have a fixed context (512 tokens for bge-small). Extra text is truncated and simply not represented, so important content must come first.
14. **Why run models with ONNX Runtime instead of PyTorch?** For inference only, ONNX gives a much smaller install (no ~2 GB torch), fast CPU execution and the same weights. PyTorch is needed for training or fine-tuning.
15. **Why `query_embed` vs `embed`?** Some models are trained with different prefixes or encoders for queries and passages (asymmetric search). Using the right one matters for quality.
16. **Why are dense scores all between 0.5 and 0.7?** Embedding spaces are anisotropic: even unrelated texts have positive similarity. Absolute scores aren't probabilities, so compare ranks, calibrate a threshold on your data, or rerank.
17. **How do you test code that needs embeddings and a vector DB?** A deterministic fake embedder (no downloads) plus a real in-memory vector store, so you test your filters, deletes and pipeline logic, not the model's quality. Model quality is measured with evals (Phase 5).
18. **What makes the indexing job safe to retry?** Idempotent upserts by id, fingerprints instead of "already done" flags, commits per batch, and a lock per schema. A crash at any point leaves state that the next run converges from.

---

## 11. Known gaps (carried forward)

- **Search isn't wired into generation yet.** The playground shows retrieval; **Phase 4** fuses dense + BM25 (RRF), expands along foreign keys, reranks, and feeds the top tables to the SQL prompt.
- **No score threshold.** Dense always returns `limit` hits; calibration or a reranker comes in Phase 4.
- **Very wide tables** (hundreds of columns) are trimmed to 2,000 characters; column-group chunks would cover the rest.
- **Embedded Qdrant is single-process** and the in-process job queue is lost on restart. Redis workers and a Qdrant server are the Phase 8/9 setup.
- **Orphaned points** can remain if Qdrant is down during a delete. They are harmless (unreachable by search), but a periodic cleanup job would reclaim the space.
- The first index after a restart pays ~1–2 s to load the models from disk. They could be warmed at startup in a background thread.
