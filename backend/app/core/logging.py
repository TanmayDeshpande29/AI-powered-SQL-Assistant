import logging

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # httpx logs every Groq call at INFO; keep it quiet unless debugging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
