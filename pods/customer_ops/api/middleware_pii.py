from __future__ import annotations
import re
from typing import Dict, Any

# Simple, conservative patterns (tuned to minimize false positives)
EMAIL_RE   = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE   = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b")
SSN_RE     = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")

REDACTION_TOKEN = "[REDACTED]"

def redact_text(s: str) -> str:
    s = EMAIL_RE.sub(REDACTION_TOKEN, s)
    s = PHONE_RE.sub(REDACTION_TOKEN, s)
    s = SSN_RE.sub(REDACTION_TOKEN, s)
    return s

def redact_json(obj: Any) -> Any:
    # Best-effort scrub of prompt/inputs; preserves structure
    if isinstance(obj, dict):
        return {k: redact_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_json(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
