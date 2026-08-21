import json
import logging
import sys

from app.config import settings

_REDACTED_KEYS = {"access_token", "refresh_token", "token", "password", "authorization"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event_type = getattr(record, "event_type", None)
        if event_type:
            payload["event_type"] = event_type
        context = getattr(record, "context", None)
        if context:
            payload["context"] = _redact(context)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _redact(context: dict) -> dict:
    return {
        key: ("***" if key.lower() in _REDACTED_KEYS else value)
        for key, value in context.items()
    }


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event_type: str, message: str = "", level: str = "info", **context) -> None:
    """Structured event log, e.g. log_event(logger, "SEARCH_STARTED", search_run_id=...)."""
    logger.log(logging.getLevelName(level.upper()), message or event_type, extra={"event_type": event_type, "context": context})
