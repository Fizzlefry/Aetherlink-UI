"""
CRM Events → SSE Microservice
Consumes Kafka topic aetherlink.events and exposes SSE endpoint for Command Center
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "aetherlink.events")
KAFKA_GROUP = os.getenv("KAFKA_GROUP", "crm-events-sse")

app = FastAPI(title="CRM Events → SSE", version="1.0.0")

# Prometheus metrics
SSE_CLIENTS = Gauge("crm_events_sse_clients", "Current SSE clients connected")
SSE_MESSAGES = Counter("crm_events_messages_total", "SSE messages relayed")
REQUESTS = Counter("crm_events_http_requests_total", "HTTP requests", ["path", "method"])


@app.middleware("http")
async def metrics_middleware(request, call_next):
    REQUESTS.labels(path=request.url.path, method=request.method).inc()
    return await call_next(request)


# Startup logging for debugging
@app.on_event("startup")
async def startup_event():
    print("🚀 CRM Events SSE Service starting...")
    print(f"   Kafka Brokers: {KAFKA_BROKERS}")
    print(f"   Kafka Topic: {TOPIC}")
    print(f"   Consumer Group: {KAFKA_GROUP}")


# Enable CORS for Command Center
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def event_stream() -> AsyncGenerator[bytes, None]:
    """
    Stream domain events from Kafka as Server-Sent Events
    """
    # Use 'earliest' in dev to see historical events, 'latest' in prod
    offset_reset = os.getenv("KAFKA_OFFSET_RESET", "earliest")

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKERS,
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset=offset_reset,
        group_id=KAFKA_GROUP,
    )

    await consumer.start()

    try:
        # Send initial connection event
        yield f"data: {json.dumps({'kind': 'connected', 'topic': TOPIC, 'group': KAFKA_GROUP})}\n\n".encode()
        SSE_MESSAGES.inc()

        async for msg in consumer:
            # Forward Kafka message as SSE event
            event_data = {
                "kind": "domain_event",
                "topic": msg.topic,
                "partition": msg.partition,
                "offset": msg.offset,
                "timestamp": msg.timestamp,
                "key": msg.key.decode("utf-8") if msg.key else None,
                "value": msg.value,
            }
            data = json.dumps(event_data)
            yield f"data: {data}\n\n".encode()
            SSE_MESSAGES.inc()

    except asyncio.CancelledError:
        # Client disconnected
        pass
    finally:
        await consumer.stop()


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "ok": True,
        "service": "crm-events",
        "status": "ready",
        "kafka_brokers": KAFKA_BROKERS,
        "topic": TOPIC,
        "group": KAFKA_GROUP,
    }


@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check"""
    return {"ok": True}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/crm-events")
async def crm_events_sse():
    """
    Server-Sent Events endpoint for CRM domain events

    Usage from Command Center:
    ```javascript
    const es = new EventSource('/api/ops/crm-events');
    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      console.log(event);
    };
    ```
    """
    SSE_CLIENTS.inc()
    try:
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    finally:
        SSE_CLIENTS.dec()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9010)
