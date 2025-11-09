"""
RoofWonder - Roofing Job Management Service
Can run independently or integrate with AetherLink
"""
from fastapi import FastAPI, Depends, HTTPException, Header, status, File, UploadFile, Request, Response
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timezone
import os
import httpx
from db import init_db, get_db
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, Counter

app = FastAPI(title="RoofWonder", version="1.0.0")

# Phase XVI M1: AetherLink service health metric
SERVICE_NAME = os.getenv("SERVICE_NAME", "roofwonder")
SERVICE_ENV = os.getenv("AETHER_ENV", "local")

aether_service_up = Gauge(
    "aether_service_up",
    "Service reachability flag for AetherLink monitoring",
    ["service", "env"]
)

# Phase XXII: Business metric for RoofWonder leads/jobs
roofwonder_leads_ingested_total = Counter(
    "roofwonder_leads_ingested_total",
    "Total leads captured by RoofWonder",
    ["env"]
)

# Initialize database on startup
init_db()

# Phase XVI M1: Mark service as up on startup
aether_service_up.labels(service=SERVICE_NAME, env=SERVICE_ENV).set(1)

# Auth configuration
RAW_KEYS = os.getenv("APP_KEYS") or os.getenv("APP_KEY", "local-dev-key")
VALID_KEYS = {k.strip() for k in RAW_KEYS.split(",") if k.strip()}
MEDIA_API = os.getenv("MEDIA_API", "http://localhost:9109")

async def verify_app_key(
    request: Request,
    x_app_key: Optional[str] = Header(default=None)
):
    """Verify API key for write operations - supports multiple keys"""
    if not x_app_key or x_app_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-App-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    # Stash key for downstream handlers (per-key attribution)
    request.state.app_key = x_app_key

# Models
class Property(BaseModel):
    id: Optional[int] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    roof_type: Optional[str] = None  # shingle, metal, flat, tile
    roof_age: Optional[int] = None
    created_at: Optional[str] = None

class Job(BaseModel):
    id: Optional[int] = None
    customer_name: str
    property_id: Optional[int] = None
    address: str
    status: str = "scheduled"  # scheduled, in_progress, completed, cancelled
    scheduled_date: Optional[str] = None
    completion_date: Optional[str] = None
    photos: List[str] = []
    estimate_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

class Estimate(BaseModel):
    id: Optional[int] = None
    job_id: int
    materials_cost: float
    labor_cost: float
    total_cost: float
    notes: Optional[str] = None
    created_at: Optional[str] = None

# Health endpoint
@app.get("/health")
def health():
    return {"status": "ok", "service": "roofwonder"}

