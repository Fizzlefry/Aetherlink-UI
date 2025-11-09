"""
PolicyPal AI - Insurance Policy Management & Analysis Service
Can run independently or integrate with AetherLink
"""
from fastapi import FastAPI, Depends, HTTPException, Header, status, Request, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import os
from db import init_db, get_db
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

app = FastAPI(title="PolicyPal AI", version="1.0.0")

# Phase XVI M1: AetherLink service health metric
SERVICE_NAME = os.getenv("SERVICE_NAME", "policypal")
SERVICE_ENV = os.getenv("AETHER_ENV", "local")

aether_service_up = Gauge(
    "aether_service_up",
    "Service reachability flag for AetherLink monitoring",
    ["service", "env"]
)

# Initialize database on startup
init_db()

# Phase XVI M1: Mark service as up on startup
aether_service_up.labels(service=SERVICE_NAME, env=SERVICE_ENV).set(1)

# Auth configuration
APP_KEY = os.getenv("APP_KEY", "local-dev-key")  # Backward compatibility
APP_KEYS = os.getenv("APP_KEYS", APP_KEY)  # Support multiple keys
VALID_KEYS = set(key.strip() for key in APP_KEYS.split(",") if key.strip())

async def verify_app_key(
    request: Request,
    x_app_key: Optional[str] = Header(default=None)
):
    """Verify API key for write operations"""
    if not x_app_key or x_app_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-App-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    # Stash key for downstream handlers (per-key attribution)
    request.state.app_key = x_app_key

# Models
class Policy(BaseModel):
    id: Optional[int] = None
    policy_number: str
    policy_type: str  # auto, home, life, health, business
    carrier: str
    policyholder: str
    effective_date: str
    expiration_date: str
    premium_amount: Optional[float] = None
    coverage_amount: Optional[float] = None
    coverage_details: Optional[Dict[str, Any]] = None
    exclusions: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    documents: List[str] = []  # URLs or file paths
    summary: Optional[str] = None
    created_at: Optional[str] = None

class PolicyIngest(BaseModel):
    policy_data: Dict[str, Any]  # Raw policy data to parse

class AIActionRequest(BaseModel):
    action: str  # summarize_policy, extract_coverage, compare_policies
    policy_id: Optional[int] = None
    policy_ids: Optional[List[int]] = None
    parameters: Optional[Dict[str, Any]] = None

# Health endpoint
@app.get("/health")
def health():
    return {"status": "ok", "service": "policypal-ai"}

# AI Snapshot endpoint
@app.get("/ai/snapshot")
def ai_snapshot():
    """AI-friendly view of policy data"""
    from datetime import datetime, timedelta

    now = datetime.now()

    with get_db() as conn:
        cursor = conn.cursor()

        # Get all policies from database
        cursor.execute("SELECT * FROM policies")
        rows = cursor.fetchall()
        policies = [dict(row) for row in rows]

    # Find expiring policies (within 30 days)
    expiring_soon = []
    for policy in policies:
        try:
            exp_date = datetime.fromisoformat(policy.get("expiration_date", ""))
            days_until = (exp_date - now).days
            if 0 < days_until <= 30:
                expiring_soon.append({**policy, "days_until_expiration": days_until})
        except:
            pass

    # Find policies without summaries
    needs_summary = [p for p in policies if not p.get("summary")]

    # Recent policies
    recent = sorted(policies, key=lambda p: p.get("created_at", ""), reverse=True)[:5]

    # Build recommendations
    recommendations = []

    if expiring_soon:
        recommendations.append({
            "priority": "high",
            "category": "expiration",
            "message": f"{len(expiring_soon)} policies expiring within 30 days",
            "action": "Review and renew expiring policies"
        })

    if needs_summary:
        recommendations.append({
            "priority": "low",
            "category": "documentation",
            "message": f"{len(needs_summary)} policies missing AI summaries",
            "action": "Generate summaries using /ai/action"
        })

    if not recommendations:
        recommendations.append({
            "priority": "low",
            "category": "status",
            "message": "All policies are up to date",
            "action": "No action required"
        })

    return {
        "timestamp": now.isoformat(),
        "policies": {
            "total": len(policies),
            "recent": recent,
            "expiring_soon": expiring_soon[:5],
            "needs_summary": needs_summary[:3],
            "by_type": _group_by_type(policies)
        },
        "recommendations": recommendations
    }

