import contextlib
import json
import math
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import rq
import rq.job
from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, Summary
from pydantic import ValidationError
from redis import Redis
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from typing_extensions import TypedDict

from ..knowledge.rag import RAG
from . import observability
from .auth import (
    AdminOnly,
    ApiKeyRequired,
    EditorOrAdmin,
    require_admin_key,
    require_api_key_dynamic,
    require_role,
)
from .config import get_settings, reload_settings
from .crud import create_lead as create_lead_crud
from .deps import get_db
from .embeddings import build_embedder
from .enrich import enrich_text
from .envelope import err, ok
from .health import get_health
from .lead_store import create_lead as store_create_lead
from .lead_store import list_leads as store_list_leads
from .limiter import chat_limit_dep, faq_limit_dep, init_rate_limiter, ops_limit_dep
from .logger import log_chat, log_faq, logger
from .logging_setup import setup_json_logging
from .memory import append_history_safe, get_history
from .metrics import INTENT_COUNT
from .metrics import router as metrics_router
from .middleware_pii import redact_json
from .middleware_request_id import RequestIdMiddleware
from .model_client import ToolSpec, build_model_client
from .models import Base, ChatRequest, ChatResponse, FaqAnswer, FaqRequest
from .schemas import (
    AnalyticsResponse,
    LeadItem,
    LeadListResponse,
    LeadRequest,
    LeadResponse,
    OutcomeRequest,
    OutcomeResponse,
)
from .semcache import get_semcache, set_semcache
from .session import engine
from .tools import TOOL_FUNCS, TOOLS
from .vector_store import SQLiteVectorStore

settings = get_settings()
# Configure JSON logging early (non-fatal on failure)
try:
    setup_json_logging(getattr(settings, "LOG_LEVEL", "INFO"))
except Exception:
    pass

# In-memory rate limiter for /search endpoint
# Maps IP address -> deque of request timestamps
_search_rate_limiter: dict[str, deque] = {}
SEARCH_RATE_LIMIT = 60  # requests per minute per IP
SEARCH_WINDOW_SECONDS = 60

# Hot query cache (per tenant, configurable TTL)
# Maps (namespace, cache_key) -> (expiry_time, response)
_CACHE_STORE: dict[tuple[str, tuple], tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SEC = int(os.getenv("ANSWER_CACHE_TTL", "60"))

# Cache metrics (with tenant labels for per-tenant observability)
AETHER_CACHE_HITS = Counter("aether_rag_cache_hits_total", "RAG cache hits", ["endpoint", "tenant"])
AETHER_CACHE_MISSES = Counter(
    "aether_rag_cache_misses_total", "RAG cache misses", ["endpoint", "tenant"]
)

# Hybrid search weighting (0.0 = all lexical, 1.0 = all semantic)
HYBRID_ALPHA = float(os.getenv("HYBRID_ALPHA", "0.6"))


def _cache_get(ns: str, key: tuple, tenant: str = "default") -> dict[str, Any] | None:
    """Get cached response with metrics tracking"""
    now = time.time()
    cache_key = (ns, key)
    entry = _CACHE_STORE.get(cache_key)

    if not entry:
        AETHER_CACHE_MISSES.labels(endpoint=ns, tenant=tenant).inc()
        return None

    expires_at, payload = entry
    if now > expires_at:
        _CACHE_STORE.pop(cache_key, None)
        AETHER_CACHE_MISSES.labels(endpoint=ns, tenant=tenant).inc()
        return None

    AETHER_CACHE_HITS.labels(endpoint=ns, tenant=tenant).inc()
    return payload


def _cache_put(ns: str, key: tuple, payload: dict[str, Any], tenant: str = "default"):
    """Store response in cache with TTL"""
    cache_key = (ns, key)
    _CACHE_STORE[cache_key] = (time.time() + CACHE_TTL_SEC, payload)


def rate_limit_search(request: Request):
    """Rate limit /search endpoint to prevent abuse of embedding operations"""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Initialize deque for this IP if needed
    if client_ip not in _search_rate_limiter:
        _search_rate_limiter[client_ip] = deque()

    # Remove timestamps outside the sliding window
    timestamps = _search_rate_limiter[client_ip]
    while timestamps and timestamps[0] < now - SEARCH_WINDOW_SECONDS:
        timestamps.popleft()

    # Check if limit exceeded
    if len(timestamps) >= SEARCH_RATE_LIMIT:
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {SEARCH_RATE_LIMIT} requests per minute",
        )

    # Record this request
    timestamps.append(now)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.AUTH_KEYS = dict(settings.API_KEYS)
    app.state.ADMIN_KEY = getattr(settings, "API_ADMIN_KEY", None)  # Store for RBAC
    await init_rate_limiter(settings.REDIS_URL)
    # Initialize tenants count metric
    tenant_count = len(set(settings.API_KEYS.values()))
    TENANTS_COUNT.set(tenant_count)
    # Model client (agent brain)
    app.state.model_client = build_model_client()
    app.state.model_last = {"ok": False, "info": {}, "ts": 0.0}
    # RAG components
    app.state.VSTORE = SQLiteVectorStore(str(Path(__file__).parent / "rag.sqlite3"))
    app.state.EMBEDDER = build_embedder(settings.EMBED_PROVIDER, settings.EMBED_MODEL, settings)
    app.state.RAG_ENABLED = settings.RAG_ENABLED
    app.state.RAG_TOP_K = settings.RAG_TOP_K
    app.state.RAG_MIN_SCORE = settings.RAG_MIN_SCORE
    yield


app = FastAPI(title="AetherLink CustomerOps API", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)

# Metrics are handled by observability.PrometheusMiddleware (see observability.py)


# Access log middleware for observability
@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """Log all requests with method, path, status, latency, and client IP"""
    t0 = time.time()
    response = await call_next(request)
    latency_ms = int((time.time() - t0) * 1000)
    client_ip = request.client.host if request.client else "unknown"

    logger.info(
        "access",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "latency_ms": latency_ms,
            "client_ip": client_ip,
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
    return response


# PII redaction middleware
@app.middleware("http")
async def pii_redaction_middleware(request: Request, call_next):
    # Attach a flag/redactor for downstream use
    request.state.redact = redact_json
    response = await call_next(request)
    return response


# Error helpers
def _req_id(request: Request) -> str:
    return getattr(getattr(request, "state", object()), "request_id", "")


def error_response(request: Request, err_type: str, message: str, status: int) -> JSONResponse:
    try:
        endpoint = request.url.path
    except Exception:
        endpoint = "unknown"
    ERRORS_TOTAL.labels(err_type, endpoint).inc()
    return JSONResponse(
        status_code=status,
        content={"error": {"type": err_type, "message": message, "trace_id": _req_id(request)}},
    )


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return error_response(request, "http_error", exc.detail or "HTTP error", exc.status_code)


@app.exception_handler(ValidationError)
async def validation_exc_handler(request: Request, exc: ValidationError):
    return error_response(request, "validation_error", str(exc.errors()), 422)


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    return error_response(request, "internal_error", "Internal server error", 500)


# Legacy auth (kept for backward compatibility with existing code)
_ApiKeyRequired_legacy = require_api_key_dynamic(enabled=settings.REQUIRE_API_KEY)
AdminGuard = require_admin_key(getattr(settings, "API_ADMIN_KEY", None))

# RBAC dependencies - now imported from auth.py with API key support
# AdminOnly, EditorOrAdmin, ApiKeyRequired are imported from .auth
AnyRole = require_role("admin", "editor", "viewer")


# Admin-only dependency for control plane (legacy, kept for backward compat)
def AdminRequired(x_admin_key: str | None = Header(None)) -> None:
    """Require admin key for sensitive operations (dashboard, evals)."""
    expected = getattr(settings, "API_ADMIN_KEY", None)
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="admin_required")


# RQ (Redis Queue) helpers for background jobs
def _rq() -> rq.Queue:
    """Get RQ queue for background ingestion jobs."""
    conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    return rq.Queue("ingest", connection=conn, default_timeout=600)


def _rq_job(job_id: str) -> rq.job.Job | None:
    """Fetch job by ID from Redis."""
    try:
        conn = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        return rq.job.Job.fetch(job_id, connection=conn)
    except Exception:
        return None


class HealthResp(TypedDict):
    ok: bool


@app.get("/health")
async def health():
    """Enhanced health check with uptime and service status"""
    return await get_health()