# AI Snapshot endpoint
@app.get("/ai/snapshot")
def ai_snapshot():
    """AI-friendly view of roofing jobs"""
    from datetime import datetime

    now = datetime.now()
    today_str = now.date().isoformat()

    # Read from database
    with get_db() as conn:
        jobs = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50").fetchall()
        properties = conn.execute("SELECT * FROM properties ORDER BY created_at DESC LIMIT 25").fetchall()
        estimates = conn.execute("SELECT * FROM estimates ORDER BY created_at DESC LIMIT 25").fetchall()

        # Get photo counts for jobs
        photo_counts = {}
        for row in conn.execute("SELECT job_id, COUNT(*) as count FROM job_photos GROUP BY job_id"):
            photo_counts[row["job_id"]] = row["count"]

    jobs_list = [dict(j) for j in jobs]
    properties_list = [dict(p) for p in properties]
    estimates_list = [dict(e) for e in estimates]

    # Find today's jobs
    jobs_today = []
    for job in jobs_list:
        scheduled_date = job.get("scheduled_date") or ""
        if scheduled_date and scheduled_date.startswith(today_str):
            jobs_today.append(job)

    # Find jobs missing photos
    missing_photos = [
        j for j in jobs_list
        if j.get("status") == "completed" and photo_counts.get(j.get("id"), 0) == 0
    ]

    # Find stalled jobs (in_progress but scheduled > 3 days ago)
    stalled_jobs = []
    for job in jobs_list:
        if job.get("status") == "in_progress":
            scheduled_date = job.get("scheduled_date")
            if scheduled_date:
                try:
                    scheduled = datetime.fromisoformat(scheduled_date)
                    if (now - scheduled).days > 3:
                        stalled_jobs.append(job)
                except:
                    pass

    # Build recommendations
    recommendations = []

    if jobs_today:
        recommendations.append({
            "priority": "high",
            "category": "jobs",
            "message": f"{len(jobs_today)} jobs scheduled for today",
            "action": "Review job details and crew assignments"
        })

    if missing_photos:
        recommendations.append({
            "priority": "medium",
            "category": "jobs",
            "message": f"{len(missing_photos)} completed jobs missing photos",
            "action": "Upload completion photos for documentation"
        })

    if stalled_jobs:
        recommendations.append({
            "priority": "high",
            "category": "jobs",
            "message": f"{len(stalled_jobs)} jobs in progress for 3+ days",
            "action": "Check job status and update or close"
        })

    if not recommendations:
        recommendations.append({
            "priority": "low",
            "category": "status",
            "message": "All jobs on track",
            "action": "No action required"
        })

    return {
        "timestamp": now.isoformat(),
        "jobs": {
            "total": len(jobs_list),
            "today": jobs_today,
            "in_progress": [j for j in jobs_list if j.get("status") == "in_progress"],
            "completed_this_week": [j for j in jobs_list if j.get("status") == "completed"][:7],
            "missing_photos": missing_photos[:3],
            "stalled": stalled_jobs[:3]
        },
        "properties": {
            "total": len(properties_list),
            "recent": properties_list[:5]
        },
        "estimates": {
            "total": len(estimates_list),
            "recent": estimates_list[:5]
        },
        "recommendations": recommendations
    }

# Roofing Endpoints - Jobs
@app.get("/rw/jobs")
def list_jobs():
    with get_db() as conn:
        jobs = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [dict(j) for j in jobs]

@app.post("/rw/jobs", dependencies=[Depends(verify_app_key)])
def create_job(job: Job, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[RoofWonder] Job created via key: {used_key}")
    
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (customer_name, property_id, address, status, scheduled_date, completion_date, estimate_amount, actual_amount, notes, created_at, created_by_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job.customer_name, job.property_id, job.address, job.status, job.scheduled_date, job.completion_date, job.estimate_amount, job.actual_amount, job.notes, now, used_key)
        )
        job_id = cur.lastrowid
        conn.commit()

    # Phase XXII: Increment business metric for new leads
    roofwonder_leads_ingested_total.labels(env=SERVICE_ENV).inc()

    return {
        "id": job_id,
        "customer_name": job.customer_name,
        "property_id": job.property_id,
        "address": job.address,
        "status": job.status,
        "scheduled_date": job.scheduled_date,
        "completion_date": job.completion_date,
        "photos": job.photos,
        "estimate_amount": job.estimate_amount,
        "actual_amount": job.actual_amount,
        "notes": job.notes,
        "created_at": now
    }

@app.get("/rw/jobs/{job_id}")
def get_job(job_id: int):
    with get_db() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        photos = conn.execute(
            "SELECT photo_url, created_at FROM job_photos WHERE job_id = ? ORDER BY created_at DESC",
            (job_id,),
        ).fetchall()

    job_dict = dict(job)
    job_dict["photos"] = [dict(p) for p in photos]
    return job_dict

@app.post("/rw/jobs/{job_id}/photos")
async def upload_job_photo(job_id: int, file: UploadFile = File(...)):
    """Upload a photo for a job via media service"""
    # Per-key attribution: log which key was used (would need request injection for this)
    print(f"[RoofWonder] Photo uploaded")
    
    # 1) Forward to media-service
    file_content = await file.read()
    files = {"file": (file.filename, file_content, file.content_type)}
    data = {"job_id": str(job_id)}

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{MEDIA_API}/upload", files=files, data=data)

    if r.status_code != 200:
        raise HTTPException(500, "Failed to upload to media service")

    media_res = r.json()
    photo_url = media_res["url"]
    now = datetime.now().isoformat()

    # 2) Store in RoofWonder DB
    used_key = None  # Would need request injection to get this
    with get_db() as conn:
        conn.execute(
            "INSERT INTO job_photos (job_id, photo_url, created_at, created_by_key) VALUES (?, ?, ?, ?)",
            (job_id, photo_url, now, used_key),
        )
        conn.commit()

    return {
        "status": "ok",
        "job_id": job_id,
        "photo_url": photo_url,
        "uploaded_at": now,
    }

