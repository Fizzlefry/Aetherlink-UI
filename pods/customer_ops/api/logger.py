import json
import logging
import sys
import time

from .config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            base["request_id"] = record.request_id
        return json.dumps(base, ensure_ascii=False)


logger = logging.getLogger("customer_ops")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(getattr(logging, get_settings().LOG_LEVEL.upper(), logging.INFO))


def log_chat(user_id: str, message: str, intent: str, confidence: float) -> None:
    logger.info(
        "chat",
        extra={
            "user_id": user_id,
            "intent": intent,
            "confidence": confidence,
            "message_length": len(message),
        },
    )


def log_faq(query: str, found: bool, score: float | None = None) -> None:
    logger.info(
        "faq",
        extra={"query_length": len(query), "found": found, "score": score},
    )
