import json
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from .config import get_settings


# Try to import redis/fakeredis; fall back to in-memory shim for tests
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


# Type variable for generic return type
T = TypeVar('T')


class _RedisShim:
    """Very small in-memory shim implementing the subset of Redis API used in tests.

    Supports: get, set, setex, lpush, lrange, pipeline()
    """
    def __init__(self):
        self._store: dict = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: str):
        self._store[key] = value

    def setex(self, key: str, time: int, value: str):
        # ignore expiry in shim
        self._store[key] = value

    def lpush(self, key: str, value: str):
        lst = self._store.get(key) or []
        if not isinstance(lst, list):
            lst = []
        lst.insert(0, value)
        self._store[key] = lst

    def lrange(self, key: str, start: int, end: int):
        lst = self._store.get(key) or []
        return lst[start:end + 1]

    def pipeline(self):
        shim = self

        class Pipe:
            def __init__(self, shim):
                self._ops = []
                self._shim = shim

            def set(self, k, v):
                self._ops.append(('set', k, v))

            def lpush(self, k, v):
                self._ops.append(('lpush', k, v))

            def execute(self):
                for op, k, v in self._ops:
                    if op == 'set':
                        self._shim.set(k, v)
                    elif op == 'lpush':
                        self._shim.lpush(k, v)

        return Pipe(shim)


def get_redis_client():
    """Return a Redis-like client: prefer real redis (from URL), then fakeredis, else shim."""
    s = get_settings()
    url = str(s.REDIS_URL) if s.REDIS_URL else ""
    # reuse a single client/shim instance for the process to preserve state
    global _CLIENT
    try:
        if _CLIENT is not None:
            return _CLIENT
    except NameError:
        _CLIENT = None

    if HAVE_REDIS and url:
        try:
            return redis.from_url(
                url=url,
                socket_timeout=s.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=s.REDIS_SOCKET_CONNECT_TIMEOUT,
                decode_responses=True,
            )
        except Exception:
            # fall through to fakeredis/shim
            pass
    if HAVE_FAKEREDIS:
        _CLIENT = fakeredis.FakeRedis(decode_responses=True)
        return _CLIENT
    _CLIENT = _RedisShim()
    return _CLIENT


def cache_result(
    expire: int = 3600,  # 1 hour default
    prefix: str = "rag:",
    skip_keys: list[str] | None = None
) -> Callable:
    """
    Cache decorator that stores function results in Redis.
    
    Args:
        expire: Time in seconds before cache expires
        prefix: Redis key prefix for this cache
        skip_keys: List of kwargs to skip when creating cache key
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Create cache key from function name and arguments
            cache_dict = kwargs.copy()
            if skip_keys:
                for key in skip_keys:
                    cache_dict.pop(key, None)

            cache_key = f"{prefix}{func.__name__}:{json.dumps(cache_dict, sort_keys=True)}"

            # Try to get cached result
            redis_client = get_redis_client()
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Generate and cache result
            result = func(*args, **kwargs)
            redis_client.setex(
                name=cache_key,
                time=expire,
                value=json.dumps(result)
            )
            return result

        return wrapper
    return decorator