@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check (simple OK response)"""
    return {"ok": True}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    from fastapi.responses import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- RAG helpers ---
def _simple_chunk(text: str, max_len: int = 800) -> list[str]:
    """Simple line/paragraph chunker"""
    parts: list[str] = []
    buf: list[str] = []
    ln = 0
    for line in text.splitlines():
        if ln + len(line) + 1 > max_len and buf:
            parts.append(" ".join(buf).strip())
            buf, ln = [], 0
        buf.append(line)
        ln += len(line) + 1
    if buf:
        parts.append(" ".join(buf).strip())
    return [p for p in parts if p]


# --- Tool helpers ---
def _tool_specs() -> list[ToolSpec]:
    """Convert registry to ToolSpec list"""
    return [
        ToolSpec(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in TOOLS
    ]


async def _execute_tool_call(tool_call: dict) -> dict:
    """
    Execute a single tool call.
    tool_call: {"name": str, "arguments": (dict|str) ...}
    """
    name = tool_call.get("name")
    if not name or name not in TOOL_FUNCS:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    raw_args = tool_call.get("arguments") or tool_call.get("args_json") or {}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid tool arguments JSON"}
    return await TOOL_FUNCS[name](raw_args)


@app.post(
    "/ops/reload-auth",
    dependencies=[Depends(AdminGuard), Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
async def reload_auth():
    s = reload_settings()
    app.state.AUTH_KEYS.clear()
    app.state.AUTH_KEYS.update(s.API_KEYS)
    # Update tenants count metric
    tenant_count = len(set(app.state.AUTH_KEYS.values()))
    TENANTS_COUNT.set(tenant_count)
    return {"ok": True, "keys": len(app.state.AUTH_KEYS), "tenants": tenant_count}


@app.get(
    "/ops/tenants",
    dependencies=[Depends(ApiKeyRequired), Depends(AdminGuard), Depends(ops_limit_dep())],
    tags=["ops"],
)
async def list_tenants(request: Request):
    # Only expose tenant names; never keys
    tenants = sorted(set(request.app.state.AUTH_KEYS.values()))
    return {"tenants": tenants, "count": len(tenants)}


# Mount routers (admin-only for security - RBAC protected)
from .evals import router as evals_router
from .ui import router as ui_router

app.include_router(ui_router, tags=["ui"], dependencies=[Depends(AdminOnly)])
app.include_router(evals_router, tags=["evals"], dependencies=[Depends(AdminOnly)])

# Constants
CONFIDENCE_THRESHOLD = 0.75
BOOKING_WORDS = [
    "book",
    "schedule",
    "appointment",
    "consult",
    "meeting",
    "consultation",
    "demo",
    "available",
    "time",
    "slot",
]

Base.metadata.create_all(bind=engine)
rag = RAG()
rag.ensure_schema()

# Ops metrics
TENANTS_COUNT = Gauge(
    "api_tenants_count",
    "Number of active tenants (unique API keys)",
)

# RAG metrics (with tenant labels for multi-tenant observability)
RAG_RETRIEVAL_LATENCY = Summary("rag_retrieval_latency_ms", "Latency of RAG retrieval in ms")
RAG_HITS = Counter("rag_hits_total", "Number of retrieved context chunks", ["tenant"])
ANSWERS_TOTAL = Counter(
    "aether_rag_answers_total", "RAG answers generated", ["mode", "rerank", "tenant"]
)
LOWCONF_TOTAL = Counter("aether_rag_lowconfidence_total", "Low confidence answers", ["tenant"])

# Error metrics
ERRORS_TOTAL = Counter("errors_total", "Count of API errors", ["type", "endpoint"])
REDACTIONS_TOTAL = Counter("pii_redactions_total", "Count of PII redaction events")

LEAD_ENRICH_TOTAL = Counter(
    "lead_enrich_total",
    "Count of lead enrich operations",
    ["intent", "urgency", "sentiment"],
)
LEAD_SCORE_HIST = Histogram(
    "lead_enrich_score",
    "Distribution of lead enrichment scores",
    buckets=[0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0],
)
OUTCOME_TOTAL = Counter(
    "lead_outcome_total",
    "Count of lead outcomes recorded",
    ["outcome"],
)
CONVERSION_RATE = Gauge(
    "lead_conversion_rate",
    "Current conversion rate (booked / total outcomes)",
)
PRED_PROB_HIST = Histogram(
    "lead_pred_prob",
    "Distribution of predicted conversion probabilities",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
PRED_LATENCY = Summary(
    "lead_pred_latency_seconds",
    "Latency of prediction inference",
)


def _parse_schedules(csv: str) -> list[int]:
    """Parse FOLLOWUP_SCHEDULES like '30m,2h,1d' into seconds list."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    out: list[int] = []
    for part in (csv or "").split(","):
        p = part.strip().lower()
        if not p:
            continue
        try:
            if p[-1] in units:
                out.append(int(float(p[:-1]) * units[p[-1]]))
            else:
                # assume seconds
                out.append(int(p))
        except Exception:
            continue
    return out


@app.exception_handler(HTTP_429_TOO_MANY_REQUESTS)
async def _ratelimit_handler(request: Request, exc: Any):
    from fastapi.responses import JSONResponse

    req_id = getattr(request.state, "request_id", "n/a")
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content=err(req_id, "Too many requests — please slow down.", code="rate_limited"),
    )


SENSITIVE_HEADERS = {"x-api-key", "x-admin-key", "authorization"}


class ScrubAuthHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        for h in SENSITIVE_HEADERS:
            if h in response.headers:
                del response.headers[h]
        return response


app.add_middleware(ScrubAuthHeadersMiddleware)


# Security headers (safe defaults for APIs)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none';",
        )
        return resp


app.add_middleware(SecurityHeadersMiddleware)

s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in s.cors_origins.split(",") if x.strip()]
    if (s.cors_origins or "").strip() != "*"
    else ["*"],
    allow_credentials=s.CORS_ALLOW_CREDENTIALS,
    allow_methods=[x.strip() for x in s.CORS_METHODS.split(",") if x.strip()],
    allow_headers=[x.strip() for x in s.CORS_HEADERS.split(",") if x.strip()],
)

allowed_hosts = ["localhost", "127.0.0.1", "*.aetherlink.dev"]
if hasattr(s, "ALLOWED_HOSTS") and s.ALLOWED_HOSTS:
    allowed_hosts = [x.strip() for x in s.ALLOWED_HOSTS.split(",") if x.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def tenant_in_state(request: Request, call_next: RequestResponseEndpoint):
    s = getattr(request.app.state, "_settings", None) or get_settings()
    if s.REQUIRE_API_KEY:
        x_key = request.headers.get("x-api-key")
        # x_key can be None; .get() handles it gracefully
        request.state.tenant = s.API_KEYS.get(x_key or "", "public")
    else:
        request.state.tenant = "public"
    return await call_next(request)


observability.init(app)
app.include_router(metrics_router, tags=["ops"])


@app.get("/ops/reload", tags=["ops"], dependencies=[Depends(ops_limit_dep())])
async def reload() -> dict[str, object]:
    new = reload_settings()
    request_app = app
    request_app.state._settings = new
    logger.info("settings_reloaded", extra={"env": new.ENV, "log_level": new.LOG_LEVEL})
    return {"ok": True, "env": new.ENV, "log_level": new.LOG_LEVEL}


@app.get("/ops/config", tags=["ops"], dependencies=[Depends(ops_limit_dep())])
async def ops_config() -> dict[str, object]:
    s = get_settings()
    return {
        "env": s.ENV,
        "app": s.APP_NAME,
        "debug": s.DEBUG,
        "log_level": s.LOG_LEVEL,
        "cors_origins": s.cors_origins_list,
        "rate_fallback": s.RATE_LIMIT_FALLBACK,
        "faq_limit": s.RATE_LIMIT_FAQ,
        "chat_limit": s.RATE_LIMIT_CHAT,
        "require_api_key": s.REQUIRE_API_KEY,
        "enable_memory": s.ENABLE_MEMORY,
        "enable_enrichment": s.ENABLE_ENRICHMENT,
    }


@app.post("/ops/reload", tags=["ops"], dependencies=[Depends(ops_limit_dep())])
def ops_reload():
    try:
        s = reload_settings()
        return {"ok": True, "env": s.ENV, "log_level": s.LOG_LEVEL}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"reload_failed: {e}")


@app.get(
    "/ops/export/outcomes.csv",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
def export_outcomes_csv(tenant: str = Depends(ApiKeyRequired), limit: int = 1000):
    import csv
    from datetime import datetime
    from io import StringIO

    from fastapi.responses import StreamingResponse

    from .lead_store import list_outcomes

    outcomes = list_outcomes(limit=limit)
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "lead_id",
            "tenant_hash",
            "intent",
            "sentiment",
            "urgency",
            "score",
            "details_len",
            "hour_of_day",
            "outcome",
            "label",
        ],
    )
    writer.writeheader()
    for outcome_rec in outcomes:
        lead_id = outcome_rec.get("lead_id")
        outcome = outcome_rec.get("outcome", "unknown")
        from .lead_store import get_lead

        lead = get_lead(lead_id)
        if not lead:
            continue
        details = lead.get("details", "")
        created_at = lead.get("created_at", 0)
        hour = datetime.fromtimestamp(created_at).hour if created_at else 12
        tenant_id = lead.get("tenant", "public")
        tenant_hash = str(hash(tenant_id) % 10000)
        intent = lead.get("intent", "unknown")
        sentiment = lead.get("sentiment", "neutral")
        urgency = lead.get("urgency", "medium")
        score = lead.get("score", 0.5)
        writer.writerow(
            {
                "lead_id": lead_id,
                "tenant_hash": tenant_hash,
                "intent": intent,
                "sentiment": sentiment,
                "urgency": urgency,
                "score": float(score),
                "details_len": len(details),
                "hour_of_day": hour,
                "outcome": outcome,
                "label": 1 if outcome == "booked" else 0,
            }
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=outcomes.csv"},
    )


