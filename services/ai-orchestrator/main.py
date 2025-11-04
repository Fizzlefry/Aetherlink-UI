import os
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rbac import require_roles
from audit import audit_middleware, get_audit_stats

app = FastAPI(title="AetherLink AI Orchestrator v2", version="2.0.0")

# Phase III M6: Security Audit Logging
app.middleware("http")(audit_middleware)

# RBAC: Agents, operators, and admins can use AI orchestration
ai_allowed = require_roles(["agent", "operator", "admin"])

# CORS for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI Orchestrator v2: Provider Fallback Configuration
_provider_order = os.getenv("PROVIDER_ORDER", "claude,ollama,openai")
PROVIDER_ORDER: list[str] = [p.strip() for p in _provider_order.split(",") if p.strip()]

# Map provider names to URLs
PROVIDER_URLS = {
    "claude": os.getenv(
        "PROVIDER_CLAUDE_URL", "http://aether-ai-summarizer:9108/summaries/extract-lead"
    ),
    "ollama": os.getenv("PROVIDER_OLLAMA_URL", "http://ollama:11434/api/generate"),
    "openai": os.getenv("PROVIDER_OPENAI_URL", "http://openai-proxy:8088/v1/chat/completions"),
}

# In-memory provider health tracking
provider_health: dict[str, dict[str, Any]] = {
    name: {
        "healthy": True,
        "last_error": None,
        "last_checked": None,
        "total_calls": 0,
        "failed_calls": 0,
    }
    for name in PROVIDER_URLS.keys()
}

# Legacy endpoints
AI_SUMMARIZER_URL = os.getenv("AI_SUMMARIZER_URL", "http://aether-ai-summarizer:9108")
GRAFANA_ANNOTATIONS_URL = os.getenv("GRAFANA_ANNOTATIONS_URL")  # optional


class OrchestrateRequest(BaseModel):
    tenant_id: str
    intent: str  # "extract-lead" | "summarize-activity" | "classify" | ...
    payload: dict


class OrchestrateResponse(BaseModel):
    status: str
    provider: str
    latency_ms: float
    result: dict


def mark_provider_failure(name: str, error: str):
    """Mark a provider as unhealthy after a failure"""
    if name in provider_health:
        provider_health[name]["healthy"] = False
        provider_health[name]["last_error"] = error
        provider_health[name]["last_checked"] = datetime.utcnow().isoformat()
        provider_health[name]["failed_calls"] += 1


def mark_provider_success(name: str):
    """Mark a provider as healthy after a successful call"""
    if name in provider_health:
        provider_health[name]["healthy"] = True
        provider_health[name]["last_error"] = None
        provider_health[name]["last_checked"] = datetime.utcnow().isoformat()
        provider_health[name]["total_calls"] += 1


async def call_provider(provider: str, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Call a single AI provider. Raises exception on error.
    This is where you'd customize the payload format per provider.
    """
    url = PROVIDER_URLS.get(provider)
    if not url:
        raise RuntimeError(f"Provider {provider} has no URL configured")

    # For now, all providers use the same format
    # You can branch here based on provider type
    request_body = payload

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=request_body)

    if resp.status_code >= 400:
        raise RuntimeError(f"{provider} responded with {resp.status_code}: {resp.text}")

    return resp.json()


async def annotate(message: str):
    """Send annotation to Grafana if configured"""
    if not GRAFANA_ANNOTATIONS_URL:
        return
    try:
        async with httpx.AsyncClient() as client:
            # adjust to your Grafana API
            await client.post(GRAFANA_ANNOTATIONS_URL, json={"text": message})
    except Exception as e:
        print(f"Failed to annotate Grafana: {e}")


@app.post("/orchestrate", response_model=OrchestrateResponse, dependencies=[Depends(ai_allowed)])
async def orchestrate(req: OrchestrateRequest):
    """
    AI Orchestrator v2 with Provider Fallback

    Tries providers in order from PROVIDER_ORDER until one succeeds.
    Skips providers marked as unhealthy from recent failures.
    Returns the first successful response with provider name and latency.

    Requires: agent, operator, or admin role
    """
    start = time.perf_counter()
    errors: list[dict[str, str]] = []

    # Prepare payload based on intent (customize per provider if needed)
    if req.intent == "extract-lead":
        payload = {
            "tenant_id": req.tenant_id,
            "raw_text": req.payload.get("raw_text", ""),
        }
    elif req.intent == "summarize-activity":
        payload = {
            "tenant_id": req.tenant_id,
            "activity": req.payload.get("activity", ""),
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown intent: {req.intent}")

    # Try each provider in order
    for provider in PROVIDER_ORDER:
        # Skip explicitly unhealthy providers (failed recently)
        if provider in provider_health and provider_health[provider].get("healthy") is False:
            errors.append({"provider": provider, "error": "Provider marked unhealthy, skipping"})
            continue

        # Skip providers not in our URL map
        if provider not in PROVIDER_URLS:
            errors.append({"provider": provider, "error": "Provider not configured"})
            continue

        try:
            # Attempt to call this provider
            result = await call_provider(provider, req.intent, payload)

            # Success! Mark provider healthy and return
            mark_provider_success(provider)
            latency_ms = (time.perf_counter() - start) * 1000

            await annotate(
                f"AI orchestrator handled intent={req.intent} in {latency_ms:.1f}ms via {provider}"
            )

            return OrchestrateResponse(
                status="ok",
                provider=provider,
                latency_ms=latency_ms,
                result=result,
            )

        except Exception as e:
            # This provider failed, mark it and try next
            error_msg = str(e)
            mark_provider_failure(provider, error_msg)
            errors.append({"provider": provider, "error": error_msg})
            continue

    # If we got here, all providers failed
    latency_ms = (time.perf_counter() - start) * 1000
    await annotate(
        f"AI orchestrator failed for intent={req.intent}: all {len(PROVIDER_ORDER)} providers failed"
    )

    raise HTTPException(
        status_code=502,
        detail={
            "message": "All AI providers failed",
            "intent": req.intent,
            "tenant_id": req.tenant_id,
            "errors": errors,
            "provider_order": PROVIDER_ORDER,
            "latency_ms": latency_ms,
        },
    )


@app.get("/ping")
def ping():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "ai-orchestrator-v2",
        "providers": PROVIDER_ORDER,
    }


@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    return {"status": "up", "service": "ai-orchestrator"}


@app.get("/audit/stats", dependencies=[Depends(ai_allowed)])
async def audit_stats():
    """
    Get audit statistics for security monitoring.
    
    Phase III M6: Returns request counts, auth failures, and usage patterns.
    Requires: agent, operator, or admin role
    """
    return get_audit_stats()


@app.get("/providers/health")
async def providers_health():
    """
    Provider health status endpoint.
    Shows which AI providers are healthy/unhealthy and their error history.
    Used by Command Center for operational visibility.
    """
    return provider_health
