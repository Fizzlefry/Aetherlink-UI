"""JSON logging setup for production-grade logs."""

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for easy parsing and grep."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        # Add request_id if present
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Add any extra fields
        if hasattr(record, "extra"):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_json_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatting."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
