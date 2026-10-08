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

from app.core.config import Settings

logger = logging.getLogger(__name__)


def configure_tracing(settings: Settings) -> bool:
    """Export LangSmith settings to the environment. Returns True if tracing is on."""
    if not settings.langsmith_tracing:
        logger.info("LangSmith tracing is off (set LANGSMITH_TRACING=true to enable).")
        return False
    if settings.langsmith_api_key is None:
        logger.warning("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is empty: tracing stays off.")
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    logger.info("LangSmith tracing is on: project '%s'.", settings.langsmith_project)
    return True
