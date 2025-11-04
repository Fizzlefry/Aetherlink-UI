from __future__ import annotations

import json

from .config import get_settings

# Try real redis first; fall back to fakeredis (tests), then to an in-memory shim.
try:
    import redis  # type: ignore

    HAVE_REDIS = True
except Exception:
    HAVE_REDIS = False

try:
    import fakeredis  # type: ignore

    HAVE_FAKEREDIS = True
except Exception:
    HAVE_FAKEREDIS = False


# Minimal in-memory shim (last resort)
class _Mem:
    def __init__(self):
        self._m: dict[str, str] = {}

    def get(self, k: str):
        return self._m.get(k)

    def setex(self, k: str, ttl: int, v: str):
        self._m[k] = v


_mem = _Mem()


def _make_client():
    s = get_settings()
    url = str(s.REDIS_URL) if s.REDIS_URL else ""
    if HAVE_REDIS and url:
        return redis.from_url(url, decode_responses=True)
    if HAVE_FAKEREDIS:
        return fakeredis.FakeRedis(decode_responses=True)
    return _mem


_client = _make_client()


def _key(tenant: str | None, query: str) -> str:
    tenant = tenant or "public"
    return f"semfaq:{tenant}:{query.strip().lower()}"


def get_semcache(a: str, b: str | None = None) -> dict | None:
    """Compatibility wrapper:
    - get_semcache(query) -> old callers
    - get_semcache(tenant, query) -> new callers
    """
    if b is None:
        tenant = "public"
        query = a
    else:
        tenant = a
        query = b
    raw = _client.get(_key(tenant, query))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_semcache(
    a: str, b: str | None = None, value: dict | None = None, ttl_seconds: int = 3600
) -> None:
    """Compatibility wrapper:
    - set_semcache(query, payload)
    - set_semcache(tenant, query, payload)
    """
    if value is None:
        # called as set_semcache(query, payload)
        query = a
        payload = b or {}
        tenant = "public"
    else:
        tenant = a
        query = b or ""
        payload = value
    _client.setex(_key(tenant, query), ttl_seconds, json.dumps(payload))