def _group_by_type(policies):
    """Group policies by type"""
    result = {}
    for p in policies:
        policy_type = p.get("policy_type", "unknown")
        if policy_type not in result:
            result[policy_type] = 0
        result[policy_type] += 1
    return result

# Policy Endpoints
@app.get("/pp/policies")
def list_policies():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM policies ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.post("/pp/policies", dependencies=[Depends(verify_app_key)])
def create_policy(policy: Policy, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[PolicyPal AI] Policy created via key: {used_key}")
    
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO policies (
                policy_number, policy_type, carrier, policyholder,
                effective_date, expiration_date, premium_amount,
                coverage_amount, summary, created_at, created_by_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            policy.policy_number,
            policy.policy_type,
            policy.carrier,
            policy.policyholder,
            policy.effective_date,
            policy.expiration_date,
            policy.premium_amount,
            policy.coverage_amount,
            policy.summary,
            now,
            used_key
        ))
        conn.commit()
        policy_id = cursor.lastrowid

    return {
        "id": policy_id,
        "policy_number": policy.policy_number,
        "policy_type": policy.policy_type,
        "carrier": policy.carrier,
        "policyholder": policy.policyholder,
        "effective_date": policy.effective_date,
        "expiration_date": policy.expiration_date,
        "premium_amount": policy.premium_amount,
        "coverage_amount": policy.coverage_amount,
        "summary": policy.summary,
        "created_at": now
    }

@app.get("/pp/policies/{policy_id}")
def get_policy(policy_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM policies WHERE id = ?", (policy_id,))
        row = cursor.fetchone()

    if row:
        return dict(row)
    return {"error": "Policy not found"}, 404

@app.post("/pp/policies/ingest")
def ingest_policy(data: PolicyIngest):
    """Ingest raw policy data and create structured policy"""
    # In production, this would parse PDF/JSON and extract fields
    # For now, just create a basic policy from the data
    raw = data.policy_data

    # Get count for default policy number
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM policies")
        count = cursor.fetchone()[0]

    policy_number = raw.get("policy_number", f"POL-{count + 1}")
    policy_type = raw.get("type", "unknown")
    carrier = raw.get("carrier", "Unknown")
    policyholder = raw.get("policyholder", "Unknown")
    effective_date = raw.get("effective_date", datetime.now().isoformat())
    expiration_date = raw.get("expiration_date", (datetime.now() + timedelta(days=365)).isoformat())
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO policies (
                policy_number, policy_type, carrier, policyholder,
                effective_date, expiration_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            policy_number,
            policy_type,
            carrier,
            policyholder,
            effective_date,
            expiration_date,
            now
        ))
        conn.commit()
        policy_id = cursor.lastrowid

    policy = {
        "id": policy_id,
        "policy_number": policy_number,
        "policy_type": policy_type,
        "carrier": carrier,
        "policyholder": policyholder,
        "effective_date": effective_date,
        "expiration_date": expiration_date,
        "created_at": now
    }

    return {"status": "ingested", "policy": policy}

