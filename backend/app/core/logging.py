import logging

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # httpx logs every Groq call at INFO; keep it quiet unless debugging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # sqlglot warns for every statement it can't fully parse; our DDL extractor already
    # turns those into per-upload warnings the user sees, so the log copy is noise.
    logging.getLogger("sqlglot").setLevel(logging.ERROR)
