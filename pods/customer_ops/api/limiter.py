from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from fastapi import Request

_limiter_ready = False

async def init_rate_limiter(redis_url: str) -> None:
    """Try to init limiter; if Redis not ready, degrade gracefully."""
    global _limiter_ready
    try:
        from redis import asyncio as aioredis
        r = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(r)
        _limiter_ready = True
    except Exception as e:
        print(f"[WARN] Rate limiter disabled (Redis not ready): {e}")
        _limiter_ready = False

def _dep_safe(times: int, seconds: int, msg: str):
    if _limiter_ready:
        # Use default error handling; custom 429 response is defined in main.py
        return RateLimiter(times=times, seconds=seconds)
    async def _noop(_: Request):  # no-op when limiter is off
        return
    return _noop

def _parse_rate(rate: str) -> tuple[int, int]:
    # e.g., "10/minute" -> (10, 60)
    n, unit = rate.split("/", 1)
    n = int(n.strip())
    unit = unit.strip().lower()
    seconds = {
        "second": 1, "minute": 60, "hour": 3600, "day": 86400
    }[unit]
    return n, seconds

def ops_limit_dep():
    return _dep_safe(5, 60, "Too many /ops requests; slow down.")

def faq_limit_dep():
    from .config import get_settings
    s = get_settings()
    n, seconds = _parse_rate(s.RATE_LIMIT_FAQ)
    return _dep_safe(n, seconds, "Too many FAQ requests; slow down.")

def chat_limit_dep():
    from .config import get_settings
    s = get_settings()
    n, seconds = _parse_rate(s.RATE_LIMIT_CHAT)
    return _dep_safe(n, seconds, "Too many chat requests; slow down.")
