"""Application settings, loaded once from environment variables / the .env file.

Every tunable value lives here so the rest of the code never calls os.getenv()
directly. Pydantic validates types at startup: a missing GROQ_API_KEY or a
non-numeric POSTGRES_PORT fails fast instead of crashing on the first request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

ReasoningEffort = Literal["low", "medium", "high"]


class ModelPrice(BaseModel):
    """USD per 1 million tokens, as listed by the provider."""

    input: float
    output: float
    cached_input: float | None = None


# Groq list prices, checked 2026-10-07/08 on console.groq.com (docs + /models API).
# Override with LLM_PRICES='{"model-id": {"input": 0.1, "output": 0.4}}' in .env.
DEFAULT_LLM_PRICES = {
    "openai/gpt-oss-120b": ModelPrice(input=0.15, output=0.60, cached_input=0.075),
    "openai/gpt-oss-20b": ModelPrice(input=0.075, output=0.30, cached_input=0.037),
    "qwen/qwen3.8-27b": ModelPrice(input=0.80, output=4.00, cached_input=0.40),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate unrelated variables in .env
    )

    # --- App ---
    app_name: str = "SQLAssist API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Database (PostgreSQL) ---
    # Either the individual connection fields (local dev: the same login you use in pgAdmin)...
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "sql_assistant"
    # ...or one complete URL, as cloud providers hand out. When set, it wins over the fields.
    database_url: str | None = None
    db_echo: bool = False

    # --- Auth ---
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- LLM (Groq) ---
    groq_api_key: SecretStr
    llm_model_primary: str = "openai/gpt-oss-120b"  # quality: SQL generation / reasoning
    llm_model_fast: str = "openai/gpt-oss-20b"  # speed: explanations, routing, judging
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2  # retries for transient errors only (network, 5xx); see llm/client.py
    # Hard cap per answer: bounds cost and latency. Reasoning tokens count toward it.
    llm_max_output_tokens: int = 4096
    llm_reasoning_effort: ReasoningEffort = "medium"  # default when a request doesn't choose
    # How the model is forced into our output schema: "json_schema" = constrained decoding
    # (Groq strict mode, gpt-oss only); "function_calling" = schema sent as a tool definition.
    llm_structured_output_method: Literal["json_schema", "function_calling"] = "json_schema"
    llm_prices: dict[str, ModelPrice] = Field(default_factory=lambda: dict(DEFAULT_LLM_PRICES))
    # Vision (screenshots of schemas). The only image-capable model on Groq's list today.
    llm_model_vision: str = "qwen/qwen3.8-27b"
    # Qwen's own reasoning switch ("none" | "default"): transcription needs no thinking
    # (measured: 0.9 s with "none" vs 2.3 s with reasoning). Empty = provider default.
    llm_vision_reasoning_effort: str | None = "none"

    # --- Schema ingestion (Phase 2) ---
    max_sql_upload_bytes: int = 5_000_000  # .sql files: schema-only dumps are far smaller
    max_image_upload_bytes: int = 4_000_000  # Groq's limit for base64-encoded images
    # Budget for the schema text put into a prompt (~4 characters per token).
    # Bigger schemas get truncated: the limit that RAG (Phases 3-4) removes.
    schema_context_max_chars: int = 12_000

    # --- Embeddings + vector store (Phase 3) ---
    # Qdrant: a server URL (docker compose: http://localhost:6333, or Qdrant Cloud + API key),
    # or, when empty, "embedded" mode: Qdrant runs inside this process and stores its data
    # in qdrant_path. Embedded mode = no server to install, one process only, exact search.
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_path: str = ".qdrant"
    qdrant_collection: str = "schema_tables"
    # Hugging Face models, run locally on the CPU through ONNX Runtime (fastembed): no
    # API key, no GPU, no PyTorch. Downloaded once into embedding_cache_dir on first use.
    embedding_model_dense: str = "BAAI/bge-small-en-v1.5"  # 384-d meaning vectors, 67 MB
    embedding_model_sparse: str = "Qdrant/bm25"  # keyword weights (BM25), IDF applied by Qdrant
    embedding_cache_dir: str = ".cache/fastembed"
    embedding_batch_size: int = 32
    # LLM-written description + synonyms per table, added to what we embed ("purchases"
    # should find `orders`). Costs one fast-model call per batch of tables.
    schema_enrichment: bool = True
    schema_enrichment_batch_size: int = 8

    # --- Tracing (LangSmith) ---
    # Off unless LANGSMITH_TRACING=true and an API key are set. When on, prompts and answers
    # are sent to LangSmith's cloud so every LLM call can be inspected as a trace.
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "sqlassist-dev"
    langsmith_endpoint: str | None = None  # e.g. the EU region: https://eu.api.smith.langchain.com

    @property
    def sqlalchemy_url(self) -> URL | str:
        """Where SQLAlchemy (app engine + Alembic) connects.

        URL.create() keeps the password as a separate component, so characters such as
        @ : / # % need no manual URL-encoding (in a hand-written URL string they would
        break parsing). Its repr() also masks the password, so it is safe to log.
        """
        if self.database_url:
            return self.database_url
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value() or None,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is parsed once per process, not on every call."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment


settings = get_settings()
