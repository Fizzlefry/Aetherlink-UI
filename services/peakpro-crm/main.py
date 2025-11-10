"""
PeakPro CRM - Standalone CRM Service
Can run independently or integrate with AetherLink
"""

import os
from datetime import UTC, datetime

from db import get_db, init_db
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from prometheus_client import Gauge
from pydantic import BaseModel

app = FastAPI(title="PeakPro CRM", version="1.0.0")

# Phase XVI M1: AetherLink service health metric
SERVICE_NAME = os.getenv("SERVICE_NAME", "peakpro")
SERVICE_ENV = os.getenv("AETHER_ENV", "local")

aether_service_up = Gauge(
    "aether_service_up", "Service reachability flag for AetherLink monitoring", ["service", "env"]
)

# Initialize database on startup
init_db()

# Phase XVI M1: Mark service as up on startup
aether_service_up.labels(service=SERVICE_NAME, env=SERVICE_ENV).set(1)

# Auth configuration
RAW_KEYS = os.getenv("APP_KEYS") or os.getenv("APP_KEY", "local-dev-key")
VALID_KEYS = {k.strip() for k in RAW_KEYS.split(",") if k.strip()}


async def verify_app_key(request: Request, x_app_key: str | None = Header(default=None)):
    """Verify API key for write operations - supports multiple keys"""
    if not x_app_key or x_app_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-App-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    # Return the key for use in handlers
    print(f"[PeakPro CRM] verify_app_key called with key: {x_app_key}")
    return x_app_key


# Models
class Contact(BaseModel):
    id: int | None = None
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    created_at: str | None = None


class Deal(BaseModel):
    id: int | None = None
    title: str
    contact_id: int | None = None
    value: float
    stage: str = "new"  # new, qualified, proposal, negotiation, won, lost
    probability: int = 50
    created_at: str | None = None
    updated_at: str | None = None


class Note(BaseModel):
    id: int | None = None
    contact_id: int
    content: str
    created_at: str | None = None


# Health endpoint
@app.get("/health")
def health():
    return {"status": "ok", "service": "peakpro-crm"}


# AI Snapshot endpoint
@app.get("/ai/snapshot")
def ai_snapshot():
    """AI-friendly view of CRM data"""
    from datetime import datetime

    now = datetime.now()

    # Read from database
    with get_db() as conn:
        contacts = conn.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC LIMIT 25"
        ).fetchall()
        deals = conn.execute("SELECT * FROM deals ORDER BY updated_at DESC LIMIT 25").fetchall()
        notes = conn.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT 25").fetchall()

    contacts_list = [dict(c) for c in contacts]
    deals_list = [dict(d) for d in deals]
    notes_list = [dict(n) for n in notes]

    # Find stale deals (no update in 7 days)
    stale_deals = []
    for deal in deals_list:
        if deal.get("updated_at"):
            try:
                updated = datetime.fromisoformat(deal["updated_at"])
                if (now - updated).days > 7:
                    stale_deals.append(deal)
            except:
                pass

    # Find contacts without recent notes
    contacts_needing_followup = []
    for contact in contacts_list:
        contact_notes = [n for n in notes_list if n.get("contact_id") == contact.get("id")]
        if not contact_notes:
            contacts_needing_followup.append(contact)

    # Build recommendations
    recommendations = []
    if stale_deals:
        recommendations.append(
            {
                "priority": "medium",
                "category": "deals",
                "message": f"{len(stale_deals)} deals have not been updated in 7+ days",
                "action": "Review and update stale deals",
            }
        )

    if contacts_needing_followup:
        recommendations.append(
            {
                "priority": "low",
                "category": "contacts",
                "message": f"{len(contacts_needing_followup)} contacts have no notes",
                "action": "Add notes or schedule follow-up",
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "priority": "low",
                "category": "status",
                "message": "All CRM data is up to date",
                "action": "No action required",
            }
        )

    return {
        "timestamp": now.isoformat(),
        "contacts": {
            "total": len(contacts_list),
            "recent": contacts_list[:5],
            "needing_followup": contacts_needing_followup[:3],
        },
        "deals": {
            "total": len(deals_list),
            "open": [d for d in deals_list if d.get("stage") not in ["won", "lost"]],
            "stale": stale_deals[:3],
            "total_value": sum(
                d.get("value", 0) for d in deals_list if d.get("stage") not in ["lost"]
            ),
        },
        "notes": {"total": len(notes_list), "recent": notes_list[:5]},
        "recommendations": recommendations,
    }


# CRM Endpoints - Contacts
@app.get("/crm/contacts")
def list_contacts():
    with get_db() as conn:
        contacts = conn.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
    return [dict(c) for c in contacts]


