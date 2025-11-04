from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import time
from rbac import require_roles

app = FastAPI(title="AetherLink AI Orchestrator", version="0.1.0")

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

# endpoints for existing services
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
    Decide which AI backend to call based on intent.
    v1: route to existing ai-summarizer for known intents.
    
    Requires: agent, operator, or admin role
    """
    start = time.perf_counter()
    provider_used = "ai-summarizer"
    result: dict = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if req.intent == "extract-lead":
                resp = await client.post(
                    f"{AI_SUMMARIZER_URL}/summaries/extract-lead",
                    json={
                        "tenant_id": req.tenant_id,
                        "raw_text": req.payload.get("raw_text", ""),
                    },
                )
                resp.raise_for_status()
                result = resp.json()
            elif req.intent == "summarize-activity":
                resp = await client.post(
                    f"{AI_SUMMARIZER_URL}/summaries/activity",
                    json={
                        "tenant_id": req.tenant_id,
                        "activity": req.payload.get("activity", ""),
                    },
                )
                resp.raise_for_status()
                result = resp.json()
            else:
                raise HTTPException(status_code=400, detail=f"Unknown intent: {req.intent}")
        except httpx.HTTPStatusError as e:
            # TODO: v2 fallback to Ollama / other providers
            latency_ms = (time.perf_counter() - start) * 1000
            await annotate(f"AI orchestrator failed for intent={req.intent}: HTTP {e.response.status_code}")
            raise HTTPException(status_code=502, detail=f"Provider error: {e.response.status_code}")
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            await annotate(f"AI orchestrator failed for intent={req.intent}: {e}")
            raise HTTPException(status_code=502, detail=str(e))

    latency_ms = (time.perf_counter() - start) * 1000
    await annotate(f"AI orchestrator handled intent={req.intent} in {latency_ms:.1f}ms via {provider_used}")

    return OrchestrateResponse(
        status="ok",
        provider=provider_used,
        latency_ms=latency_ms,
        result=result,
    )

@app.get("/ping")
def ping():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    return {"status": "up", "service": "ai-orchestrator"}
