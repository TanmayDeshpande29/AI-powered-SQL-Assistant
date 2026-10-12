# SQLAssist Roadmap

How we turn a prototype into an industry-grade, AI-native SaaS, one tested increment at a time.
Every phase follows the same loop:

1. **Concept**: learn the idea (notebook pages first).
2. **Build**: write the code.
3. **Verify**: tests, live checks and, from Phase 5 on, eval metrics.
4. **Document**: this roadmap, `docs/phases/phase-N-*.md`, the README diagrams and new notebook pages.
5. **Commit / PR.**

## Decisions log

| Date | Decision | Why | Alternatives considered |
|---|---|---|---|
| 2026-10-07 | **PostgreSQL only** (MongoDB removed) | relational data (users → schemas → tables → columns → FKs), DB-enforced constraints, transactions | keep Mongo (rejected: joins/constraints in app code) |
| 2026-10-07 | **Qdrant** as vector DB | real DB server: payload filtering, multi-tenancy, sparse+dense hybrid with server-side RRF, snapshots | FAISS (library only), pgvector (fewer hybrid features) |
| 2026-10-07 | **LangChain + LangGraph** from the start | standard interfaces for models/tools/prompts; LangGraph gives state, loops, checkpointing, HITL | hand-rolled agent loop (skipped by choice) |
| 2026-10-07 | **Schema-only** product scope | we never connect to or execute on customers' databases (safer, simpler); EXPLAIN-based features stay optional | executor agent on live DBs (deferred) |
| 2026-10-07 | **Groq `openai/gpt-oss-120b` (primary) + `gpt-oss-20b` (fast)** | free tier, very fast; Llama 3 models used by the prototype are deprecated | — |
| 2026-10-07 | **uv** for Python, `pyproject.toml` + lockfile | reproducible installs, fast | pip + requirements.txt (still exported for compatibility) |
| 2026-10-07 | **JWT access (15 min) + refresh (7 days)**, bcrypt | stateless API that scales horizontally; `jti` claim ready for revocation | server sessions |
| 2026-10-07 | **LangSmith** for tracing | zero-code with LangChain/LangGraph (env vars only), free tier, LangGraph tooling | Langfuse Cloud, self-hosted Langfuse (needs Docker + ClickHouse), none |
| 2026-10-07 | **Structure what code consumes, stream what people read** | generate/debug/optimize return a typed `SQLAnswer` we can validate; explain streams prose over SSE | streaming partial JSON (complicates validation) |
| 2026-10-07 | **Strict JSON-schema output** (Groq constrained decoding) | the decoder can only emit schema-valid JSON on gpt-oss | function calling (kept as a config switch), JSON mode (no schema guarantee) |
| 2026-10-07 | **Retry transient errors, fall back on rate limits**; Groq SDK retries off | the SDK would sleep up to 60 s per 429 before any fallback | SDK default retries |
| 2026-10-07 | **sqlglot validation pulled into Phase 1** | cheap, visible quality gate on every answer; groundwork for the Validator agent | wait until Phase 6 |
| 2026-10-07 | **Per-prompt reasoning effort** (explain = low) | measured: medium effort spent 71% of output on hidden reasoning; low was 2.5× faster to first word and 4.4× cheaper | one global effort |
| 2026-10-08 | **Schemas belong to a user; workspaces deferred to Phase 8** | one owner column keeps queries and IDOR checks simple now; a `workspace_id` can replace `user_id` later | workspaces now (teams/roles before anyone needs them) |
| 2026-10-08 | **In-process jobs**: FastAPI `BackgroundTasks` + a Postgres row as the job record, 202 + polling | no Redis needed yet; the client contract (202 + poll) stays the same when a real queue replaces the executor | Redis + arq/Celery now (Docker daemon not available yet) |
| 2026-10-08 | **Idempotent uploads** via sha256 + `UNIQUE(schema_id, content_hash)` | double clicks and retries never reprocess or pay twice; enforced by the database | client-side de-duplication only |
| 2026-10-08 | **Screenshots: two stages** (vision LLM → DDL text → our parser) | one deterministic parser for every input; the transcription is visible to the user; cost paid once per upload | vision model straight to JSON tables |
| 2026-10-08 | **Images stored in Postgres (`BYTEA`)** for now | ≤ 4 MB each, few uploads; no extra service | S3/R2 object storage (Phase 8/9) |
| 2026-10-08 | **Prompt stuffing with a character budget** as the baseline | measurable starting point before RAG; truncation is reported to the user | retrieval right away (Phases 3–4 need this baseline to beat) |
| 2026-10-08 | **Schema as data in the human message** (`<schema>` tags), rules in the system message; prompts v3 | user-supplied comments could contain instructions; roles keep data and instructions apart | schema in the system prompt |
| 2026-10-08 | **Schema-reference validation separate from syntax** (`schema_issues`, `valid` unchanged) | "valid SQL that names a missing column" is two facts; the UI shows both | mark such SQL invalid |

## Phases

### Phase 0: Foundation ✅ (2026-10-07)
- Layered FastAPI backend (`core/ db/ models/ schemas/ services/ llm/ api/`).
- PostgreSQL via SQLAlchemy 2 async + asyncpg; Alembic migrations.
- bcrypt passwords; JWT access + refresh; `/users/me`; owner-scoped history.
- LangChain LCEL chains on Groq; per-mode prompts; model names in config.
- One error envelope + correct status codes; health checks.
- Frontend API client with silent refresh; protected routes.
- 23 tests; docker-compose for Postgres + Qdrant; DB login via POSTGRES_* settings; notebook volume 1.
- Details: [phases/phase-0-foundation.md](phases/phase-0-foundation.md)