@app.post("/crm/contacts")
def create_contact(
    contact: Contact, x_app_key: str | None = Header(default=None, alias="x-app-key")
):
    print(f"[PeakPro CRM] Received x_app_key: {x_app_key}")
    # Verify API key
    if not x_app_key or x_app_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-App-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Per-key attribution: use the verified key
    used_key = x_app_key
    print(f"[PeakPro CRM] About to insert with key: {used_key}")

    now = datetime.now().isoformat()
    with get_db() as conn:
        print(
            f"[PeakPro CRM] Executing INSERT with values: {contact.name}, {contact.email}, {contact.phone}, {contact.company}, {now}, {used_key}"
        )
        cur = conn.execute(
            "INSERT INTO contacts (name, email, phone, company, created_at, created_by_key) VALUES (?, ?, ?, ?, ?, ?)",
            (contact.name, contact.email, contact.phone, contact.company, now, used_key),
        )
        contact_id = cur.lastrowid
        print(f"[PeakPro CRM] Inserted contact {contact_id} with key {used_key}")

        # Verify what was inserted
        inserted = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        print(f"[PeakPro CRM] Retrieved contact: {dict(inserted) if inserted else 'None'}")

        conn.commit()

    return {
        "id": contact_id,
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "company": contact.company,
        "created_at": now,
    }


@app.get("/crm/contacts/{contact_id}")
def get_contact(contact_id: int):
    with get_db() as conn:
        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if contact:
        return dict(contact)
    raise HTTPException(status_code=404, detail="Contact not found")


# CRM Endpoints - Deals
@app.get("/crm/deals")
def list_deals():
    with get_db() as conn:
        deals = conn.execute("SELECT * FROM deals ORDER BY updated_at DESC").fetchall()
    return [dict(d) for d in deals]


@app.post("/crm/deals", dependencies=[Depends(verify_app_key)])
def create_deal(deal: Deal, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[PeakPro CRM] Deal created via key: {used_key}")

    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO deals (title, value, stage, probability, contact_id, created_at, updated_at, created_by_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                deal.title,
                deal.value,
                deal.stage,
                deal.probability,
                deal.contact_id,
                now,
                now,
                used_key,
            ),
        )
        deal_id = cur.lastrowid
        conn.commit()

    return {
        "id": deal_id,
        "title": deal.title,
        "contact_id": deal.contact_id,
        "value": deal.value,
        "stage": deal.stage,
        "probability": deal.probability,
        "created_at": now,
        "updated_at": now,
    }


# CRM Endpoints - Notes
@app.get("/crm/contacts/{contact_id}/notes")
def get_contact_notes(contact_id: int):
    with get_db() as conn:
        notes = conn.execute(
            "SELECT * FROM notes WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,)
        ).fetchall()
    return [dict(n) for n in notes]


@app.post("/crm/contacts/{contact_id}/notes", dependencies=[Depends(verify_app_key)])
def create_note(contact_id: int, note: Note, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[PeakPro CRM] Note created via key: {used_key}")

    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO notes (contact_id, content, created_at, created_by_key) VALUES (?, ?, ?, ?)",
            (contact_id, note.content, now, used_key),
        )
        note_id = cur.lastrowid
        conn.commit()

    return {"id": note_id, "contact_id": contact_id, "content": note.content, "created_at": now}


@app.get("/stats")
def get_stats():
    """Lightweight operational stats for PeakPro CRM."""
    today = datetime.now(UTC).date().isoformat()

    with get_db() as conn:
        total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]

        total_deals = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]

        deals_today = conn.execute(
            "SELECT COUNT(*) FROM deals WHERE created_at >= ?", (today,)
        ).fetchone()[0]

        contacts_today = conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE created_at >= ?", (today,)
        ).fetchone()[0]

        # Attribution: last created by key and top creators
        last_created_by_key = conn.execute("""
            SELECT created_by_key FROM (
                SELECT created_by_key, created_at FROM contacts WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key, created_at FROM deals WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key, created_at FROM notes WHERE created_by_key IS NOT NULL
            ) ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        top_creator_keys = conn.execute("""
            SELECT created_by_key, COUNT(*) as count FROM (
                SELECT created_by_key FROM contacts WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key FROM deals WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key FROM notes WHERE created_by_key IS NOT NULL
            ) GROUP BY created_by_key ORDER BY count DESC LIMIT 3
        """).fetchall()

    # Build attribution section
    attribution = {}
    if last_created_by_key and last_created_by_key[0]:
        attribution["last_created_by_key"] = last_created_by_key[0]

    if top_creator_keys:
        attribution["top_creator_keys"] = [
            {"key": row[0], "count": row[1]} for row in top_creator_keys
        ]

    return {
        "service": "peakpro-crm",
        "summary": {
            "contacts": total_contacts,
            "deals": total_deals,
            "contacts_today": contacts_today,
            "deals_today": deals_today,
        },
        # flat for backward-compat / quick UI
        "contacts": total_contacts,
        "deals": total_deals,
        "contacts_today": contacts_today,
        "deals_today": deals_today,
        "timestamp": datetime.now(UTC).isoformat(),
        "attribution": attribution,
    }


@app.get("/keys")
def get_configured_keys():
    """Return the API keys configured for this service (read-only, no auth required)"""
    return {
        "service": "peakpro-crm",
        "keys": list(VALID_KEYS),
        "timestamp": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8021))
    uvicorn.run(app, host="0.0.0.0", port=port)
