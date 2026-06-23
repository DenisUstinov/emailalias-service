import logging
import sys

from pythonjsonlogger import json

from app.core.config import settings


class ServiceNameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = settings.SERVICE_NAME
        return True


def setup_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    stream = sys.stdout if settings.LOG_OUTPUT.lower() == "stdout" else sys.stderr

    if settings.LOG_FORMAT.lower() == "json":
        formatter = json.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s %(service_name)s"
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    logging.basicConfig(level=log_level, handlers=[handler], force=True)
    logging.getLogger().addFilter(ServiceNameFilter())
