# pods/customer_ops/tests/test_memory_fakeredis.py
import os

os.environ["REDIS_URL"] = ""  # force in-memory fallback

from pods.customer_ops.api.memory import append_history, get_history


def test_memory_roundtrip_in_memory():
    append_history("public", "L123", "user", "Need a metal roof quote ASAP")
    hist = get_history("public", "L123", limit=5)
    assert len(hist) >= 1 and hist[0]["text"].startswith("Need a metal roof")