# Roofing Endpoints - Properties
@app.get("/rw/properties")
def list_properties():
    with get_db() as conn:
        properties = conn.execute("SELECT * FROM properties ORDER BY created_at DESC").fetchall()
    return [dict(p) for p in properties]

@app.post("/rw/properties", dependencies=[Depends(verify_app_key)])
def create_property(prop: Property, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[RoofWonder] Property created via key: {used_key}")
    
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO properties (address, city, state, zip_code, roof_type, roof_age, created_at, created_by_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (prop.address, prop.city, prop.state, prop.zip_code, prop.roof_type, prop.roof_age, now, used_key)
        )
        property_id = cur.lastrowid
        conn.commit()

    return {
        "id": property_id,
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip_code": prop.zip_code,
        "roof_type": prop.roof_type,
        "roof_age": prop.roof_age,
        "created_at": now
    }

# Roofing Endpoints - Estimates
@app.get("/rw/estimates")
def list_estimates():
    with get_db() as conn:
        estimates = conn.execute("SELECT * FROM estimates ORDER BY created_at DESC").fetchall()
    return [dict(e) for e in estimates]

@app.post("/rw/estimates", dependencies=[Depends(verify_app_key)])
def create_estimate(estimate: Estimate, request: Request):
    # Per-key attribution: log which key was used
    used_key = getattr(request.state, "app_key", None)
    print(f"[RoofWonder] Estimate created via key: {used_key}")
    
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO estimates (job_id, materials_cost, labor_cost, total_cost, notes, created_at, created_by_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (estimate.job_id, estimate.materials_cost, estimate.labor_cost, estimate.total_cost, estimate.notes, now, used_key)
        )
        estimate_id = cur.lastrowid
        conn.commit()

    return {
        "id": estimate_id,
        "job_id": estimate.job_id,
        "materials_cost": estimate.materials_cost,
        "labor_cost": estimate.labor_cost,
        "total_cost": estimate.total_cost,
        "notes": estimate.notes,
        "created_at": now
    }

@app.get("/stats")
def get_rw_stats():
    """Operational stats for RoofWonder."""
    today = datetime.now(timezone.utc).date().isoformat()

    with get_db() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        total_properties = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        total_estimates = conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0]
        total_photos = conn.execute("SELECT COUNT(*) FROM job_photos").fetchone()[0]

        jobs_today = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE created_at >= ?",
            (today,)
        ).fetchone()[0]

        photos_today = conn.execute(
            "SELECT COUNT(*) FROM job_photos WHERE created_at >= ?",
            (today,)
        ).fetchone()[0]

        # Attribution: last created by key and top creators
        last_created_by_key = conn.execute("""
            SELECT created_by_key FROM (
                SELECT created_by_key, created_at FROM jobs WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key, created_at FROM properties WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key, created_at FROM estimates WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key, created_at FROM job_photos WHERE created_by_key IS NOT NULL
            ) ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        top_creator_keys = conn.execute("""
            SELECT created_by_key, COUNT(*) as count FROM (
                SELECT created_by_key FROM jobs WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key FROM properties WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key FROM estimates WHERE created_by_key IS NOT NULL
                UNION ALL
                SELECT created_by_key FROM job_photos WHERE created_by_key IS NOT NULL
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
        "service": "roofwonder",
        "summary": {
            "jobs": total_jobs,
            "properties": total_properties,
            "estimates": total_estimates,
            "photos": total_photos,
            "jobs_today": jobs_today,
            "photos_today": photos_today,
        },
        "jobs": total_jobs,
        "properties": total_properties,
        "estimates": total_estimates,
        "photos": total_photos,
        "jobs_today": jobs_today,
        "photos_today": photos_today,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
    }

@app.get("/keys")
def get_configured_keys():
    """Return the API keys configured for this service (read-only, no auth required)"""
    return {
        "service": "roofwonder",
        "keys": list(VALID_KEYS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for AetherLink monitoring."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8022))
    uvicorn.run(app, host="0.0.0.0", port=port)
