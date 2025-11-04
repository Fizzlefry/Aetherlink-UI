"""
CRM Events Sink - Consumes and materializes ApexFlow domain events.
Subscribes to Kafka topics, exposes metrics, and persists events to PostgreSQL.
"""

import json
import logging
import os
import threading
import time
from typing import Any

import psycopg2
import uvicorn
from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer, KafkaProducer
from prometheus_client import Counter, start_http_server

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("crm-events-sink")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
GROUP_ID = os.getenv("GROUP_ID", "crm-events-sink")
POSTGRES_DSN = os.getenv("POSTGRES_DSN")  # postgresql://user:pass@host:5432/db
PROM_PORT = int(os.getenv("PROM_PORT", "9105"))

TOPICS = [
    "apexflow.leads.created",
    "apexflow.leads.note_added",
    "apexflow.leads.status_changed",
    "apexflow.leads.assigned",
    "apexflow.jobs.created",
]

# FastAPI app for operator endpoints
app = FastAPI(title="CRM Events Sink API", version="1.0.0")

# Global references (set in main())
GLOBAL_PG_CONN = None
GLOBAL_KAFKA_PRODUCER = None

# Prometheus metrics
events_ingested = Counter(
    "crm_events_ingested_total",
    "CRM domain events ingested from Kafka",
    ["topic", "tenant_id"],
)

events_persisted = Counter(
    "crm_events_persisted_total",
    "CRM domain events persisted to PostgreSQL",
    ["topic", "tenant_id"],
)


def get_pg_conn() -> psycopg2.extensions.connection | None:
    """Create PostgreSQL connection."""
    if not POSTGRES_DSN:
        return None
    return psycopg2.connect(POSTGRES_DSN)


