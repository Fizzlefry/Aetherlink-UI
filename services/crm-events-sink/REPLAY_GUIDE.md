# CRM Events Sink - Replay & DLQ Guide

## Overview
The CRM Events Sink now includes HTTP API endpoints for event replay and dead letter queue (DLQ) management. This enables operators to recover from failures and re-process events.

## API Endpoints

### Base URL
- **Metrics**: `http://localhost:9105` (Prometheus)
- **API**: `http://localhost:9106` (FastAPI)

### Health Check
```bash
curl http://localhost:9106/health
```

### List Latest Events
```bash
# Get last 20 events (default)
curl http://localhost:9106/events/latest

# Get last 50 events
curl http://localhost:9106/events/latest?limit=50
```

**Response:**
```json
[
  {
    "id": 7,
    "tenant_id": "acme",
    "topic": "apexflow.jobs.created",
    "received_at": "2025-11-03T20:03:58.586440+00:00"
  },
  ...
]
```

### Replay Event
Republishes a single event from the journal back to its original Kafka topic.

```bash
# PowerShell
Invoke-RestMethod -Method POST -Uri http://localhost:9106/replay/5

# Bash
curl -X POST http://localhost:9106/replay/5
```

**Response:**
```json
{
  "status": "replayed",
  "event_id": 5,
  "topic": "apexflow.leads.created",
  "tenant_id": "acme"
}
```

**Important:** Replayed events will be re-consumed by the sink and re-persisted, creating duplicates in the journal. This is intentional for audit trails.

### Check Dead Letter Queue
```bash
curl http://localhost:9106/dlq
```

**Response:**
```json
[
  {
    "id": 1,
    "topic": "apexflow.leads.created",
    "error": "psycopg2.IntegrityError: duplicate key value",
    "received_at": "2025-11-03T20:15:00.123456+00:00"
  }
]
```

## Use Cases

### 1. Replay Failed Events
If events were lost due to downstream service outages:

```bash
# 1. Find the missing event IDs
curl http://localhost:9106/events/latest?limit=100

# 2. Replay each event
Invoke-RestMethod -Method POST -Uri http://localhost:9106/replay/42
Invoke-RestMethod -Method POST -Uri http://localhost:9106/replay/43
```

### 2. Reprocess Events for New Consumer
When adding a new consumer service that needs historical events:

```sql
-- Get event IDs for a specific time range
SELECT id FROM event_journal
WHERE received_at >= '2025-11-03 00:00:00'
ORDER BY id;
```

Then replay each event via the API.

### 3. Check for Processing Errors
```bash
# Check DLQ for failed persistence attempts
curl http://localhost:9106/dlq

# If DLQ has entries, investigate the error messages
# Then replay from journal after fixing the issue
```

### 4. Monitor Replay Activity
Replayed events appear in Prometheus metrics:

```bash
curl http://localhost:9105/metrics | Select-String 'crm_events_ingested_total'
```

Each replay increments both `crm_events_ingested_total` and `crm_events_persisted_total`.

## Database Queries

### Find Events by Tenant
```sql
SELECT id, topic, payload->>'name', received_at
FROM event_journal
WHERE tenant_id = 'acme'
ORDER BY received_at DESC;
```

### Find Events by Topic
```sql
SELECT id, tenant_id, payload, received_at
FROM event_journal
WHERE topic = 'apexflow.leads.created'
ORDER BY received_at DESC
LIMIT 20;
```

### Check for DLQ Entries
```sql
SELECT * FROM event_dlq
ORDER BY received_at DESC;
```

## Architecture Notes

### Replay Flow
```
Operator → HTTP POST /replay/{id}
       ↓
   event_journal (SELECT payload)
       ↓
   Kafka Producer (send to original topic)
       ↓
   Kafka Consumer (re-ingests event)
       ↓
   event_journal (INSERT duplicate)
```

This creates an intentional feedback loop where replayed events are re-persisted for audit purposes.

### DLQ Behavior
- Triggered when `persist_event()` throws an exception
- Original payload preserved in `event_dlq.payload` (JSONB)
- Error message captured in `event_dlq.error`
- Consumer continues processing (does not crash)
- Manual intervention required to replay from DLQ

## Port Reference
- **9105**: Prometheus metrics (`/metrics`)
- **9106**: HTTP API (`/health`, `/events/latest`, `/replay/{id}`, `/dlq`)

## Testing

### Test Replay End-to-End
```bash
# 1. Start a Kafka consumer in background
docker exec kafka rpk topic consume apexflow.leads.created --num 1 --offset end --format json

# 2. Replay an event
Invoke-RestMethod -Method POST -Uri http://localhost:9106/replay/5

# 3. Verify the consumer received it
# (Check the consumer output)

# 4. Verify metrics incremented
curl http://localhost:9105/metrics | Select-String 'crm_events_ingested_total'
```

### Simulate DLQ Entry
```sql
-- Temporarily break persistence (e.g., add a constraint)
ALTER TABLE event_journal ADD CONSTRAINT test_constraint CHECK (false);

-- Create a new event in ApexFlow
-- It will fail to persist and go to DLQ

-- Check DLQ
curl http://localhost:9106/dlq

-- Fix the issue
ALTER TABLE event_journal DROP CONSTRAINT test_constraint;

-- Replay from journal or create new events
```

## Monitoring & Alerts

### Prometheus Queries
```promql
# Replay rate (events re-ingested)
rate(crm_events_ingested_total[5m])

# DLQ size (requires custom metric)
# Currently: Query database directly
```

### Grafana Dashboard
Add panels:
- **DLQ Size**: `SELECT COUNT(*) FROM event_dlq`
- **Replay Activity**: Track spikes in `crm_events_ingested_total`
- **Persistence Success Rate**: `crm_events_persisted_total / crm_events_ingested_total`

## Security Notes
- No authentication on HTTP API (assumes internal network)
- No rate limiting on replay endpoint
- Consider adding:
  - Basic auth headers
  - Rate limiting (e.g., max 10 replays/minute)
  - Tenant-scoped replay (restrict by JWT tenant_id)

## Future Enhancements
- Batch replay: `POST /replay/batch` with event ID array
- DLQ replay: `POST /dlq/{id}/retry` to replay from DLQ table
- Event filtering: `GET /events?tenant_id=acme&topic=leads`
- Replay by time range: `POST /replay/range?start=...&end=...`
