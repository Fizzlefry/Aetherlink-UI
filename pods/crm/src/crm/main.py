import logging
import os
import time

from crm.auth_routes import router as auth_router
from crm.config import settings
from crm.routers.proposals import router as proposals_router
from crm.routes import router
from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, Histogram, generate_latest

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metrics
request_latency_seconds = Histogram(
    "crm_request_latency_seconds", "Request latency in seconds", ["route", "method"]
)

# AetherLink monitoring gauge
SERVICE_NAME = os.getenv("SERVICE_NAME", "peakpro-crm")
SERVICE_ENV = os.getenv("AETHER_ENV", "local")

aether_service_up = Gauge(
    "aether_service_up",
    "Service reachability flag for AetherLink monitoring",
    ["service", "env"]
)

print(f"[DEBUG] AetherLink gauge created: SERVICE_NAME={SERVICE_NAME}, SERVICE_ENV={SERVICE_ENV}")

app = FastAPI(
    title="PeakPro CRM", description="Minimal CRM for testing monitoring stack", version="1.0.0"
)


# Middleware for request latency tracking
@app.middleware("http")
async def track_latency(request: Request, call_next):
    """Track request latency."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Record latency
    route = request.url.path
    method = request.method
    request_latency_seconds.labels(route=route, method=method).observe(duration)

    return response


# Include routes
app.include_router(auth_router)
app.include_router(router, tags=["crm"])
app.include_router(proposals_router)

# Sprint 2: Portal routes
from crm.routes_portal import router as portal_router

app.include_router(portal_router)

# Sprint 3: Payments
from crm.routers.payments import router as payments_router

app.include_router(payments_router)

# Sprint 4: QuickBooks Online
from crm.routers.qbo import router as qbo_router

app.include_router(qbo_router)

# Sprint 5: QuickBooks Sync (Customer + Invoice Poller)
from crm.routers.qbo_sync import router as qbo_sync_router

app.include_router(qbo_sync_router)


@app.on_event("startup")
async def startup():
    """Startup event handler."""
    logger.info("Starting PeakPro CRM API")
    logger.info(f"AetherLink monitoring: SERVICE_NAME={SERVICE_NAME}, SERVICE_ENV={SERVICE_ENV}")

    # Mark service as up for AetherLink monitoring
    aether_service_up.labels(service=SERVICE_NAME, env=SERVICE_ENV).set(1)
    logger.info("AetherLink monitoring: Set aether_service_up gauge")

    # Sprint 5: Start background invoice status poller
    import asyncio

    asyncio.create_task(_invoice_status_poller())

    # Run seed data if enabled
    if settings.CRM_ENABLE_SEED:
        try:
            from crm.seed import seed_database

            seed_database()
        except Exception as e:
            logger.error(f"Failed to seed database: {e}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"ok": True, "service": "crm-api"}


async def _invoice_status_poller():
    """
    Background task: Poll QuickBooks invoice status for all open invoices.
    Runs every QBO_INVOICE_POLL_INTERVAL_MIN minutes (default 30).
    """
    import asyncio
    import os

    from crm.db import SessionLocal
    from crm.models_v2 import Lead
    from crm.qbo_sync import poll_invoice_status

    interval = int(os.getenv("QBO_INVOICE_POLL_INTERVAL_MIN", "30"))
    logger.info(f"Starting invoice status poller (interval: {interval}min)")

    while True:
        try:
            await asyncio.sleep(interval * 60)

            db = SessionLocal()
            try:
                # Get all proposals with QBO invoices that aren't marked Paid
                proposals = db.query(Lead).filter(Lead.qbo_invoice_id.isnot(None)).all()

                for proposal in proposals:
                    try:
                        poll_invoice_status(db, proposal.org_id, proposal.id)
                        await asyncio.sleep(0)  # Yield to event loop
                    except Exception as e:
                        logger.warning(f"Invoice poll error for proposal {proposal.id}: {e}")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Invoice poller error: {e}")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "PeakPro CRM",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "leads": "/leads",
            "projects": "/projects",
            "contacts": "/contacts",
        },
    }