@app.post(
    "/ops/followup-hook",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
async def followup_hook(request: Request, tenant: str = Depends(ApiKeyRequired)):
    request_id = getattr(request.state, "request_id", "n/a")
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    lead_id = payload.get("lead_id")
    strategy = payload.get("strategy", "unknown")
    message = payload.get("message", "")
    logger.info(
        "followup_hook_received",
        extra={
            "request_id": request_id,
            "lead_id": lead_id,
            "strategy": strategy,
            "message": message,
        },
    )
    return {"ok": True, "message": "Follow-up hook received"}


@app.get(
    "/ops/followup/queue",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
def followup_queue_status(tenant: str = Depends(ApiKeyRequired)):
    if not app.state.q_followups:
        return {"enabled": False, "queue": None, "jobs": 0}
    try:
        from rq.registry import ScheduledJobRegistry

        q = app.state.q_followups
        scheduled_registry = ScheduledJobRegistry(queue=q)
        return {
            "enabled": True,
            "queue": s.FOLLOWUP_QUEUE,
            "jobs": {
                "queued": len(q),
                "scheduled": len(scheduled_registry),
            },
        }
    except Exception as e:
        logger.warning("queue_status_error", extra={"error": str(e)})
        return {"enabled": True, "queue": s.FOLLOWUP_QUEUE, "error": str(e)}


@app.post(
    "/ops/reload-model",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
def reload_model_endpoint(
    min_auc: float = 0.65,
    tenant: str = Depends(ApiKeyRequired),
):
    try:
        from .predict import reload_model

        result = reload_model(min_auc=min_auc)
        if result.get("ok"):
            logger.info(
                "model_reloaded",
                extra={
                    "version": result.get("version"),
                    "auc": result.get("auc"),
                    "n_train": result.get("n_train"),
                    "min_auc": min_auc,
                },
            )
        else:
            logger.warning(
                "model_reload_rejected",
                extra={
                    "reason": result.get("error"),
                    "auc": result.get("auc"),
                    "min_auc": min_auc,
                },
            )
        return result
    except Exception as e:
        logger.error("model_reload_failed", extra={"error": str(e)})
        return {"ok": False, "error": str(e)}


@app.get(
    "/ops/model-status",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
async def model_status_endpoint(request: Request, tenant: str = Depends(ApiKeyRequired)) -> Any:
    mc = request.app.state.model_client
    t0 = time.time()
    ok_flag, info = await mc.ahealth()
    latency = time.time() - t0
    request.app.state.model_last = {"ok": ok_flag, "info": info, "ts": t0}
    out: Any = {
        "loaded": True,
        "provider": settings.MODEL_PROVIDER,
        "model": settings.MODEL_NAME,
        "health": "ok" if ok_flag else "error",
        "latency_ms": round(latency * 1000, 1),
    }
    out.update(info)
    return out


class AgentChatRequest(TypedDict, total=False):
    message: str  # required
    system: str
    context: Any


@app.post(
    "/chat", tags=["agent"], dependencies=[Depends(ApiKeyRequired), Depends(chat_limit_dep())]
)
async def chat_endpoint(
    request: Request,
    body: AgentChatRequest = Body(...),
    tenant: str = Depends(ApiKeyRequired),
) -> Any:
    req_id = getattr(request.state, "request_id", "n/a")

    # PII redaction
    body_redacted = request.state.redact(body)
    if body_redacted != body:
        REDACTIONS_TOTAL.inc()

    msg = body_redacted.get("message")
    if not msg:
        return JSONResponse(
            status_code=400,
            content=err(req_id, "Missing required field: message", code="missing_message"),
        )
    sys_prompt = body_redacted.get("system") or settings.AGENT_PERSONALITY
    ctx_raw = body_redacted.get("context")
    ctx: Any = ctx_raw if isinstance(ctx_raw, dict) else {}
    tools = _tool_specs()
    mc = request.app.state.model_client

    # RAG retrieval hook
    context_blocks: list[str] = []
    if app.state.RAG_ENABLED:
        try:
            start = time.perf_counter()
            q_vec = app.state.EMBEDDER.embed([msg])[0]
            hits = app.state.VSTORE.search(
                tenant,
                q_vec,
                top_k=app.state.RAG_TOP_K,
                min_score=app.state.RAG_MIN_SCORE,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            RAG_RETRIEVAL_LATENCY.observe(elapsed_ms)
            if hits:
                RAG_HITS.labels(tenant=tenant).inc(len(hits))
                for score, chunk, src in hits:
                    context_blocks.append(f"[score={score:.3f} source={src or 'N/A'}]\n{chunk}")
        except Exception:
            # don't block chat if retrieval fails
            pass

    # Prepend context for the model
    if context_blocks:
        msg = (
            "Use the following context if relevant:\n\n"
            + "\n\n---\n\n".join(context_blocks)
            + f"\n\n---\n\nUser: {msg}"
        )

    t0 = time.time()
    result = await mc.chat(prompt=msg, system=sys_prompt, context=ctx, tools=tools)
    latency = time.time() - t0

    # Tool requested?
    tc = result.get("tool_call")
    if tc:
        tool_res = await _execute_tool_call(tc)
        logger.info(
            "agent_tool_call",
            extra={
                "request_id": req_id,
                "tenant": tenant,
                "tool_name": tc.get("name"),
                "latency_ms": round(latency * 1000, 1),
            },
        )
        return {
            "request_id": req_id,
            "tool_result": tool_res,
            "latency_ms": round(latency * 1000, 1),
            "provider": settings.MODEL_PROVIDER,
            "model": settings.MODEL_NAME,
        }

    # Text response
    reply_text = result.get("text", "")
    logger.info(
        "agent_chat",
        extra={
            "request_id": req_id,
            "tenant": tenant,
            "latency_ms": round(latency * 1000, 1),
            "msg_len": len(msg),
            "reply_len": len(reply_text),
        },
    )
    return {
        "request_id": req_id,
        "reply": reply_text,
        "latency_ms": round(latency * 1000, 1),
        "provider": settings.MODEL_PROVIDER,
        "model": settings.MODEL_NAME,
    }


@app.post(
    "/chat/stream",
    tags=["agent"],
    dependencies=[Depends(ApiKeyRequired), Depends(chat_limit_dep())],
)
async def chat_stream_endpoint(
    request: Request,
    body: AgentChatRequest = Body(...),
    tenant: str = Depends(ApiKeyRequired),
):
    req_id = getattr(request.state, "request_id", "n/a")

    # PII redaction
    body_redacted = request.state.redact(body)
    if body_redacted != body:
        REDACTIONS_TOTAL.inc()

    msg = body_redacted.get("message")
    if not msg:
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("message is required", status_code=400)

    sys_prompt = body_redacted.get("system") or settings.AGENT_PERSONALITY
    ctx_raw = body_redacted.get("context")
    ctx: Any = ctx_raw if isinstance(ctx_raw, dict) else {}
    tools = _tool_specs()
    mc = request.app.state.model_client

    # RAG retrieval hook (same as /chat)
    context_blocks: list[str] = []
    if app.state.RAG_ENABLED:
        try:
            start = time.perf_counter()
            q_vec = app.state.EMBEDDER.embed([msg])[0]
            hits = app.state.VSTORE.search(
                tenant,
                q_vec,
                top_k=app.state.RAG_TOP_K,
                min_score=app.state.RAG_MIN_SCORE,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            RAG_RETRIEVAL_LATENCY.observe(elapsed_ms)
            if hits:
                RAG_HITS.labels(tenant=tenant).inc(len(hits))
                for score, chunk, src in hits:
                    context_blocks.append(f"[score={score:.3f} source={src or 'N/A'}]\n{chunk}")
        except Exception:
            pass

    if context_blocks:
        msg = (
            "Use the following context if relevant:\n\n"
            + "\n\n---\n\n".join(context_blocks)
            + f"\n\n---\n\nUser: {msg}"
        )

    async def event_gen():
        try:
            async for chunk in mc.stream(prompt=msg, system=sys_prompt, context=ctx, tools=tools):
                # Stream text deltas
                if chunk.get("type") == "text" and "delta" in chunk:
                    yield {"event": "text", "data": chunk["delta"]}
                # Tool call surfaced mid-stream → execute and emit result
                elif chunk.get("type") == "tool_call":
                    tool_res = await _execute_tool_call(chunk)
                    yield {"event": "tool_result", "data": json.dumps(tool_res)}
            # Graceful end
            yield {"event": "done", "data": "ok"}
        except HTTPException as e:
            # surface structured SSE error
            err = {"type": "http_error", "message": e.detail, "trace_id": req_id}
            yield {"event": "error", "data": json.dumps(err)}
        except Exception:
            err = {"type": "internal_error", "message": "Internal server error", "trace_id": req_id}
            yield {"event": "error", "data": json.dumps(err)}

    return EventSourceResponse(event_gen(), ping=15000)


@app.post(
    "/knowledge/ingest",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def knowledge_ingest(payload: dict, request: Request, tenant: str = Depends(ApiKeyRequired)):
    """
    Ingest text chunks into RAG knowledge base.
    Body: { "text": "...", "source": "optional-id-or-url" }
    """
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    source = payload.get("source")

    # Get tenant from dependency or fallback
    tenant_name = tenant or getattr(request.state, "tenant", None) or "unknown"

    chunks = _simple_chunk(text)
    embedder = app.state.EMBEDDER
    vectors = embedder.embed(chunks)
    app.state.VSTORE.upsert(tenant_name, source, chunks, vectors)
    return {"ok": True, "ingested_chunks": len(chunks), "source": source, "tenant": tenant_name}


@app.get(
    "/knowledge/list", tags=["knowledge"], dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)]
)
async def knowledge_list(
    tenant: str = Depends(ApiKeyRequired), limit: int = 50, q: str | None = None
):
    """List knowledge entries for tenant with optional text search."""
    vs = app.state.VSTORE  # type: ignore[attr-defined]
    items = vs.list(tenant=tenant, limit=limit, q=q)
    return {"ok": True, "count": len(items), "items": items}


@app.delete(
    "/knowledge/delete",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def knowledge_delete(ids: list[str] = Query(...), tenant: str = Depends(ApiKeyRequired)):
    """Delete knowledge entries by IDs for tenant."""
    vs = app.state.VSTORE  # type: ignore[attr-defined]
    deleted = vs.delete(tenant=tenant, ids=ids)
    return {"ok": True, "deleted": deleted}


@app.get(
    "/knowledge/export",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)],
)
async def knowledge_export(tenant: str = Depends(ApiKeyRequired)):
    """Export knowledge entries as CSV."""
    from fastapi.responses import PlainTextResponse

    vs = app.state.VSTORE  # type: ignore[attr-defined]
    csv = vs.export_csv(tenant=tenant)
    return PlainTextResponse(csv, media_type="text/csv")


@app.get("/search", tags=["knowledge"], dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)])
async def semantic_search(
    request: Request,
    q: str = Query(..., description="Search query text"),
    k: int = Query(5, description="Number of results to return"),
    mode: str = Query("hybrid", description="Search mode: 'semantic', 'lexical', or 'hybrid'"),
    rerank: bool = Query(False, description="Apply reranking to improve result quality"),
    rerank_topk: int = Query(10, ge=3, le=50, description="Number of candidates for reranking"),
    tenant: str | None = Depends(ApiKeyRequired),
):
    """
    Hybrid search combining semantic (vector) and lexical (keyword) retrieval.
    Rate limited to 60 requests per minute per IP.

    Args:
        q: Search query text
        k: Maximum number of results (default: 5)
        mode: Search mode - "semantic" (vector only), "lexical" (keyword only), or "hybrid" (both)
        tenant: Optional tenant filter (defaults to "default")

    Returns:
        Results with id, content, metadata, and combined score
    """
    from pods.customer_ops.db_duck import query_embeddings as duck_query
    from pods.customer_ops.db_duck import query_lexical

    # Apply rate limiting
    rate_limit_search(request)

    # Default to "default" tenant if not specified
    tenant_id = tenant or "default"

    # Check cache
    cache_key = (tenant_id, q.strip().lower(), mode, str(rerank), str(k), str(rerank_topk))
    cached = _cache_get("search", cache_key, tenant=tenant_id)
    if cached:
        return cached

    # Validate mode
    if mode not in ["semantic", "lexical", "hybrid"]:
        raise HTTPException(
            status_code=400, detail=f"Invalid mode: {mode}. Use 'semantic', 'lexical', or 'hybrid'"
        )

    results_dict = {}  # id -> {content, metadata, score_semantic, score_lex}

    # Semantic search (vector similarity)
    if mode in ["semantic", "hybrid"]:
        embedder = app.state.EMBEDDER
        query_vec = embedder.embed([q])[0]
        semantic_rows = duck_query(
            query_vec, tenant_id=tenant_id, top_k=k * 2
        )  # Get more for merging

        for row in semantic_rows:
            doc_id = row["id"]
            score_semantic = max(0.0, 1.0 - row["distance"])  # Convert distance to similarity

            if doc_id not in results_dict:
                results_dict[doc_id] = {
                    "id": doc_id,
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "score_semantic": 0.0,
                    "score_lex": 0.0,
                }
            results_dict[doc_id]["score_semantic"] = score_semantic

    # Lexical search (keyword matching)
    if mode in ["lexical", "hybrid"]:
        lexical_rows = query_lexical(q, tenant_id=tenant_id, top_k=k * 2)

        # Normalize lexical scores to 0-1 range
        max_lex = max([r["score_lex"] for r in lexical_rows], default=1)

        for row in lexical_rows:
            doc_id = row["id"]
            score_lex_normalized = row["score_lex"] / max_lex if max_lex > 0 else 0.0

            if doc_id not in results_dict:
                results_dict[doc_id] = {
                    "id": doc_id,
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "score_semantic": 0.0,
                    "score_lex": 0.0,
                }
            results_dict[doc_id]["score_lex"] = score_lex_normalized

    # Combine scores and rank
    results = []
    for doc in results_dict.values():
        if mode == "semantic":
            final_score = doc["score_semantic"]
        elif mode == "lexical":
            final_score = doc["score_lex"]
        else:  # hybrid
            # Weighted blend: HYBRID_ALPHA controls semantic vs lexical balance
            final_score = (
                HYBRID_ALPHA * doc["score_semantic"] + (1 - HYBRID_ALPHA) * doc["score_lex"]
            )

        results.append(
            {
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": round(final_score, 4),
                "score_semantic": round(doc["score_semantic"], 4),
                "score_lex": round(doc["score_lex"], 4),
            }
        )

    # Sort by final score
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[: k if not rerank else rerank_topk]

    # Apply reranking if requested
    rerank_used = "none"
    if rerank and results:
        try:
            results = _rerank_embed(q, results, topk=rerank_topk)
            rerank_used = "embed"
        except Exception:
            results = _rerank_token(q, results, topk=rerank_topk)
            rerank_used = "token"
        results = results[:k]

    response = {
        "ok": True,
        "mode": mode,
        "query": q,
        "results": results,
        "count": len(results),
        "reranked": rerank,
        "rerank_used": rerank_used,
    }

    # Cache response
    _cache_put("search", cache_key, response, tenant=tenant_id)

    return response


# --- RERANK SUPPORT -----------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors"""
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b, strict=False))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0.0 or db == 0.0:
        return 0.0
    return num / (da * db)


