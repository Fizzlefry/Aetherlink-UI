"""Test that the rate limiter gracefully degrades when Redis isn't available."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_limiter_init_fails_gracefully():
    """Verify init_rate_limiter doesn't crash when Redis is unavailable."""
    from api.limiter import init_rate_limiter

    # Simulate Redis connection failure (patch the redis.asyncio import)
    with patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis unavailable")):
        # Should not raise; limiter marks itself as not ready internally
        await init_rate_limiter("redis://fake:6379/0")


def test_rate_limit_dep_returns_callable():
    """Verify rate limit dependencies return callables (RateLimiter or no-op)."""
    from api.limiter import chat_limit_dep, faq_limit_dep, ops_limit_dep

    # When _limiter_ready is False, deps return async no-op functions
    # When ready, they return RateLimiter instances
    # Runtime behavior is validated in integration tests
    ops_dep = ops_limit_dep()
    faq_dep = faq_limit_dep()
    chat_dep = chat_limit_dep()

    # Each should be callable (either RateLimiter or async function)
    assert callable(ops_dep)
    assert callable(faq_dep)
    assert callable(chat_dep)