@app.get("/pp/policies/search")
def search_policies(query: str = ""):
    """Simple search across policies"""
    with get_db() as conn:
        cursor = conn.cursor()
        if not query:
            cursor.execute("SELECT * FROM policies ORDER BY created_at DESC")
        else:
            query_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM policies
                WHERE policy_number LIKE ? OR carrier LIKE ? OR policyholder LIKE ?
                ORDER BY created_at DESC
            """, (query_pattern, query_pattern, query_pattern))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.post("/ai/action")
def ai_action(request: AIActionRequest):
    """Execute AI actions on policies"""
    action = request.action

    if action == "summarize_policy":
        if not request.policy_id:
            return {"error": "policy_id required"}, 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM policies WHERE id = ?", (request.policy_id,))
            row = cursor.fetchone()

        if not row:
            return {"error": "Policy not found"}, 404

        policy = dict(row)

        # Generate simple summary
        summary = f"Policy {policy.get('policy_number')} is a {policy.get('policy_type')} policy from {policy.get('carrier')} for {policy.get('policyholder')}. "
        summary += f"Coverage amount: ${policy.get('coverage_amount', 0):,.2f}. "
        summary += f"Expires: {policy.get('expiration_date')}."

        # Update policy with summary in database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE policies SET summary = ? WHERE id = ?",
                (summary, request.policy_id)
            )
            conn.commit()

        return {"action": "summarize_policy", "summary": summary}

    elif action == "extract_coverage":
        if not request.policy_id:
            return {"error": "policy_id required"}, 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM policies WHERE id = ?", (request.policy_id,))
            row = cursor.fetchone()

        if not row:
            return {"error": "Policy not found"}, 404

        policy = dict(row)

        return {
            "action": "extract_coverage",
            "coverage_amount": policy.get("coverage_amount"),
        }

    elif action == "compare_policies":
        if not request.policy_ids or len(request.policy_ids) < 2:
            return {"error": "At least 2 policy_ids required"}, 400

        with get_db() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(request.policy_ids))
            cursor.execute(
                f"SELECT * FROM policies WHERE id IN ({placeholders})",
                request.policy_ids
            )
            rows = cursor.fetchall()

        policies_to_compare = [dict(row) for row in rows]

        if len(policies_to_compare) < 2:
            return {"error": "Not enough policies found"}, 404

        comparison = {
            "action": "compare_policies",
            "policies": policies_to_compare,
            "differences": {
                "carriers": list(set(p.get("carrier") for p in policies_to_compare)),
                "types": list(set(p.get("policy_type") for p in policies_to_compare)),
                "coverage_amounts": [p.get("coverage_amount") for p in policies_to_compare]
            }
        }

        return comparison

    else:
        return {"error": f"Unknown action: {action}"}, 400

@app.get("/stats")
def get_pp_stats():
    """Operational stats for PolicyPal AI."""
    today = datetime.now(timezone.utc).date().isoformat()

    with get_db() as conn:
        total_policies = conn.execute(
            "SELECT COUNT(*) FROM policies"
        ).fetchone()[0]

        policies_today = conn.execute(
            "SELECT COUNT(*) FROM policies WHERE created_at >= ?",
            (today,)
        ).fetchone()[0]

        # optional: count expiring in next 30 days
        expiring_soon = conn.execute(
            """
            SELECT COUNT(*)
            FROM policies
            WHERE expiration_date IS NOT NULL
              AND expiration_date <= date('now', '+30 day')
            """
        ).fetchone()[0]

        # Attribution: last created by key and top creators
        last_created_by_key = conn.execute("""
            SELECT created_by_key FROM policies 
            WHERE created_by_key IS NOT NULL 
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        top_creator_keys = conn.execute("""
            SELECT created_by_key, COUNT(*) as count FROM policies 
            WHERE created_by_key IS NOT NULL 
            GROUP BY created_by_key ORDER BY count DESC LIMIT 3
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
        "service": "policypal-ai",
        "summary": {
            "policies": total_policies,
            "policies_today": policies_today,
            "expiring_soon": expiring_soon,
        },
        "policies": total_policies,
        "policies_today": policies_today,
        "expiring_soon": expiring_soon,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
    }

@app.get("/keys")
def get_configured_keys():
    """Return the API keys configured for this service (read-only, no auth required)"""
    return {
        "service": "policypal-ai",
        "keys": list(VALID_KEYS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8023))
    uvicorn.run(app, host="0.0.0.0", port=port)