### Phase 1: LLM layer ✅ (2026-10-07)
- Structured output: `with_structured_output(SQLAnswer, method="json_schema", strict=True, include_raw=True)`.
- SQL validation with sqlglot (`valid`, `dialect`, `statement_types`, `errors`) on every generated query.
- Streaming explanations over Server-Sent Events (FastAPI `EventSourceResponse`); frontend reads the stream with `fetch` + `ReadableStream`.
- Token usage (incl. reasoning and cached tokens), latency and list-price cost per call, stored with history (migration 2: 7 new columns, `details` as JSONB).
- Reasoning effort per request (low/medium/high) with per-prompt defaults; "Thinking" switch in the UI.
- Resilience: LangChain `with_retry` for transient errors, `with_fallbacks` to the other model tier on 429, HTTP 429 + `Retry-After` when both are limited.
- Prompt versioning (`PromptSpec`, e.g. `generate_sql@v2`) recorded in history and traces.
- LangSmith tracing, configured once at startup; DB connection released during LLM calls.
- 51 tests; verified live end to end (API, PostgreSQL, Groq, browser UI).
- Details: [phases/phase-1-llm-layer.md](phases/phase-1-llm-layer.md)

### Phase 2: Schema ingestion ✅ (2026-10-08)
- Inputs: pasted SQL, `.sql`/`.ddl`/`.txt` upload, screenshot (vision model `qwen/qwen3.8-27b` → DDL → parser).
- sqlglot DDL extraction: pg_dump, mysqldump, SSMS scripts, `ALTER`, `COMMENT ON`; tables, columns and joins inferred from plain queries; one broken statement = one warning.
- Normalized storage (migration 3): `db_schemas`, `schema_sources`, `schema_tables`, `schema_columns`, `schema_relationships`; explicit merge rules across uploads.
- Background processing: 202 + polling, Postgres job rows, idempotent uploads (sha256), per-schema lock, parsing in a thread, startup recovery.
- Grounded prompts v3 (schema as data, character budget, truncation reported); schema-aware validation (`schema_issues`).
- UI: real Database Setup workspace; Query Builder and SQL Assistants pick a schema and tables.
- 74 tests; verified live (paste, file, screenshot, grounded vs ungrounded generation).
- Details: [phases/phase-2-schema-ingestion.md](phases/phase-2-schema-ingestion.md)

### Phase 3: Embeddings + Qdrant
- Table cards (one chunk per table) with LLM-written descriptions and synonyms.
- Hugging Face embedding model (start with `BAAI/bge-small-en-v1.5`, 384-d); sparse BM25 vectors.
- Qdrant collection with tenant-indexed `user_id` / `schema_id` payload (workspace later).
- Re-embed a schema's tables when an upload changes them (hook into the ingestion job).
- **Learn:** embeddings, similarity metrics, HNSW, payload filtering, multitenancy.

### Phase 4: Retrieval
- BM25-only, dense-only, hybrid (RRF), each measurable on its own.
- Query rewriting / multi-query / HyDE (compare).
- FK-graph expansion; cross-encoder reranking (`bge-reranker-base`).
- Generation grounded in retrieved tables + sqlglot validation.
- **Learn:** lexical vs semantic search, fusion, reranking, context construction.

### Phase 5: RAG evaluation
- Golden dataset (hand-written + reviewed synthetic + Spider/BIRD subset).
- Retrieval metrics: precision/recall@k, hit rate, MRR, nDCG.
- Generation metrics: valid-SQL rate, execution accuracy on a seeded sandbox DB, RAGAS faithfulness/relevancy, LLM-as-judge.
- Eval dashboard page; CI quality gate.
- **Learn:** offline vs online evaluation, metric design, judge biases.

### Phase 6: Agents (LangGraph)
- Router, Schema-Ingestion, Retriever, SQL Generator, Validator/Critic (reflection loop), Safety Guard, Optimizer, Explainer.
- Postgres checkpointer (short-term memory per thread), Store (long-term user memory).
- Human-in-the-loop: clarifying questions, table confirmation, approval for non-SELECT.
- Agent trace viewer in the UI.
- **Learn:** tool calling, ReAct, state graphs, reducers, memory types, interrupts.

### Phase 7: MCP
- FastMCP server exposing `search_schema`, `generate_sql`, `validate_sql`, `explain_sql` (reusing `services/`).
- stdio for local use, Streamable HTTP + auth for remote; tested from Claude Desktop / Cursor.
- Agents as MCP clients where useful.
- **Learn:** MCP architecture, primitives, transports, lifecycle, security.

### Phase 8: SaaS & scale
- Workspaces + roles, plans/quotas, per-user rate limiting (token bucket in Redis).
- Exact + semantic caching; refresh token in httpOnly cookie; token revocation (`jti` denylist, rotation).
- Redis-backed job queue for ingestion (replaces `BackgroundTasks`); object storage for uploaded images.
- Structured logging, metrics, traces; UI/UX overhaul (design system, toasts, empty states, accessibility).
- **Learn:** multi-tenancy, caching, rate limiting, observability.

### Phase 9: Ship
- Multi-stage Dockerfiles, full docker-compose, GitHub Actions (lint → test → eval → build → deploy).
- Deployment (Render / Railway / Fly.io / VM), secrets management, backups.
- **Learn:** containers, CI/CD, deployment strategies.
