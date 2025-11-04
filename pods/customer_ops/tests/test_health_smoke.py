import asyncio

from pods.customer_ops.api.health import get_health


def test_health_basic():
    result = asyncio.run(get_health())
    assert "ok" in result
    assert "db" in result  # True for sqlite (dev), may be False if DB intentionally down
