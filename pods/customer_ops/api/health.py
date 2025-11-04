from __future__ import annotations

import contextlib
import time
from typing import Any

from redis import asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .session import engine

# Track application start time for uptime calculation
START_TIME = time.time()


async def get_health() -> dict[str, Any]:
    ok = True
    details: dict[str, Any] = {}

    # Uptime tracking
    uptime_seconds = int(time.time() - START_TIME)
    details["uptime_seconds"] = uptime_seconds
    details["uptime_human"] = _format_uptime(uptime_seconds)

    # DB check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        details["db"] = "ok"
    except SQLAlchemyError as e:
        details["db"] = "error"
        details["db_error"] = type(e).__name__
        ok = False

    # Redis check (non-fatal)
    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    if redis_url:
        try:
            r = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            with contextlib.suppress(Exception):
                pong = await r.ping()
                details["redis"] = "ok" if pong else "error"
        except Exception as e:
            details["redis"] = "error"
            details["redis_error"] = type(e).__name__
            # keep overall ok unless you want Redis to be required
    else:
        details["redis"] = "not_configured"

    details["ok"] = ok
    return details


def _format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"
