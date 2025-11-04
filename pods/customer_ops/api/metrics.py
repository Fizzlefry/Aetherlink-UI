from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

router = APIRouter()
INTENT_COUNT = Counter("agent_intent_total", "Intent counts", ["intent", "route"])


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