def _rerank_embed(
    query: str, candidates: list[dict[str, Any]], topk: int = 10
) -> list[dict[str, Any]]:
    """
    Re-scores candidates by cosine(query_emb, passage_emb) using the existing embedder.
    Only touches the top 'topk' items; preserves other fields; adds 'rerank_score'.
    """
    embedder = app.state.EMBEDDER
    if not embedder:
        raise RuntimeError("embedder-unavailable")

    # Embed query
    qv = embedder.embed([query])[0]

    # Embed top-k passages
    pool = candidates[:topk]
    passages = [c.get("content", "") for c in pool]
    pv_list = embedder.embed(passages)

    # Compute cosine scores
    for c, pv in zip(pool, pv_list, strict=False):
        c["rerank_score"] = float(_cosine(qv, pv))

    # Re-sort by rerank score
    pool.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)

    return pool + candidates[topk:]


def _rerank_token(
    query: str, candidates: list[dict[str, Any]], topk: int = 10
) -> list[dict[str, Any]]:
    """
    Deterministic fallback: counts token hits; adds 'rerank_score_token'.
    """
    toks = [t for t in query.lower().split() if len(t) > 2][:8]

    def hits(txt: str) -> int:
        L = txt.lower()
        return sum(1 for t in toks if t in L)

    pool = candidates[:topk]
    for c in pool:
        c["rerank_score_token"] = hits(c.get("content", ""))

    # Re-sort by token hits
    pool.sort(key=lambda x: x.get("rerank_score_token", 0), reverse=True)

    return pool + candidates[topk:]


# --- ANSWER HELPERS -----------------------------------------------------------


