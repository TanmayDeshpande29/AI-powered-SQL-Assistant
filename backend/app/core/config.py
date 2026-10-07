"""Application settings, loaded once from environment variables / the .env file.

Every tunable value lives here so the rest of the code never calls os.getenv()
directly. Pydantic validates types at startup: a missing GROQ_API_KEY or a
non-numeric POSTGRES_PORT fails fast instead of crashing on the first request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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
    llm_model_fast: str = "openai/gpt-oss-20b"  # speed: routing, rewriting, judging
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

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
