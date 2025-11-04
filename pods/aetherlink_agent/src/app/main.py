import asyncio
import logging
from contextlib import asynccontextmanager

from app.actions.ops import restart_api, scale_up
from app.clients.prom import prom_client
from app.config import settings
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metrics
agent_alerts_total = Counter(
    "aether_agent_alerts_total", "Total alerts received by agent", ["alertname", "severity"]
)

agent_health_checks_total = Counter(
    "aether_agent_health_checks_total", "Total health checks performed", ["status"]
)

# Background task state
background_task: asyncio.Task | None = None
last_health_score: float | None = None
consecutive_low_count = 0


async def health_check_loop():
    """Background task that checks health score every 60 seconds."""
    global last_health_score, consecutive_low_count

    logger.info("Starting health check background loop (60s interval)")

    while True:
        try:
            await asyncio.sleep(60)

            # Query health score
            score = await prom_client.instant("aether:health_score:15m")

            if score is None:
                logger.debug("Health score query returned no data")
                continue

            logger.info(f"Health score: {score:.2f}")

            # Check if score is low (<60)
            if score < 60:
                consecutive_low_count += 1
                agent_health_checks_total.labels(status="low").inc()

                if consecutive_low_count >= 2:
                    logger.warning(
                        f"HEALTH SCORE LOW: {score:.2f} (consecutive: {consecutive_low_count})"
                    )
            else:
                consecutive_low_count = 0
                agent_health_checks_total.labels(status="ok").inc()

            last_health_score = score

        except Exception as e:
            logger.error(f"Error in health check loop: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown tasks."""
    global background_task

    # Startup
    logger.info("Starting AetherLink Command AI Agent")
    background_task = asyncio.create_task(health_check_loop())

    yield

    # Shutdown
    logger.info("Shutting down AetherLink Command AI Agent")
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass

    await prom_client.close()


app = FastAPI(
    title="AetherLink Command AI Agent",
    description="Autonomous monitoring and ops agent for AetherLink",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================


class HealthResponse(BaseModel):
    ok: bool = True
    health_score: float | None = None
    consecutive_low: int = 0


class QueryRequest(BaseModel):
    ql: str = Field(..., description="PromQL query string")


class QueryResponse(BaseModel):
    value: float | None
    query: str


class ActionRequest(BaseModel):
    action: str = Field(..., description="Action to perform: restart_api, scale_up")
    reason: str | None = Field(None, description="Reason for action")
    service: str | None = Field(None, description="Service name (for scale_up)")
    replicas: int | None = Field(None, description="Target replicas (for scale_up)")


class ActionResponse(BaseModel):
    accepted: bool = True
    action: str
    details: dict


class Alert(BaseModel):
    labels: dict[str, str]
    annotations: dict[str, str]
    startsAt: str
    endsAt: str | None = None
    status: str


class AlertmanagerWebhook(BaseModel):
    alerts: list[Alert]
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        ok=True, health_score=last_health_score, consecutive_low=consecutive_low_count
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/query", response_model=QueryResponse)
async def query_prometheus(request: QueryRequest):
    """
    Proxy PromQL instant query to Prometheus.

    Args:
        request: Query request with PromQL string

    Returns:
        Query result with scalar value
    """
    try:
        value = await prom_client.instant(request.ql)
        return QueryResponse(value=value, query=request.ql)
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/act", response_model=ActionResponse, status_code=202)
async def perform_action(request: ActionRequest):
    """
    Perform operational action (restart, scale, etc.).

    Args:
        request: Action request with action type and parameters

    Returns:
        Action acceptance response
    """
    logger.info(f"Action requested: {request.action}")

    if request.action == "restart_api":
        reason = request.reason or "manual trigger"
        result = restart_api(reason)

    elif request.action == "scale_up":
        if not request.service or not request.replicas:
            raise HTTPException(
                status_code=400, detail="scale_up requires 'service' and 'replicas' parameters"
            )
        result = scale_up(request.service, request.replicas)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    return ActionResponse(accepted=True, action=request.action, details=result)


@app.post("/alertmanager")
async def alertmanager_webhook(webhook: AlertmanagerWebhook):
    """
    Receive Alertmanager webhook notifications.

    Args:
        webhook: Alertmanager webhook payload

    Returns:
        Success response
    """
    logger.info(f"Received {len(webhook.alerts)} alert(s) from Alertmanager")

    for alert in webhook.alerts:
        alertname = alert.labels.get("alertname", "unknown")
        severity = alert.labels.get("severity", "unknown")
        tenant = alert.labels.get("tenant", "N/A")
        summary = alert.annotations.get("summary", "No summary")

        # Log compact summary
        logger.info(
            f"ALERT: {alertname} | severity={severity} | tenant={tenant} | "
            f"summary='{summary}' | startsAt={alert.startsAt}"
        )

        # Increment counter
        agent_alerts_total.labels(alertname=alertname, severity=severity).inc()

        # Special handling for HealthScoreDegradation
        if alertname == "HealthScoreDegradation":
            logger.warning(f"Health Score Degradation Alert: tenant={tenant}, severity={severity}")

    return {"status": "ok", "alerts_processed": len(webhook.alerts)}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "AetherLink Command AI Agent",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "query": "POST /query",
            "act": "POST /act",
            "alertmanager": "POST /alertmanager",
        },
    }
