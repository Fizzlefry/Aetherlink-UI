import importlib

import fakeredis

from pods.customer_ops.api import lead_store


def _fake_client():
    return fakeredis.FakeRedis(decode_responses=True)

def test_lead_roundtrip(monkeypatch):
    from pods.customer_ops.api import cache
    monkeypatch.setattr(cache, "get_redis_client", _fake_client)
    importlib.reload(lead_store)

    lid = lead_store.create_lead(tenant="acme", name="Jon", phone="7632801272", details="Metal roof")
    got = lead_store.get_lead(lid)
    assert got and got["id"] == lid and got["tenant"] == "acme"

    items = lead_store.list_leads(tenant="acme", limit=10)
    assert any(i["id"] == lid for i in items)