def get_kafka_producer() -> KafkaProducer:
    """Create Kafka producer for replay."""
    return KafkaProducer(
        bootstrap_servers=[KAFKA_BOOTSTRAP],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def persist_event(
    conn: psycopg2.extensions.connection | None,
    tenant_id: str,
    topic: str,
    payload: dict[str, Any],
    replay_count: int = 0,
    replay_source: str | None = None,
) -> bool:
    """Persist event to PostgreSQL event_journal table."""
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_journal (tenant_id, topic, payload, replay_count, replay_source)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (tenant_id, topic, json.dumps(payload), replay_count, replay_source),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to persist event: {e}")
        conn.rollback()
        return False


def handle_event(conn: psycopg2.extensions.connection | None, topic: str, payload: dict[str, Any]):
    """Handle incoming event - increment metrics, log, and persist."""
    tenant_id = payload.get("tenant_id", "unknown")
    event_type = payload.get("event_type", "unknown")

    # Check if this is a replayed event
    is_replay = "_replayed_from_event_id" in payload
    replay_count = 1 if is_replay else 0
    replay_source = payload.get("_replay_source") if is_replay else None

    # 1. Increment ingestion metric
    events_ingested.labels(topic=topic, tenant_id=tenant_id).inc()

    # 2. Persist to database
    try:
        if persist_event(conn, tenant_id, topic, payload, replay_count, replay_source):
            events_persisted.labels(topic=topic, tenant_id=tenant_id).inc()
            if is_replay:
                logger.info(
                    f"Persisted REPLAYED {event_type} for tenant {tenant_id} (from event {payload['_replayed_from_event_id']})"
                )
            else:
                logger.info(f"Persisted {event_type} for tenant {tenant_id}")
        else:
            logger.warning(f"Failed to persist {event_type} for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Failed to persist event: {e}")
        # Insert into DLQ
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO event_dlq (topic, payload, error)
                        VALUES (%s, %s, %s)
                        """,
                        (topic, json.dumps(payload), str(e)),
                    )
                conn.commit()
                logger.info(f"Event sent to DLQ: {topic}")
            except Exception as dlq_error:
                logger.error(f"Also failed to write to DLQ: {dlq_error}")


# ============================================================================
# HTTP API Endpoints (for operators)
# ============================================================================


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "crm-events-sink"}


@app.get("/events/latest")
def latest_events(limit: int = 20):
    """List latest events from the journal."""
    if GLOBAL_PG_CONN is None:
        raise HTTPException(status_code=500, detail="Database not ready")

    try:
        with GLOBAL_PG_CONN.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, topic, received_at
                FROM event_journal
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "tenant_id": r[1],
                "topic": r[2],
                "received_at": r[3].isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.post("/replay/{event_id}")
def replay_event(event_id: int):
    """Replay a single event from the journal back to Kafka."""
    if GLOBAL_PG_CONN is None:
        raise HTTPException(status_code=500, detail="Database not ready")
    if GLOBAL_KAFKA_PRODUCER is None:
        raise HTTPException(status_code=500, detail="Kafka producer not ready")

    try:
        with GLOBAL_PG_CONN.cursor() as cur:
            cur.execute(
                "SELECT topic, payload FROM event_journal WHERE id = %s",
                (event_id,),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Event not found")

        topic, payload_json = row
        # payload_json is already a dict (psycopg2 auto-deserializes JSONB)
        if isinstance(payload_json, str):
            payload = json.loads(payload_json)
        else:
            payload = payload_json

        # Mark as replayed for tracking
        payload["_replayed_from_event_id"] = event_id
        payload["_replay_source"] = "operator_api"

        # Re-publish to Kafka
        GLOBAL_KAFKA_PRODUCER.send(topic, payload)
        GLOBAL_KAFKA_PRODUCER.flush(timeout=3)

        logger.info(f"Replayed event {event_id} to topic {topic}")
        return {
            "status": "replayed",
            "event_id": event_id,
            "topic": topic,
            "tenant_id": payload.get("tenant_id", "unknown"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay failed: {str(e)}")


@app.get("/dlq")
def get_dlq(limit: int = 20):
    """List events in the dead letter queue."""
    if GLOBAL_PG_CONN is None:
        raise HTTPException(status_code=500, detail="Database not ready")

    try:
        with GLOBAL_PG_CONN.cursor() as cur:
            cur.execute(
                """
                SELECT id, topic, error, received_at
                FROM event_dlq
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "topic": r[1],
                "error": r[2],
                "received_at": r[3].isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


def main():
    """Main consumer loop."""
    global GLOBAL_PG_CONN, GLOBAL_KAFKA_PRODUCER

    # Start Prometheus metrics server
    start_http_server(PROM_PORT)
    logger.info(f"Prometheus metrics server started on :{PROM_PORT}")

    # Connect to PostgreSQL with retry
    pg_conn = None
    if POSTGRES_DSN:
        for attempt in range(5):
            try:
                pg_conn = get_pg_conn()
                logger.info("Connected to PostgreSQL for event persistence")
                break
            except Exception as e:
                logger.warning(f"PostgreSQL not ready yet (attempt {attempt + 1}/5): {e}")
                time.sleep(3)

        if pg_conn is None:
            logger.error("Failed to connect to PostgreSQL after 5 attempts")
    else:
        logger.warning("No POSTGRES_DSN provided - events will not be persisted")

    # Set global references for HTTP API
    GLOBAL_PG_CONN = pg_conn
    if pg_conn:
        try:
            GLOBAL_KAFKA_PRODUCER = get_kafka_producer()
            logger.info("Kafka producer created for replay functionality")
        except Exception as e:
            logger.warning(f"Failed to create Kafka producer: {e}")

    # Start FastAPI server in background thread
    def run_api():
        uvicorn.run(app, host="0.0.0.0", port=9106, log_level="info")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("HTTP API started on :9106")

    # Wait a bit for Kafka to be ready
    time.sleep(3)

    # Create Kafka consumer
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=[KAFKA_BOOTSTRAP],
        group_id=GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )

    logger.info(f"CRM Events Sink started. Listening to topics: {TOPICS}")

    for msg in consumer:
        try:
            handle_event(pg_conn, msg.topic, msg.value)
        except Exception as e:
            logger.error(f"Failed to handle event from {msg.topic}: {e}")
            # Try to reconnect to PostgreSQL if connection was lost
            if pg_conn and POSTGRES_DSN:
                try:
                    pg_conn = get_pg_conn()
                    logger.info("Reconnected to PostgreSQL")
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect to PostgreSQL: {reconnect_error}")


if __name__ == "__main__":
    main()