def _uniq_by(results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Remove duplicate results by a metadata key (e.g., 'url' or 'source')"""
    seen, out = set(), []
    for r in results:
        k = (r.get("metadata") or {}).get(key)
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        out.append(r)
    return out


def _make_citations(
    results: list[dict[str, Any]],
    used_by_url: dict[str, list[str]] = None,
    max_cites: int = 3,
    snippet_chars: int = 220,
) -> list[dict[str, Any]]:
    """
    Format citations with URL grouping, hit counts, and merged highlights.

    Args:
        results: Search results with content and metadata
        used_by_url: Map of URL -> list of sentences used from that source
        max_cites: Max number of unique sources to include
        snippet_chars: Max chars for each snippet

    Returns:
        List of citation dicts with {url, snippet, count, highlights}
    """
    url_data: dict[str, dict[str, Any]] = {}

    for r in results:
        meta = r.get("metadata") or {}
        url = (meta.get("url") or meta.get("source") or "unknown").strip()
        content = r.get("content", "")

        if url not in url_data:
            url_data[url] = {"url": url, "content": content, "count": 0, "used_sentences": []}

        # Track used sentences for this URL
        if used_by_url and url in used_by_url:
            url_data[url]["count"] += len(used_by_url[url])
            url_data[url]["used_sentences"].extend(used_by_url[url])

    # Sort by count (most cited first), take top max_cites
    ranked = sorted(url_data.values(), key=lambda x: x["count"], reverse=True)[:max_cites]

    out = []
    for item in ranked:
        used_sents = item["used_sentences"]
        content = item["content"]

        # Create smart snippet centered around first used sentence
        if used_sents:
            snippet = _centered_snippet(content, used_sents[0], snippet_chars)
        else:
            snippet = content[:snippet_chars].replace("\n", " ").strip()

        citation: dict[str, Any] = {"url": item["url"], "snippet": snippet, "count": item["count"]}

        # Extract highlights for the snippet
        if used_sents:
            highlights = _extract_highlights(snippet, used_sents)
            if highlights:
                citation["highlights"] = highlights

        out.append(citation)

    return out


def _confidence(query: str, topk: list[dict[str, Any]], used: list[str]) -> float:
    """
    Calculate confidence score based on token coverage and retrieval strength.
    Returns value between 0.0 and 1.0.
    """
    toks = [t for t in query.lower().split() if len(t) > 2]
    if not toks or not topk:
        return 0.0

    # Token coverage from answer sentences
    hit = sum(1 for t in toks for s in used if t in s.lower())
    cov = hit / (len(toks) * max(1, len(used)))

    # Retrieval strength (use final fused score field)
    ret = sum(float(r.get("score", 0.0)) for r in topk[:3]) / max(1, min(3, len(topk)))

    # Blend (60% coverage, 40% retrieval strength)
    return 0.6 * cov + 0.4 * min(1.0, ret)


def _pii_guard(answer: str) -> tuple[bool, str]:
    """
    Check if answer contains PII placeholders and refuse to surface them.
    Returns (ok, safe_answer) tuple.
    """
    pii_tags = ["[SSN]", "[CARD]", "[EMAIL]", "[PHONE]"]
    if any(tag in answer for tag in pii_tags):
        return (
            False,
            "This answer contains sensitive PII. Please open the cited source with proper permissions.",
        )
    return True, answer


def _extract_highlights(snippet: str, used_sentences: list[str]) -> list[dict[str, int]]:
    """
    Find character offsets for sentences used in the answer.
    Returns list of {start, end} dicts for UI highlighting (capped at 6).
    """
    highlights = []
    for sent in used_sentences:
        s = sent.strip()
        if not s:
            continue
        idx = snippet.find(s)
        if idx >= 0:
            highlights.append({"start": idx, "end": idx + len(s)})
    return highlights[:6]  # Cap for UI


def _centered_snippet(text: str, needle: str, max_len: int) -> str:
    """
    Extract a snippet centered around the needle (matched sentence).
    Tries to trim to sentence boundaries.
    """
    idx = text.find(needle)
    if idx < 0 or max_len <= 0:
        return text[:max_len]

    # Center window around the needle
    left = max(0, idx - max_len // 3)
    right = min(len(text), left + max_len)
    window = text[left:right]

    # Try to trim to sentence boundaries (lightweight heuristic)
    if "." in window:
        first = window.find(".")
        last = window.rfind(".")
        if 0 < first < len(window) - 1 and 0 < last <= len(window):
            window = window[first + 1 : last + 1].strip()

    return window


def _fetch_neighbor_chunks(
    conn,
    doc_key: str,
    chunk_index: int,
    around_chunk_id: str,
    window: int = 1,
    max_chars: int = 1800,
) -> str:
    """
    Fetch ±window chunks from the same document for richer context.
    Returns concatenated text of neighbors (capped at max_chars).
    """
    try:
        # Query neighbor chunks by chunk_index offset
        query = """
            SELECT chunk_index, content
            FROM embeddings
            WHERE doc_key = ?
              AND chunk_index BETWEEN ? AND ?
            ORDER BY chunk_index
        """
        rows = conn.execute(query, (doc_key, chunk_index - window, chunk_index + window)).fetchall()

        if not rows:
            return ""

        # Concatenate neighbor content
        texts = [r[1] for r in rows if r[1]]
        combined = " ".join(texts)
        return combined[:max_chars]
    except Exception as e:
        logger.warning(f"Failed to fetch neighbor chunks for {around_chunk_id}: {e}")
        return ""


def _synthetic_answer(
    query: str, chunks: list[dict[str, Any]], max_chars: int = 700
) -> tuple[str, list[str]]:
    """Extract key sentences matching query tokens (LLM-free baseline)"""
    # Extract meaningful query tokens
    q_toks = [t for t in query.lower().split() if len(t) > 2][:6]
    picks = []

    for r in chunks:
        content = r.get("content", "")
        for sent in content.split(". "):
            s = sent.strip()
            if not s:
                continue
            # Count token hits
            hits = sum(1 for t in q_toks if t in s.lower())
            if hits >= 1:
                picks.append(s)
        if len(" ".join(picks)) > max_chars:
            break

    if not picks:
        # Fallback: first chunk head
        head = (chunks[0].get("content", "") if chunks else "")[:max_chars]
        fallback = head.strip() or "I couldn't find enough information in the indexed documents."
        return fallback, [fallback]

    # Trim and tidy
    ans = " ".join(picks)[:max_chars].strip()

    # Ensure 60-120 words-ish
    words = ans.split()
    if len(words) > 130:
        ans = " ".join(words[:120]) + "..."

    return ans, picks


@app.get("/answer", tags=["knowledge"], dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)])
async def answer_endpoint(
    request: Request,
    q: str = Query(..., description="Question to answer"),
    k: int = Query(5, ge=1, le=10, description="Number of chunks to retrieve"),
    mode: str = Query("hybrid", description="Search mode: semantic, lexical, or hybrid"),
    rerank: bool = Query(False, description="Apply reranking to improve result quality"),
    rerank_topk: int = Query(10, ge=3, le=50, description="Number of candidates for reranking"),
    tenant: str | None = Depends(ApiKeyRequired),
):
    """
    Answer question using RAG with citations.
    Retrieves relevant chunks and synthesizes a grounded answer with source citations.

    Args:
        q: Question text
        k: Number of chunks to retrieve (1-10)
        mode: Search mode (semantic, lexical, hybrid)
        rerank: Apply reranking (embed strategy with token fallback)
        rerank_topk: Number of candidates to rerank
        tenant: Tenant ID from API key

    Returns:
        Answer text with citations (url/source + snippet) and confidence score
    """
    from pods.customer_ops.db_duck import query_embeddings as duck_query
    from pods.customer_ops.db_duck import query_lexical

    # Apply rate limiting (reuse search rate limiter)
    rate_limit_search(request)

    # Default tenant
    tenant_id = tenant or "default"

    # Check cache
    cache_key = (tenant_id, q.strip().lower(), mode, str(rerank), str(k), str(rerank_topk))
    cached = _cache_get("answer", cache_key, tenant=tenant_id)
    if cached:
        return cached

    # Validate mode
    if mode not in ["semantic", "lexical", "hybrid"]:
        mode = "hybrid"

    # Internal search (same logic as /search endpoint)
    results_dict = {}

    # Semantic search
    if mode in ["semantic", "hybrid"]:
        embedder = app.state.EMBEDDER
        query_vec = embedder.embed([q])[0]
        semantic_rows = duck_query(query_vec, tenant_id=tenant_id, top_k=max(k, 5) * 2)

        for row in semantic_rows:
            doc_id = row["id"]
            score_semantic = max(0.0, 1.0 - row["distance"])

            if doc_id not in results_dict:
                results_dict[doc_id] = {
                    "id": doc_id,
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "score_semantic": 0.0,
                    "score_lex": 0.0,
                }
            results_dict[doc_id]["score_semantic"] = score_semantic

    # Lexical search
    if mode in ["lexical", "hybrid"]:
        lexical_rows = query_lexical(q, tenant_id=tenant_id, top_k=max(k, 5) * 2)
        max_lex = max([r["score_lex"] for r in lexical_rows], default=1)

        for row in lexical_rows:
            doc_id = row["id"]
            score_lex_normalized = row["score_lex"] / max_lex if max_lex > 0 else 0.0

            if doc_id not in results_dict:
                results_dict[doc_id] = {
                    "id": doc_id,
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "score_semantic": 0.0,
                    "score_lex": 0.0,
                }
            results_dict[doc_id]["score_lex"] = score_lex_normalized

    # Combine and rank
    results = []
    for doc in results_dict.values():
        if mode == "semantic":
            final_score = doc["score_semantic"]
        elif mode == "lexical":
            final_score = doc["score_lex"]
        else:  # hybrid
            final_score = max(doc["score_semantic"], doc["score_lex"])

        results.append(
            {
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": final_score,
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[: max(k, 5) if not rerank else max(k, rerank_topk)]

    # Rerank if requested
    rerank_used = "none"
    if rerank and results:
        try:
            results = _rerank_embed(q, results, topk=rerank_topk)
            rerank_used = "embed"
        except Exception:
            results = _rerank_token(q, results, topk=rerank_topk)
            rerank_used = "token"
        results = results[: max(k, 5)]

    # Deduplicate by URL/source
    results = _uniq_by(results, "url")

    # No results found
    if not results:
        ANSWERS_TOTAL.labels(mode=mode, rerank=str(bool(rerank)).lower(), tenant=tenant_id).inc()
        return {
            "answer": "I couldn't find enough information in the indexed documents.",
            "citations": [],
            "used_mode": mode,
            "rerank_used": rerank_used,
            "confidence": 0.0,
        }

    # Enrich results with neighbor chunks (±1 for richer context)
    from pods.customer_ops.db_duck import get_conn as get_duck_conn

    try:
        conn = get_duck_conn()
        for r in results[:5]:  # Only enrich top 5 for performance
            meta = r.get("metadata") or {}
            doc_key = meta.get("doc_key", "")
            chunk_index = meta.get("chunk_index", 0)
            chunk_id = r.get("id", "")

            if doc_key and isinstance(chunk_index, int):
                neighbors = _fetch_neighbor_chunks(conn, doc_key, chunk_index, chunk_id, window=1)
                if neighbors:
                    # Append neighbor context to content (mark with separator)
                    r["content"] = r["content"] + "\n\n[Context] " + neighbors
    except Exception as e:
        logger.warning(f"Failed to enrich with neighbor chunks: {e}")

    # Synthesize answer
    answer_text, used_sentences = _synthetic_answer(q, results)

    # Track which URLs contributed sentences
    used_by_url: dict[str, list[str]] = {}
    for sent in used_sentences:
        for r in results:
            if sent in r.get("content", ""):
                meta = r.get("metadata") or {}
                url = (meta.get("url") or meta.get("source") or "unknown").strip()
                if url not in used_by_url:
                    used_by_url[url] = []
                used_by_url[url].append(sent)
                break  # Each sentence comes from one source

    # Generate citations with URL grouping and merged highlights
    citations = _make_citations(results, used_by_url=used_by_url, max_cites=3)

    # PII guard check
    pii_ok, safe_answer = _pii_guard(answer_text)
    if not pii_ok:
        ANSWERS_TOTAL.labels(mode=mode, rerank=str(bool(rerank)).lower(), tenant=tenant_id).inc()
        return {
            "answer": safe_answer,
            "citations": citations,
            "used_mode": mode,
            "rerank_used": rerank_used,
            "confidence": 0.0,
            "pii_blocked": True,
        }

    # Calculate confidence
    conf = _confidence(q, results, used_sentences)

    # Check confidence threshold
    if conf < 0.25:
        LOWCONF_TOTAL.labels(tenant=tenant_id).inc()
        ANSWERS_TOTAL.labels(mode=mode, rerank=str(bool(rerank)).lower(), tenant=tenant_id).inc()
        return {
            "answer": f"I found some related information but cannot confidently answer this question (confidence: {conf:.2f}). Please review the citations below.",
            "citations": citations,
            "used_mode": mode,
            "rerank_used": rerank_used,
            "confidence": conf,
        }

    # Success: emit metrics
    ANSWERS_TOTAL.labels(mode=mode, rerank=str(bool(rerank)).lower(), tenant=tenant_id).inc()

    response = {
        "answer": answer_text,
        "citations": citations,
        "used_mode": mode,
        "rerank_used": rerank_used,
        "confidence": round(conf, 3),
    }

    # Cache response
    _cache_put("answer", cache_key, response, tenant=tenant_id)

    return response


@app.get(
    "/embed/project", tags=["knowledge"], dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)]
)
async def embed_project(tenant: str = Depends(ApiKeyRequired), k: int = 200):
    """Project embeddings to 2D using UMAP or PCA fallback."""
    vs = app.state.VSTORE  # type: ignore[attr-defined]
    pts = vs.project_umap(tenant=tenant, k=k)
    return {"ok": True, "n": len(pts), "points": pts}


@app.get(
    "/embed/project.csv",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(AnyRole)],
)
async def embed_project_csv(tenant: str = Depends(ApiKeyRequired), k: int = 200):
    """Export 2D projection as CSV."""
    from fastapi.responses import PlainTextResponse

    vs = app.state.VSTORE  # type: ignore[attr-defined]
    csv = vs.project_umap_csv(tenant=tenant, k=k)
    return PlainTextResponse(csv, media_type="text/csv")


@app.post(
    "/knowledge/ingest-url",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def knowledge_ingest_url(
    url: str, source: str = "url", tenant: str = Depends(ApiKeyRequired)
):
    """Ingest knowledge from a URL with HTML text extraction."""
    import html
    import re
    from urllib.request import urlopen

    def _strip_html(data: bytes) -> str:
        # naive HTML text extractor
        s = data.decode("utf-8", errors="ignore")
        s = re.sub(r"(?is)<script.*?>.*?</script>", " ", s)
        s = re.sub(r"(?is)<style.*?>.*?</style>", " ", s)
        s = re.sub(r"(?is)<.*?>", " ", s)
        s = html.unescape(s)
        return re.sub(r"\s+", " ", s).strip()

    try:
        data = urlopen(url, timeout=10).read()
        text = _strip_html(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")

    chunks = _simple_chunk(text)
    embedder = app.state.EMBEDDER
    vectors = embedder.embed(chunks)
    app.state.VSTORE.upsert(tenant, source, chunks, vectors)
    return {"ok": True, "ingested_chunks": len(chunks), "source": source, "tenant": tenant}


def _read_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        import io

        from pypdf import PdfReader

        r = PdfReader(io.BytesIO(data))
        return "\n".join([p.extract_text() or "" for p in r.pages])
    except Exception:
        return ""


@app.post(
    "/knowledge/ingest-file",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def knowledge_ingest_file(
    file: UploadFile = File(...),
    source: str = "upload",
    tenant: str | None = Depends(ApiKeyRequired),
):
    """Ingest knowledge from uploaded file (PDF, TXT, MD, DOCX)."""
    raw = await file.read()
    text = ""
    name = (file.filename or "").lower()

    if name.endswith(".pdf"):
        text = _read_text_from_pdf(raw)
    elif name.endswith(".txt") or name.endswith(".md"):
        text = raw.decode("utf-8", errors="ignore")
    elif name.endswith(".docx"):
        try:
            from io import BytesIO

            import docx  # python-docx (optional)

            d = docx.Document(BytesIO(raw))
            text = "\n".join([p.text for p in d.paragraphs])
        except Exception:
            # Fallback: try UTF-8
            text = raw.decode("utf-8", errors="ignore")
    else:
        # Default: treat as text
        text = raw.decode("utf-8", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text extracted from file")

    chunks = _simple_chunk(text)
    embedder = app.state.EMBEDDER
    vectors = embedder.embed(chunks)
    tenant_id = tenant or "default"
    app.state.VSTORE.upsert(tenant_id, source or "upload", chunks, vectors)

    return {
        "ok": True,
        "filename": file.filename,
        "ingested_chunks": len(chunks),
        "source": source or "upload",
        "tenant": tenant_id,
    }


# ============================================================================
# Background Ingestion (Async with Job Queue)
# ============================================================================


@app.post(
    "/knowledge/ingest-text-async",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def ingest_text_async(
    text: str = Body(..., embed=True),
    source: str = Body("upload", embed=True),
    tenant: str | None = Depends(ApiKeyRequired),
):
    """
    Enqueue text ingestion to background worker.
    Returns immediately with job_id for status polling.
    """
    tenant_id = tenant or "default"
    q = _rq()
    job = q.enqueue("pods.customer_ops.worker.ingest_text_job", text, source, tenant_id)
    return {
        "ok": True,
        "job_id": job.id,
        "queued": True,
        "type": "text",
        "tenant": tenant_id,
        "source": source,
    }


@app.post(
    "/knowledge/ingest-url-async",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def ingest_url_async(
    url: str = Body(..., embed=True),
    source: str = Body("web", embed=True),
    tenant: str | None = Depends(ApiKeyRequired),
):
    """
    Enqueue URL ingestion to background worker.
    Downloads and processes URL content asynchronously.
    """
    tenant_id = tenant or "default"
    q = _rq()
    job = q.enqueue("pods.customer_ops.worker.ingest_url_job", url, source, tenant_id)
    return {
        "ok": True,
        "job_id": job.id,
        "queued": True,
        "type": "url",
        "tenant": tenant_id,
        "source": source,
        "url": url,
    }


@app.post(
    "/knowledge/ingest-file-async",
    tags=["knowledge"],
    dependencies=[Depends(ApiKeyRequired), Depends(EditorOrAdmin)],
)
async def ingest_file_async(
    file: UploadFile = File(...),
    source: str = "upload",
    tenant: str | None = Depends(ApiKeyRequired),
):
    """
    Enqueue file ingestion to background worker.
    Supports PDF, TXT, MD, DOCX formats.
    """
    tenant_id = tenant or "default"
    file_bytes = await file.read()
    filename = file.filename or "upload"

    q = _rq()
    job = q.enqueue(
        "pods.customer_ops.worker.ingest_file_job", file_bytes, filename, source, tenant_id
    )
    return {
        "ok": True,
        "job_id": job.id,
        "queued": True,
        "type": "file",
        "filename": filename,
        "tenant": tenant_id,
        "source": source,
    }


@app.get("/ops/jobs/{job_id}", tags=["ops"], dependencies=[Depends(AdminOnly)])
async def job_status(job_id: str):
    """
    Poll background job status.
    Returns job state: queued, started, finished, failed.
    """
    job = _rq_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")

    data = {
        "id": job_id,
        "status": job.get_status(),
        "enqueued_at": str(job.enqueued_at) if job.enqueued_at else None,
        "started_at": str(job.started_at) if job.started_at else None,
        "ended_at": str(job.ended_at) if job.ended_at else None,
    }

    if job.is_finished:
        data["result"] = job.result
    if job.is_failed:
        data["error"] = str(job.exc_info)[-1000:] if job.exc_info else "failed"

    return data


def _count_pii_hits(conn, doc_key: str):
    """Count PII placeholder occurrences for a document."""
    key = doc_key.replace('"', '""')
    row = conn.execute(f"""
        SELECT
            COALESCE(SUM(CAST(instr(content,'[EMAIL]')>0 AS INTEGER)),0) AS email,
            COALESCE(SUM(CAST(instr(content,'[PHONE]')>0 AS INTEGER)),0) AS phone,
            COALESCE(SUM(CAST(instr(content,'[SSN]')>0 AS INTEGER)),0)   AS ssn,
            COALESCE(SUM(CAST(instr(content,'[CARD]')>0 AS INTEGER)),0)  AS card
        FROM chunks
        WHERE metadata LIKE '%"url": "{key}%' OR metadata LIKE '%"source": "{key}%'
    """).fetchone()
    return {"EMAIL": row[0], "PHONE": row[1], "SSN": row[2], "CARD": row[3]}


@app.get("/admin/overview", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def admin_overview(limit: int = Query(20, description="Number of recent ingests to return")):
    """
    Admin dashboard: recent ingestion summary.
    Returns metadata-rich view of last N documents ingested.
    """
    from pods.customer_ops.db_duck import get_conn as get_duck_conn
    from pods.customer_ops.db_duck import recent_ingests

    docs = recent_ingests(limit=limit)

    # Add human-readable timestamps and PII info
    import datetime

    conn = get_duck_conn()
    try:
        for doc in docs:
            if doc.get("ingested_at"):
                doc["ingested_at_human"] = datetime.datetime.fromtimestamp(
                    doc["ingested_at"]
                ).strftime("%Y-%m-%d %H:%M:%S")

            # Add PII stats
            doc_key = doc.get("doc_key", "")
            hits = _count_pii_hits(conn, doc_key)

            # Try to get PII metadata from a representative chunk
            meta_row = conn.execute(
                """
                SELECT metadata FROM chunks
                WHERE metadata LIKE ? OR metadata LIKE ?
                LIMIT 1
            """,
                [
                    f'%"url": "{doc_key.replace(chr(34), chr(34)+chr(34))}%',
                    f'%"source": "{doc_key.replace(chr(34), chr(34)+chr(34))}%',
                ],
            ).fetchone()

            pii_cfg = None
            if meta_row:
                try:
                    meta = json.loads(meta_row[0])
                    pii_cfg = meta.get("pii_redaction")
                except:
                    pass

            doc["pii"] = {
                "enabled": bool(pii_cfg.get("enabled"))
                if (isinstance(pii_cfg, dict) and "enabled" in pii_cfg)
                else any(hits.values()),
                "types": sorted(pii_cfg.get("types", [])) if isinstance(pii_cfg, dict) else [],
                "hits": hits,
            }
    finally:
        conn.close()

    return {"ok": True, "count": len(docs), "documents": docs}


@app.get("/admin/doc", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def admin_doc(
    source: str | None = Query(None, description="Filter by document source"),
    url: str | None = Query(None, description="Filter by URL"),
    limit: int = Query(5, ge=1, le=50, description="Max chunks to return"),
):
    """
    Admin endpoint: fetch raw chunk snippets for inspection.
    Useful for verifying PII redaction and content quality.
    """
    from pods.customer_ops.db_duck import get_conn as get_duck_conn

    if not source and not url:
        return {"count": 0, "items": []}

    where = []
    params = []
    if source:
        # Use LIKE since metadata is stored as JSON string
        where.append("metadata LIKE ?")
        params.append(f'%"source": "{source}"%')
    if url:
        where.append("metadata LIKE ?")
        params.append(f'%"url": "{url}"%')

    w = " AND ".join(where)
    conn = get_duck_conn()
    rows = conn.execute(
        f"""
      SELECT substr(content,1,1000) AS snippet,
             metadata
      FROM chunks
      WHERE {w}
      LIMIT ?
    """,
        params + [limit],
    ).fetchall()

    return {
        "count": len(rows),
        "items": [{"snippet": r[0], "metadata": json.loads(r[1])} for r in rows],
    }


@app.get("/admin/ui", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def admin_ui():
    """
    Admin dashboard UI: lightweight HTML page for monitoring ingests and searching.
    """
    from fastapi.responses import HTMLResponse

    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AetherLink Admin Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #2c3e50; }
        .section {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .search-box input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .search-box button {
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .search-box button:hover { background: #2980b9; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th {
            background: #34495e;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 8px;
            border-bottom: 1px solid #ecf0f1;
        }
        tr:hover { background: #f8f9fa; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .pill { display:inline-block; padding:2px 8px; border-radius:9999px; font-size:12px; }
        .pill-ok { background:#10b981; color:white; }
        .pill-off { background:#9ca3af; color:white; }
        .btn-sm {
            padding: 4px 8px;
            font-size: 11px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
        }
        .btn-sm:hover { background: #5a6268; }
        .search-results {
            margin-top: 20px;
        }
        .result-item {
            padding: 12px;
            margin-bottom: 10px;
            background: #f8f9fa;
            border-left: 3px solid #3498db;
            border-radius: 4px;
        }
        .result-score {
            float: right;
            font-weight: 600;
            color: #3498db;
        }
        .loading { color: #999; font-style: italic; }
        .error { color: #e74c3c; padding: 10px; background: #fadbd8; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 AetherLink Admin Dashboard</h1>

        <div class="section">
            <h2 style="margin-bottom: 15px;">🔍 Search Knowledge Base</h2>
            <div class="search-box">
                <input type="text" id="searchQuery" placeholder="Enter search query..." />
                <button onclick="performSearch()">Search</button>
            </div>
            <div id="searchResults" class="search-results"></div>
        </div>

        <div class="section">
            <h2 style="margin-bottom: 15px;">📊 Recent Ingestions</h2>
            <div id="loading" class="loading">Loading...</div>
            <div id="error" class="error" style="display: none;"></div>
            <table id="ingestsTable" style="display: none;">
                <thead>
                    <tr>
                        <th>Title / Source</th>
                        <th>URL</th>
                        <th>Lang</th>
                        <th>Published</th>
                        <th>Chunks</th>
                        <th>Chars</th>
                        <th>Extraction</th>
                        <th>PII</th>
                        <th>Ingested</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="ingestsBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        async function loadOverview() {
            try {
                const response = await fetch('/admin/overview');
                const data = await response.json();

                document.getElementById('loading').style.display = 'none';
                document.getElementById('ingestsTable').style.display = 'table';

                const tbody = document.getElementById('ingestsBody');
                tbody.innerHTML = '';

                data.documents.forEach(doc => {
                    const row = tbody.insertRow();

                    // Title / Source
                    const titleCell = row.insertCell();
                    titleCell.innerHTML = doc.title
                        ? `<strong>${escapeHtml(doc.title)}</strong><br><small>${escapeHtml(doc.doc_key)}</small>`
                        : escapeHtml(doc.doc_key);

                    // URL
                    const urlCell = row.insertCell();
                    urlCell.innerHTML = doc.url
                        ? `<a href="${escapeHtml(doc.url)}" target="_blank" style="color: #3498db;">${truncate(doc.url, 40)}</a>`
                        : '-';

                    // Lang
                    row.insertCell().textContent = doc.lang || '-';

                    // Published
                    row.insertCell().textContent = doc.published || '-';

                    // Chunks
                    const chunksCell = row.insertCell();
                    chunksCell.innerHTML = `<span class="badge badge-info">${doc.chunks}</span>`;

                    // Chars
                    row.insertCell().textContent = doc.total_chars.toLocaleString();

                    // Extraction
                    const extractCell = row.insertCell();
                    if (doc.extraction) {
                        const badgeClass = doc.extraction === 'trafilatura' ? 'badge-success' : 'badge-warning';
                        extractCell.innerHTML = `<span class="badge ${badgeClass}">${doc.extraction}</span>`;
                    } else {
                        extractCell.textContent = '-';
                    }

                    // PII
                    const piiCell = row.insertCell();
                    const p = doc.pii || {enabled:false, hits:{EMAIL:0,PHONE:0,SSN:0,CARD:0}};
                    const txt = `E:${p.hits.EMAIL||0} P:${p.hits.PHONE||0} S:${p.hits.SSN||0} C:${p.hits.CARD||0}`;
                    const cls = p.enabled ? "pill pill-ok" : "pill pill-off";
                    piiCell.innerHTML = `<span class="${cls}" title="${txt}">PII</span> <span style="font-size:11px;color:#6b7280">${txt}</span>`;

                    // Ingested
                    row.insertCell().textContent = doc.ingested_at_human || '-';

                    // Actions
                    const actionsCell = row.insertCell();
                    if (doc.url) {
                        actionsCell.innerHTML = `<button class="btn-sm" onclick="copyUrl('${escapeHtml(doc.url)}')">Copy URL</button>`;
                    }
                });
            } catch (err) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Error loading data: ' + err.message;
            }
        }

        async function performSearch() {
            const query = document.getElementById('searchQuery').value.trim();
            if (!query) return;

            const resultsDiv = document.getElementById('searchResults');
            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';

            try {
                const response = await fetch(`/search?q=${encodeURIComponent(query)}&k=5`);
                const data = await response.json();

                if (data.results.length === 0) {
                    resultsDiv.innerHTML = '<p style="color: #999;">No results found.</p>';
                    return;
                }

                resultsDiv.innerHTML = `<p style="margin-bottom: 10px;"><strong>${data.count} results found:</strong></p>`;

                data.results.forEach(result => {
                    const div = document.createElement('div');
                    div.className = 'result-item';
                    div.innerHTML = `
                        <div class="result-score">${(result.score * 100).toFixed(1)}%</div>
                        <div><strong>${escapeHtml(result.id)}</strong></div>
                        <div style="margin-top: 5px;">${escapeHtml(truncate(result.content, 200))}</div>
                        ${result.metadata.url ? `<div style="margin-top: 5px; font-size: 12px; color: #666;"><a href="${escapeHtml(result.metadata.url)}" target="_blank">${escapeHtml(result.metadata.url)}</a></div>` : ''}
                    `;
                    resultsDiv.appendChild(div);
                });
            } catch (err) {
                resultsDiv.innerHTML = `<div class="error">Search error: ${err.message}</div>`;
            }
        }

        function copyUrl(url) {
            navigator.clipboard.writeText(url).then(() => {
                alert('URL copied to clipboard!');
            }).catch(err => {
                alert('Failed to copy: ' + err);
            });
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function truncate(str, maxLen) {
            return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
        }

        // Allow Enter key to trigger search
        document.getElementById('searchQuery').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') performSearch();
        });

        // Load on page load
        loadOverview();
    </script>
</body>
</html>
    """

    return HTMLResponse(content=html_content)


# ============================================================================
# Admin: API Key Management
# ============================================================================


@app.post("/admin/apikeys", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def create_api_key(
    tenant_id: str = Body(...),
    role: str = Body(...),
    name: str | None = Body(None),
    rpm_limit: int | None = Body(None),
    daily_quota: int | None = Body(None),
):
    """
    Create new API key with specified tenant and role.

    Generates a secure random key and stores with quotas/limits.
    """
    import secrets

    from pods.customer_ops.db_duck import upsert_api_key

    # Validate role
    if role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    # Generate secure key
    key = secrets.token_urlsafe(30)

    # Store in database
    key_data = upsert_api_key(
        key=key,
        tenant_id=tenant_id,
        role=role,
        name=name,
        rpm_limit=rpm_limit,
        daily_quota=daily_quota,
        enabled=True,
    )

    return {"ok": True, "key": key_data}


@app.get("/admin/apikeys", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def list_api_keys(limit: int = Query(100, le=500)):
    """
    List all API keys.

    Returns keys with usage stats and configuration.
    """
    from pods.customer_ops.db_duck import list_api_keys as db_list_keys

    keys = db_list_keys(limit=limit)

    return {"ok": True, "count": len(keys), "keys": keys}


@app.patch("/admin/apikeys/{key}", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def update_api_key(
    key: str,
    enabled: bool | None = Body(None),
    name: str | None = Body(None),
    role: str | None = Body(None),
    rpm_limit: int | None = Body(None),
    daily_quota: int | None = Body(None),
):
    """
    Update API key configuration.

    Can toggle enabled status, update limits, or change role.
    """
    from pods.customer_ops.db_duck import (
        get_api_key,
        set_api_key_enabled,
        upsert_api_key,
    )

    # Get current key
    key_data = get_api_key(key)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")

    # Handle simple enabled toggle
    if enabled is not None and all(x is None for x in [name, role, rpm_limit, daily_quota]):
        set_api_key_enabled(key, enabled)
        return {"ok": True, "key": get_api_key(key)}

    # Full update
    updated = upsert_api_key(
        key=key,
        tenant_id=key_data["tenant_id"],
        role=role if role is not None else key_data["role"],
        name=name if name is not None else key_data["name"],
        rpm_limit=rpm_limit if rpm_limit is not None else key_data["rpm_limit"],
        daily_quota=daily_quota if daily_quota is not None else key_data["daily_quota"],
        enabled=enabled if enabled is not None else key_data["enabled"],
    )

    return {"ok": True, "key": updated}


@app.delete("/admin/apikeys/{key}", tags=["admin"], dependencies=[Depends(AdminOnly)])
async def delete_api_key(key: str):
    """
    Delete an API key.

    Permanently removes the key from the database.
    """
    from pods.customer_ops.db_duck import delete_api_key as db_delete_key
    from pods.customer_ops.db_duck import get_api_key

    # Check if exists
    if not get_api_key(key):
        raise HTTPException(status_code=404, detail="API key not found")

    db_delete_key(key)

    return {"ok": True, "deleted": key}


@app.get(
    "/ops/experiments",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
def experiments_dashboard(tenant: str = Depends(ApiKeyRequired)):
    try:
        from .experiments import calculate_significance, list_experiments

        experiments = list_experiments()
        for exp_name, exp_info in experiments.items():
            if exp_info.get("enabled"):
                sig = calculate_significance(exp_name)
                exp_info["significance"] = sig
        return {
            "experiments": experiments,
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error("experiments_dashboard_failed", extra={"error": str(e)})
        return {"experiments": {}, "error": str(e)}


@app.post(
    "/ops/experiments/{experiment_name}/promote",
    tags=["ops"],
    dependencies=[Depends(ApiKeyRequired), Depends(ops_limit_dep())],
)
def promote_experiment(experiment_name: str, tenant: str = Depends(ApiKeyRequired)):
    try:
        from .experiments import promote_winner

        result = promote_winner(experiment_name)
        if result.get("ok"):
            logger.info(
                "experiment_promoted",
                extra={
                    "experiment": experiment_name,
                    "winner": result.get("promoted"),
                },
            )
        else:
            logger.warning(
                "experiment_promotion_failed",
                extra={
                    "experiment": experiment_name,
                    "error": result.get("error"),
                },
            )
        return result
    except Exception as e:
        logger.error(
            "promote_experiment_failed",
            extra={
                "experiment": experiment_name,
                "error": str(e),
            },
        )
        return {"ok": False, "error": str(e)}


@app.post("/v1/lead", response_model=dict, dependencies=[Depends(faq_limit_dep())])
def create_lead(req: LeadRequest, request: Request, tenant: str = Depends(ApiKeyRequired)):
    request_id = getattr(request.state, "request_id", "n/a")
    s = get_settings()
    from .experiments import get_variant, get_variant_config

    enrichment_variant = get_variant(tenant or "public", "enrichment_model")
    followup_variant = get_variant(tenant or "public", "followup_timing")
    prediction_variant = get_variant(tenant or "public", "prediction_threshold")
    enr = {"intent": "unknown", "urgency": "medium", "sentiment": "neutral", "score": 0.5}
    if s.ENABLE_ENRICHMENT:
        enr = enrich_text(req.details or req.name or "")
        LEAD_ENRICH_TOTAL.labels(enr["intent"], enr["urgency"], enr["sentiment"]).inc()
        LEAD_SCORE_HIST.observe(float(enr.get("score", 0.0)))
    pred_prob = None
    if s.ENABLE_ENRICHMENT:
        try:
            from .predict import predict

            pred_start = time.time()
            pred_prob = predict(
                score=float(enr.get("score", 0.5)),
                intent=str(enr.get("intent", "unknown")),
                sentiment=str(enr.get("sentiment", "neutral")),
                urgency=str(enr.get("urgency", "medium")),
                details=req.details or "",
                tenant=tenant or "public",
                created_at=int(time.time()),
            )
            if pred_prob is not None:
                PRED_PROB_HIST.observe(pred_prob)
                PRED_LATENCY.observe(time.time() - pred_start)
        except Exception as e:
            logger.warning("prediction_error", extra={"error": str(e)})
    lead_id = store_create_lead(
        tenant=tenant or "public",
        name=req.name,
        phone=req.phone,
        details=req.details,
    )
    if s.ENABLE_MEMORY:
        try:
            append_history_safe(
                tenant=tenant or "public",
                lead_id=lead_id,
                role="user",
                text=req.details or req.name,
                enable_redaction=s.ENABLE_PII_REDACTION,
                extra_patterns_csv=s.PII_EXTRA_PATTERNS,
            )
        except Exception:
            pass
    logger.info(
        "lead_created",
        extra={
            "request_id": request_id,
            "tenant": tenant,
            "lead_id": lead_id,
            "intent": enr["intent"],
            "urgency": enr["urgency"],
        },
    )
    INTENT_COUNT.labels("lead_capture", "/v1/lead").inc()
    followup_config = get_variant_config(tenant or "public", "followup_timing")
    prediction_config = get_variant_config(tenant or "public", "prediction_threshold")
    followup_threshold = prediction_config.get("threshold", s.FOLLOWUP_RULE_TOP_P)
    if app.state.q_followups and pred_prob is not None and pred_prob >= followup_threshold:
        try:
            from datetime import timedelta

            from .tasks_followup import run_followup

            base_url = str(request.base_url).rstrip("/")
            api_key = request.headers.get("x-api-key", "")
            if followup_config and "delay_seconds" in followup_config:
                schedules = [followup_config["delay_seconds"]]
            else:
                schedules = _parse_schedules(s.FOLLOWUP_SCHEDULES)
            for delay in schedules:
                app.state.q_followups.enqueue_in(
                    timedelta(seconds=delay),
                    run_followup,
                    base_url=base_url,
                    lead_id=lead_id,
                    strategy=f"{delay}s",
                    message=f"Auto follow-up at +{delay}s",
                    api_key=api_key,
                    experiment_variant=followup_variant,
                )
            logger.info(
                "followups_enqueued",
                extra={
                    "lead_id": lead_id,
                    "pred_prob": pred_prob,
                    "count": len(schedules),
                    "followup_variant": followup_variant,
                    "prediction_threshold": followup_threshold,
                },
            )
        except Exception as e:
            logger.warning("followup_enqueue_error", extra={"error": str(e)})
    response_data = LeadResponse(lead_id=lead_id).model_dump()
    response_data.update(enr)
    if pred_prob is not None:
        response_data["pred_prob"] = round(pred_prob, 3)
    response_data["experiments"] = {
        "enrichment_model": enrichment_variant,
        "followup_timing": followup_variant,
        "prediction_threshold": prediction_variant,
    }
    return ok(
        request_id,
        response_data,
        intent="lead_capture",
        confidence=float(enr["score"]),
    )


@app.get("/v1/lead", response_model=dict, dependencies=[Depends(faq_limit_dep())])
def list_lead(request: Request, tenant: str = Depends(ApiKeyRequired)):
    request_id = getattr(request.state, "request_id", "n/a")
    items = store_list_leads(tenant=tenant or "public", limit=50)
    lead_items = []
    for item in items:
        lead_item = LeadItem(**item)
        try:
            hist = get_history(tenant or "public", item["id"], limit=3)
            lead_item.last_messages = hist
        except Exception:
            lead_item.last_messages = []
        lead_items.append(lead_item)
    logger.info(
        "lead_list", extra={"request_id": request_id, "tenant": tenant, "count": len(items)}
    )
    return ok(
        request_id,
        LeadListResponse(items=lead_items).model_dump(),
        intent="lead_list",
        confidence=1.0,
    )


@app.get("/v1/lead/{lead_id}/history", response_model=dict)
def lead_history(
    lead_id: str,
    request: Request,
    limit: int = 20,
    tenant: str = Depends(ApiKeyRequired),
):
    request_id = getattr(request.state, "request_id", "n/a")
    try:
        items = get_history(tenant or "public", lead_id, limit=limit)
        logger.info(
            "lead_history",
            extra={"request_id": request_id, "lead_id": lead_id, "count": len(items)},
        )
        return ok(
            request_id, {"lead_id": lead_id, "items": items}, intent="lead_history", confidence=1.0
        )
    except Exception as e:
        logger.error(
            "lead_history_failed",
            extra={"request_id": request_id, "lead_id": lead_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {e}")


@app.get("/v1/search", response_model=dict, dependencies=[Depends(faq_limit_dep())])
def search_leads(
    q: str,
    request: Request,
    limit: int = 20,
    tenant: str = Depends(ApiKeyRequired),
):
    request_id = getattr(request.state, "request_id", "n/a")
    hits = []
    all_leads = store_list_leads(tenant=tenant or "public", limit=500)
    query_tokens = q.lower().split()
    for lead in all_leads:
        try:
            msgs = get_history(tenant or "public", lead["id"], limit=5)
            text = " ".join(m.get("text", "") for m in msgs).lower()
            score = sum(text.count(tok) for tok in query_tokens)
            if score > 0:
                preview = " ".join(m.get("text", "") for m in msgs)[:240]
                hits.append(
                    {
                        "lead_id": lead["id"],
                        "name": lead.get("name", ""),
                        "phone": lead.get("phone", ""),
                        "score": score,
                        "preview": preview,
                    }
                )
        except Exception:
            pass
    hits.sort(key=lambda x: x["score"], reverse=True)
    results = hits[:limit]
    logger.info(
        "search_leads", extra={"request_id": request_id, "query": q, "results": len(results)}
    )
    return ok(
        request_id,
        {"query": q, "count": len(results), "results": results},
        intent="search",
        confidence=1.0,
    )


@app.post("/v1/lead/{lead_id}/outcome", response_model=dict)
def record_outcome(
    lead_id: str,
    req: OutcomeRequest,
    request: Request,
    tenant: str = Depends(ApiKeyRequired),
):
    from .lead_store import get_lead, set_outcome

    request_id = getattr(request.state, "request_id", "n/a")
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    outcome_record = set_outcome(
        lead_id=lead_id,
        outcome=req.outcome,
        notes=req.notes,
        time_to_conversion=req.time_to_conversion,
    )
    from .experiments import get_variant
    from .experiments import track_outcome as track_experiment_outcome

    lead_tenant = lead.get("tenant", "public")
    enrichment_variant = get_variant(lead_tenant, "enrichment_model")
    followup_variant = get_variant(lead_tenant, "followup_timing")
    prediction_variant = get_variant(lead_tenant, "prediction_threshold")
    track_experiment_outcome(lead_tenant, "enrichment_model", enrichment_variant, req.outcome)
    track_experiment_outcome(lead_tenant, "followup_timing", followup_variant, req.outcome)
    track_experiment_outcome(lead_tenant, "prediction_threshold", prediction_variant, req.outcome)
    OUTCOME_TOTAL.labels(outcome=req.outcome).inc()
    try:
        from .lead_store import list_outcomes

        recent = list_outcomes(limit=1000)
        if recent:
            booked_count = sum(1 for r in recent if r.get("outcome") == "booked")
            conversion_rate = booked_count / len(recent)
            CONVERSION_RATE.set(conversion_rate)
            from .experiments import EXPERIMENT_CONVERSION_RATE, EXPERIMENT_SAMPLE_SIZE

            for exp_name in ["enrichment_model", "followup_timing", "prediction_threshold"]:
                variant_counts = {}
                for outcome_rec in recent:
                    outcome_tenant = outcome_rec.get("tenant", "public")
                    variant = get_variant(outcome_tenant, exp_name)
                    if variant not in variant_counts:
                        variant_counts[variant] = {"total": 0, "booked": 0}
                    variant_counts[variant]["total"] += 1
                    if outcome_rec.get("outcome") == "booked":
                        variant_counts[variant]["booked"] += 1
                for variant, counts in variant_counts.items():
                    EXPERIMENT_SAMPLE_SIZE.labels(experiment=exp_name, variant=variant).set(
                        counts["total"]
                    )
                    if counts["total"] > 0:
                        rate = counts["booked"] / counts["total"]
                        EXPERIMENT_CONVERSION_RATE.labels(experiment=exp_name, variant=variant).set(
                            rate
                        )
    except Exception:
        pass
    logger.info(
        "outcome_recorded",
        extra={
            "request_id": request_id,
            "lead_id": lead_id,
            "outcome": req.outcome,
            "tenant": tenant,
            "enrichment_variant": enrichment_variant,
            "followup_variant": followup_variant,
            "prediction_variant": prediction_variant,
        },
    )
    return ok(
        request_id,
        OutcomeResponse(
            lead_id=lead_id,
            outcome=req.outcome,
            recorded_at=outcome_record["recorded_at"],
        ).model_dump(),
        intent="outcome_tracking",
        confidence=1.0,
    )


@app.get("/v1/analytics/outcomes", response_model=dict)
def get_outcome_analytics(
    request: Request,
    limit: int = 500,
    tenant: str = Depends(ApiKeyRequired),
):
    from .lead_store import list_leads, list_outcomes

    request_id = getattr(request.state, "request_id", "n/a")
    outcomes = list_outcomes(limit=limit)
    total_outcomes = len(outcomes)
    all_leads = list_leads(tenant=tenant or "public", limit=5000)
    total_leads = len(all_leads)
    breakdown: dict[str, int] = {}
    for outcome_rec in outcomes:
        outcome_type = outcome_rec.get("outcome", "unknown")
        breakdown[outcome_type] = breakdown.get(outcome_type, 0) + 1
    booked_count = breakdown.get("booked", 0)
    conversion_rate = booked_count / total_outcomes if total_outcomes > 0 else 0.0
    conversion_times = [
        r["time_to_conversion"]
        for r in outcomes
        if r.get("outcome") == "booked" and r.get("time_to_conversion")
    ]
    avg_time = sum(conversion_times) / len(conversion_times) if conversion_times else None
    logger.info(
        "analytics_outcomes",
        extra={
            "request_id": request_id,
            "tenant": tenant,
            "total_outcomes": total_outcomes,
            "conversion_rate": conversion_rate,
        },
    )
    return ok(
        request_id,
        AnalyticsResponse(
            total_leads=total_leads,
            total_outcomes=total_outcomes,
            conversion_rate=conversion_rate,
            outcome_breakdown=breakdown,
            avg_time_to_conversion=avg_time,
        ).model_dump(),
        intent="analytics",
        confidence=1.0,
    )


def check_booking_intent(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in BOOKING_WORDS)


@app.post("/v1/faq", response_model=FaqAnswer, dependencies=[Depends(faq_limit_dep())])
def faq_endpoint(request: Request, query: FaqRequest, tenant: str = Depends(ApiKeyRequired)):
    request_id = getattr(request.state, "request_id", "n/a")
    cached = get_semcache(query.query)
    if cached:
        logger.info("faq_cache_hit", extra={"request_id": request_id, "tenant": tenant})
        INTENT_COUNT.labels("faq", "/v1/faq").inc()
        return ok(request_id, {**cached, "cached": True}, intent="faq", confidence=0.99)
    results = rag.query(query.query, k=1)
    if not results:
        log_faq(query.query, found=False)
        raise HTTPException(status_code=404, detail="No answer found")
    _, text, score = results[0]
    answer = text.split("A: ")[-1].strip()
    citation = text.split("Q: ")[1].split("A: ")[0].strip()
    log_faq(query.query, found=True, score=score)
    logger.info("faq_request", extra={"request_id": request_id, "tenant": tenant})
    response = {"answer": answer, "citations": [citation], "score": score}
    set_semcache(query.query, response)
    INTENT_COUNT.labels("faq", "/v1/faq").inc()
    return ok(
        request_id, {**response, "cached": False}, intent="faq", confidence=round(score or 0.0, 2)
    )


@app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(chat_limit_dep())])
def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    tenant: str = Depends(ApiKeyRequired),
):
    request_id = getattr(request.state, "request_id", "n/a")
    results = rag.query(payload.message, k=1)
    if results and results[0][2] > CONFIDENCE_THRESHOLD:
        _, text, score = results[0]
        answer = text.split("A: ")[-1].strip()
        lead = create_lead_crud(
            db=db,
            name=payload.user_id,
            phone=None,
            intent="faq",
        )
        log_chat(
            user_id=payload.user_id,
            message=payload.message,
            intent="faq",
            confidence=score,
        )
        logger.info("chat_request", extra={"request_id": request_id, "tenant": tenant})
        INTENT_COUNT.labels("faq", "/v1/faq").inc()
        return ok(
            request_id,
            {"reply": answer, "intent": "faq", "confidence": score, "lead_id": lead.id},
            intent="faq",
            confidence=score,
        )
    if check_booking_intent(payload.message):
        lead = create_lead_crud(
            db=db,
            name=payload.user_id,
            phone=None,
            intent="booking",
        )
        log_chat(
            user_id=payload.user_id,
            message=payload.message,
            intent="booking",
            confidence=1.0,
        )
        logger.info("chat_request", extra={"request_id": request_id, "tenant": tenant})
        INTENT_COUNT.labels("booking", "/v1/chat").inc()
        return ok(
            request_id,
            {
                "reply": "I can help you schedule an appointment. Let me transfer you to our booking system.",
                "intent": "booking",
                "confidence": 1.0,
                "lead_id": lead.id,
            },
            intent="booking",
            confidence=1.0,
        )
    lead = create_lead_crud(
        db=db,
        name=payload.user_id,
        phone=None,
        intent="human",
    )
    log_chat(
        user_id=payload.user_id,
        message=payload.message,
        intent="human",
        confidence=0.0,
    )
    logger.info("chat_request", extra={"request_id": request_id, "tenant": tenant})
    INTENT_COUNT.labels("human", "/v1/chat").inc()
    return ok(
        request_id,
        {
            "reply": "I'll connect you with one of our team members who can help you better.",
            "intent": "human",
            "confidence": 0.0,
            "lead_id": lead.id,
        },
        intent="human",
        confidence=0.0,
    )
