"""LangSmith tracing setup.

LangChain traces every chain/LLM call automatically when the LangSmith SDK sees
LANGSMITH_TRACING=true and LANGSMITH_API_KEY in the *process environment*.

Our settings come from backend/.env via pydantic-settings, which does NOT export
values into os.environ, so we copy them across once at startup. It must happen before
the first LLM call: the LangSmith SDK caches environment variables (functools.lru_cache)
the first time it reads them.
"""

import logging
import os
from collections.abc import MutableMapping

from app.core.config import Settings

logger = logging.getLogger(__name__)


def configure_tracing(settings: Settings, environ: MutableMapping[str, str] | None = None) -> bool:
    """Export LangSmith settings to the environment. Returns True if tracing is on.

    `environ` defaults to the real process environment; tests pass a plain dict so
    they never change global state.
    """
    env = os.environ if environ is None else environ
    if not settings.langsmith_tracing:
        logger.info("LangSmith tracing is off (set LANGSMITH_TRACING=true to enable).")
        return False
    # A blank "LANGSMITH_API_KEY=" line in .env loads as "", not None: treat both as missing.
    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    if not api_key.strip():
        logger.warning("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is empty: tracing stays off.")
        return False

    env["LANGSMITH_TRACING"] = "true"
    env["LANGSMITH_API_KEY"] = api_key.strip()
    env["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        env["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    logger.info("LangSmith tracing is on: project '%s'.", settings.langsmith_project)
    return True
