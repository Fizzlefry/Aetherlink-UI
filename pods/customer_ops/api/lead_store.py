import json
import time
import uuid
from typing import Any

from .cache import get_redis_client


LEAD_KEY = "lead:{id}"
TENANT_LEADS = "tenant:{tenant}:leads"

# Cache the redis client per-module so repeated calls in a single test run share the
# same backend instance. Tests may monkeypatch cache.get_redis_client to a factory;
# reloading this module resets _CLIENT to None which keeps tests isolated.
_CLIENT = None

def _get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = get_redis_client()
    return _CLIENT

def _lead_id() -> str:
    # ULID-ish sortable id: ts + random suffix
    return f"L{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

def create_lead(tenant: str, name: str, phone: str, details: str = "") -> str:
    rid = _lead_id()
    doc = {
        "id": rid,
        "tenant": tenant,
        "name": name,
        "phone": phone,
        "details": details,
        "created_at": int(time.time()),
    }
    r = _get_client()
    pipe = r.pipeline()
    pipe.set(LEAD_KEY.format(id=rid), json.dumps(doc))
    pipe.lpush(TENANT_LEADS.format(tenant=tenant), rid)
    pipe.execute()
    # Debug: print stored key and list length
    try:
        print("DEBUG: lead_created - key", LEAD_KEY.format(id=rid), "exists?", bool(r.get(LEAD_KEY.format(id=rid))))
        print("DEBUG: tenant list length", r.lrange(TENANT_LEADS.format(tenant=tenant), 0, -1))
    except Exception as e:
        print("DEBUG: lead_store debug failed", e)
    return rid

def get_lead(lead_id: str) -> dict[str, Any] | None:
    v = _get_client().get(LEAD_KEY.format(id=lead_id))
    return json.loads(v) if v else None

def list_leads(tenant: str, limit: int = 50) -> list[dict[str, Any]]:
    r = _get_client()
    ids = r.lrange(TENANT_LEADS.format(tenant=tenant), 0, max(0, limit - 1))
    out = []
    for lid in ids:
        # Redis returns bytes unless decode_responses=True. Ensure lid is str.
        if isinstance(lid, (bytes, bytearray)):
            lid = lid.decode()
        v = r.get(LEAD_KEY.format(id=lid))
        if v:
            out.append(json.loads(v))
    return out


# ============================================================================
# Outcome Tracking (Reward Model Foundation)
# ============================================================================

OUTCOME_KEY = "outcome:{lead_id}"
OUTCOME_LIST = "outcomes:all"  # Global list of all outcome records


def set_outcome(
    lead_id: str,
    outcome: str,
    notes: str = "",
    time_to_conversion: int | None = None,
) -> dict[str, Any]:
    """
    Record an outcome for a lead (booked, ghosted, qualified, etc.).
    Returns the outcome record with timestamp.
    """
    record = {
        "lead_id": lead_id,
        "outcome": outcome,
        "notes": notes,
        "recorded_at": int(time.time()),
        "time_to_conversion": time_to_conversion,
    }
    r = _get_client()
    pipe = r.pipeline()
    # Store outcome keyed by lead_id
    pipe.set(OUTCOME_KEY.format(lead_id=lead_id), json.dumps(record))
    # Append to global list for analytics
    pipe.lpush(OUTCOME_LIST, json.dumps(record))
    # Trim list to last 10k outcomes (adjust as needed)
    pipe.ltrim(OUTCOME_LIST, 0, 9999)
    pipe.execute()
    return record


def get_outcome(lead_id: str) -> dict[str, Any] | None:
    """Retrieve the outcome record for a specific lead."""
    v = _get_client().get(OUTCOME_KEY.format(lead_id=lead_id))
    return json.loads(v) if v else None


def list_outcomes(limit: int = 100) -> list[dict[str, Any]]:
    """List recent outcomes across all leads (for analytics)."""
    r = _get_client()
    raw = r.lrange(OUTCOME_LIST, 0, max(0, limit - 1))
    out = []
    for item in raw:
        if isinstance(item, (bytes, bytearray)):
            item = item.decode()
        out.append(json.loads(item))
    return out

