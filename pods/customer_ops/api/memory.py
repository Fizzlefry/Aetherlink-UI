# pods/customer_ops/api/memory.py
from __future__ import annotations

import json
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

import backoff

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

from .config import get_settings

_MEM_FALLBACK: Dict[str, Deque[Dict[str, Any]]] = {}
_MAX_PER_THREAD = 100


def _key(tenant: str, lead_id: str) -> str:
    return f"mem:{tenant}:{lead_id}"


def _client() -> Optional["redis.Redis"]:
    s = get_settings()
    url = os.getenv("REDIS_URL", "") or (getattr(s, "REDIS_URL", None) or "")
    if not url or redis is None:
        return None
    return redis.Redis.from_url(
        url, socket_timeout=2, socket_connect_timeout=2, decode_responses=True
    )


@backoff.on_exception(backoff.expo, Exception, max_time=8, max_tries=3, jitter=None)
def _push_redis(r: "redis.Redis", key: str, item: Dict[str, Any]) -> None:
    r.lpush(key, json.dumps(item))
    r.ltrim(key, 0, _MAX_PER_THREAD - 1)


def append_history(tenant: str, lead_id: str, role: str, text: str) -> None:
    rec = {"ts": time.time(), "role": role, "text": text}
    r = _client()
    if r:
        try:
            _push_redis(r, _key(tenant, lead_id), rec)
            return
        except Exception:
            pass
    dq = _MEM_FALLBACK.setdefault(_key(tenant, lead_id), deque(maxlen=_MAX_PER_THREAD))
    dq.appendleft(rec)


def get_history(tenant: str, lead_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    r = _client()
    key = _key(tenant, lead_id)
    if r:
        try:
            raw = r.lrange(key, 0, limit - 1)
            return [json.loads(x) for x in raw]
        except Exception:
            pass
    dq = _MEM_FALLBACK.get(key, deque())
    return list(dq)[:limit]


# ============================================================================
# PII-Safe Memory with Redaction
# ============================================================================

import hashlib
import re
from typing import Iterable, Tuple

try:
    from prometheus_client import Counter
    # Prometheus - safe registration (avoid pytest re-import issues)
    PII_REDACTIONS_TOTAL = Counter(
        "pii_redactions_total",
        "Total PII redactions performed",
        labelnames=("type",),
        registry=None,  # Use default registry
    )
except Exception:
    # Fallback if metric already exists or Prometheus not available
    class _NoOpCounter:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
    PII_REDACTIONS_TOTAL = _NoOpCounter()

# Reasonable defaults for US-style data; add more as needed
_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
_RE_PHONE = re.compile(r"(?:\+?1[-.●\s]?)?(?:\(?\d{3}\)?[-.\s●]?)\d{3}[-.\s●]?\d{4}\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_RE_SSN = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def _iter_matches(text: str, patterns: List[Tuple[str, re.Pattern]]) -> Iterable[Tuple[str, Tuple[int, int], str]]:
    for name, rx in patterns:
        for m in rx.finditer(text):
            yield name, m.span(), m.group(0)


def _compile_extra(csv_patterns: str) -> List[Tuple[str, re.Pattern]]:
    pats: List[Tuple[str, re.Pattern]] = []
    for idx, raw in enumerate([p.strip() for p in (csv_patterns or "").split(",") if p.strip()]):
        try:
            pats.append((f"extra_{idx}", re.compile(raw)))
        except re.error:
            # best-effort: skip invalid custom regex
            continue
    return pats


def redact_pii(text: str, *, extra_csv: str = "") -> Tuple[str, Dict[str, str]]:
    """
    Returns (redacted_text, mapping) where mapping maps redaction token -> hash
    """
    base = [("email", _RE_EMAIL), ("phone", _RE_PHONE), ("card", _RE_CARD), ("ssn", _RE_SSN)]
    patterns: List[Tuple[str, re.Pattern]] = base + _compile_extra(extra_csv)

    # collect matches; avoid overlap by sorting & tracking ranges
    hits: List[Tuple[str, Tuple[int, int], str]] = list(_iter_matches(text, patterns))
    hits.sort(key=lambda x: x[1][0])
    redacted = []
    mapping: Dict[str, str] = {}
    last = 0

    for name, (s, e), val in hits:
        if s < last:
            continue  # overlap—already replaced
        token = f"[{name.upper()}:{_hash(val)}]"
        PII_REDACTIONS_TOTAL.labels(name).inc()
        redacted.append(text[last:s])
        redacted.append(token)
        mapping[token] = _hash(val)
        last = e

    redacted.append(text[last:])
    return "".join(redacted), mapping


def append_history_safe(
    tenant: str,
    lead_id: str,
    role: str,
    text: str,
    *,
    enable_redaction: bool,
    extra_patterns_csv: str = "",
) -> None:
    """
    Drop-in replacement that redacts PII (if enabled), then appends to the same redis list.
    Falls back to normal append if redis is None.
    """
    to_store = text
    pii_meta: Dict[str, str] = {}
    if enable_redaction:
        to_store, pii_meta = redact_pii(text, extra_csv=extra_patterns_csv)

    rec = {"ts": time.time(), "role": role, "text": to_store, "pii": pii_meta}
    r = _client()
    if r:
        try:
            _push_redis(r, _key(tenant, lead_id), rec)
            return
        except Exception:
            pass
    dq = _MEM_FALLBACK.setdefault(_key(tenant, lead_id), deque(maxlen=_MAX_PER_THREAD))
    dq.appendleft(rec)
