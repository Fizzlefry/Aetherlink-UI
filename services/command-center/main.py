from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from rbac import require_roles
from audit import audit_middleware, get_audit_stats

app = FastAPI(title="AetherLink Command Center", version="0.1.0")

# Phase III M6: Security Audit Logging
app.middleware("http")(audit_middleware)

# RBAC: Only operators and admins can access ops endpoints
operator_only = require_roles(["operator", "admin"])

# Add CORS middleware to allow UI to call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your UI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service health endpoints map
# You can move this to config later
SERVICE_MAP = {
    "ui": os.getenv("UI_HEALTH_URL", "http://aether-crm-ui:5173/health"),
    "ai_summarizer": os.getenv("AI_SUMMARIZER_URL", "http://aether-ai-summarizer:9108/health"),
    "notifications": os.getenv("NOTIFICATIONS_URL", "http://aether-notifications-consumer:9107/health"),
    "apexflow": os.getenv("APEXFLOW_URL", "http://aether-apexflow:9109/health"),
    "kafka": os.getenv("KAFKA_URL", "http://aether-kafka:9010/health"),
}

@app.get("/ops/health", dependencies=[Depends(operator_only)])
async def ops_health():
    """
    Aggregates health status from all AetherLink services.
    Returns overall status and individual service details.
    
    Requires: operator or admin role
    """
    results = {}
    async with httpx.AsyncClient(timeout=2.5) as client:
        for name, url in SERVICE_MAP.items():
            try:
                resp = await client.get(url)
                results[name] = {
                    "status": "up" if resp.status_code == 200 else "degraded",
                    "http_status": resp.status_code,
                    "url": url,
                }
            except Exception as e:
                results[name] = {
                    "status": "down",
                    "error": str(e),
                    "url": url,
                }
    
    # Determine overall status
    overall = "up" if all(s["status"] == "up" for s in results.values()) else "degraded"
    
    return {
        "status": overall,
        "services": results,
    }

@app.get("/ops/ping")
def ping():
    """
    Simple health check for the Command Center service itself.
    """
    return {"status": "ok"}

@app.get("/audit/stats", dependencies=[Depends(operator_only)])
async def audit_stats():
    """
    Get audit statistics for security monitoring.
    
    Phase III M6: Returns request counts, auth failures, and usage patterns.
    Requires: operator or admin role
    """
    return get_audit_stats()

@app.get("/")
def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": "AetherLink Command Center",
        "version": "0.1.0",
        "endpoints": {
            "/ops/health": "Aggregated service health",
            "/ops/ping": "Command Center health check",
        }
    }
