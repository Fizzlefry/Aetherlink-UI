# Aetherlink Ship Pack — Complete Implementation Guide

**Deliverables**: Grafana Dashboard, Kafka Consumer SSE, EF Core Migrations
**Status**: ✅ Ready to Deploy
**Date**: November 2, 2025

---

## 📦 What's Included

This ship pack includes three production-ready components:

### 1. **Grafana Dashboard** — `autoheal_oidc_error_budget.json`
- **4 SLO panels**: Heartbeat age, Failure rate, Availability, Audit latency
- **Error budget burn alerts**: Fast (14.4x) and Slow (2.4x) burn visualization
- **Alert status table**: Shows firing burn alerts
- **Auto-refresh**: 10-second refresh interval

### 2. **Kafka Consumer → SSE** — `pods/crm-events`
- **FastAPI microservice**: Consumes `aetherlink.events` Kafka topic
- **Server-Sent Events**: Exposes `/crm-events` endpoint for real-time streaming
- **Event enrichment**: Includes topic, partition, offset, timestamp metadata
- **CORS enabled**: Ready for Command Center consumption

### 3. **EF Core Tables** — Outbox + Idempotency
- **OutboxEvent entity**: Transactional event publishing to Kafka
- **IdempotencyKey entity**: Duplicate webhook/command prevention
- **Migration**: `20251102_Init_Outbox_Idempotency.cs`
- **Background service**: `OutboxPublisher.cs` polls and publishes events

---

## 🚀 Quick Deploy

### One-Command Deployment

```powershell
cd C:\Users\jonmi\OneDrive\Documents\AetherLink
.\monitoring\scripts\deploy-ship-pack.ps1
```

This script will:
1. ✅ Create Kafka topic `aetherlink.events` (3 partitions)
2. ✅ Apply EF Core migration (outbox_events, idempotency_keys tables)
3. ✅ Build and start `crm-events` service
4. ℹ️ Display Grafana import instructions

**Selective deployment**:
```powershell
# Skip Kafka topic creation
.\monitoring\scripts\deploy-ship-pack.ps1 -SkipKafka

# Skip EF migration
.\monitoring\scripts\deploy-ship-pack.ps1 -SkipMigration

# Skip service startup
.\monitoring\scripts\deploy-ship-pack.ps1 -SkipService
```

---

## 📊 Component 1: Grafana Dashboard

### File Location
```
monitoring/grafana/dashboards/autoheal_oidc_error_budget.json
```

### Import Steps

1. **Open Grafana**: http://localhost:3000
2. **Navigate**: Dashboards → Import
3. **Upload JSON**: Select `autoheal_oidc_error_budget.json`
4. **Select Data Source**: Choose "Prometheus"
5. **Click Import**

### Dashboard Panels

| Panel | Metric | Threshold | Description |
|-------|--------|-----------|-------------|
| **SLO-1** | `autoheal:heartbeat:age_seconds` | <300s | Heartbeat freshness |
| **SLO-2** | `autoheal:action_fail_rate_15m` | <0.1% | Action failure rate |
| **SLO-3** | `avg_over_time(up{job="autoheal"}[5m])` | >99.9% | Service availability |
| **SLO-4** | `histogram_quantile(0.95, rate(autoheal_audit_write_seconds_bucket[5m]))` | <100ms | Audit write latency p95 |
| **Fast Burn** | `(sum(rate(...[5m])) / (300 * 0.999))` | >14.4x | 5% monthly budget in 1h |
| **Slow Burn** | `(sum(rate(...[1h])) / (300 * 0.999))` | >2.4x | 10% monthly budget in 6h |

### Expected Metrics

After Autoheal rebuild (with OpenTelemetry + Chaos):
- ✅ `autoheal:heartbeat:age_seconds` (recording rule)
- ✅ `autoheal:action_fail_rate_15m` (recording rule)
- ✅ `up{job="autoheal"}` (Prometheus scrape)
- ⏳ `autoheal_audit_write_seconds_bucket` (requires rebuild)

### Validation

```powershell
# Check if SLO metrics are available
curl http://localhost:9090/api/v1/query?query=autoheal:heartbeat:age_seconds

# Verify burn alerts loaded
$rules = Invoke-RestMethod 'http://localhost:9090/api/v1/rules'
$rules.data.groups.rules | Where-Object { $_.alert -like "*Burn*" } | Select-Object alert
```

---

## 📨 Component 2: Kafka Consumer SSE

### Architecture

```
Kafka (aetherlink.events)
  ↓
CRM Events Service (FastAPI + aiokafka)
  ↓ SSE
Command Center (Next.js EventSource)
  ↓
Real-time event display
```

### Service Files

```
pods/crm-events/
├── main.py              # FastAPI app with SSE endpoint
├── requirements.txt     # fastapi, uvicorn, aiokafka
└── Dockerfile           # Python 3.11 slim
```

### Configuration

**Environment Variables** (in `monitoring/docker-compose.yml`):
```yaml
environment:
  - KAFKA_BROKERS=kafka:9092
  - KAFKA_TOPIC=aetherlink.events
  - KAFKA_GROUP=crm-events-sse
```

### API Endpoints

#### `GET /`
Health check endpoint.

**Response**:
```json
{
  "service": "crm-events",
  "status": "ok",
  "kafka_brokers": "kafka:9092",
  "topic": "aetherlink.events",
  "group": "crm-events-sse"
}
```

#### `GET /crm-events`
Server-Sent Events stream.

**Headers**:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`

**Event Format**:
```json
{
  "kind": "domain_event",
  "topic": "aetherlink.events",
  "partition": 0,
  "offset": 1234,
  "timestamp": 1730592000000,
  "key": "JobCreated",
  "value": {
    "Type": "JobCreated",
    "TenantId": "12345678-1234-1234-1234-123456789012",
    "JobId": "...",
    "Title": "New Installation",
    "Status": "Open"
  }
}
```

### Deployment

```powershell
# Build and start service
cd monitoring
docker compose build crm-events
docker compose up -d crm-events

# Check logs
docker logs aether-crm-events --tail 50

# Health check
curl http://localhost:9010/

# Test SSE connection (PowerShell)
$wc = New-Object System.Net.WebClient
$stream = $wc.OpenRead("http://localhost:9010/crm-events")
$reader = New-Object System.IO.StreamReader($stream)
while ($true) { $reader.ReadLine() }
```

### Next.js Integration

**API Proxy** (`apps/command-center/app/api/ops/crm-events/route.ts`):
```typescript
export async function GET(request: Request) {
  const CRM_EVENTS_URL = process.env.CRM_EVENTS_URL || 'http://localhost:9010/crm-events';
  const response = await fetch(CRM_EVENTS_URL, {
    method: 'GET',
    headers: { 'Accept': 'text/event-stream' },
  });
  return new Response(response.body, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}
```

**React Component** (`apps/command-center/app/ops/crm-events/page.tsx`):
```typescript
const es = new EventSource('/api/ops/crm-events');
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  setEvents((prev) => [event, ...prev].slice(0, 500));
};
```

**Features**:
- ✅ Live event stream (last 500 events)
- ✅ Color-coded by event type (Created=green, Updated=yellow, Deleted=red)
- ✅ Real-time filter
- ✅ Status indicator (connecting/live/down)
- ✅ Metadata display (topic, partition, offset, timestamp)

---

## 🗄️ Component 3: EF Core Migrations

### Entity Models

#### `OutboxEvent.cs`
```csharp
public class OutboxEvent {
    public long Id { get; set; }
    public Guid TenantId { get; set; }
    public string Type { get; set; }        // "JobCreated", "ContactCreated"
    public string Payload { get; set; }     // JSON
    public DateTimeOffset OccurredAt { get; set; }
    public DateTimeOffset? PublishedAt { get; set; }
    public int RetryCount { get; set; }
    public string? LastError { get; set; }
}
```

#### `IdempotencyKey.cs`
```csharp
public class IdempotencyKey {
    public long Id { get; set; }
    public Guid TenantId { get; set; }
    public string Key { get; set; }         // UUID from header
    public string RequestPath { get; set; }
    public string RequestMethod { get; set; }
    public int StatusCode { get; set; }
    public string? ResponseBody { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime ExpiresAt { get; set; } // CreatedAt + 24h
}
```

### Database Schema

**Table**: `outbox_events`
```sql
CREATE TABLE outbox_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    type VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IX_outbox_events_published_occurred ON outbox_events (published_at, occurred_at);
CREATE INDEX IX_outbox_events_tenant ON outbox_events (tenant_id);
```

**Table**: `idempotency_keys`
```sql
CREATE TABLE idempotency_keys (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    key VARCHAR(200) NOT NULL,
    request_path VARCHAR(500) NOT NULL,
    request_method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_body TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IX_idempotency_keys_tenant_key ON idempotency_keys (tenant_id, key);
CREATE INDEX IX_idempotency_keys_expires ON idempotency_keys (expires_at);
```

### Apply Migration

```bash
# Install EF Core tools (one-time)
dotnet tool install --global dotnet-ef

# Navigate to PeakPro project
cd peakpro

# Apply migration
dotnet ef database update

# Verify tables created
docker exec postgres-crm psql -U crm -d crm -c "\dt"
```

**Expected output**:
```
List of relations
 Schema |       Name        | Type  | Owner
--------+-------------------+-------+-------
 public | outbox_events     | table | crm
 public | idempotency_keys  | table | crm
```

### Background Publisher

**File**: `peakpro/Infrastructure/Outbox/OutboxPublisher.cs`

**Features**:
- ✅ Polls `outbox_events` every 5 seconds (configurable)
- ✅ Publishes up to 100 events per batch
- ✅ Kafka idempotence: `acks=all`, `enable.idempotence=true`
- ✅ Retry logic: Up to 5 retries, marks as failed after
- ✅ Error logging with last error stored in database

**Configuration** (in `appsettings.json`):
```json
{
  "Kafka": {
    "Brokers": "kafka:9092",
    "OutboxTopic": "aetherlink.events",
    "PollIntervalSeconds": 5,
    "BatchSize": 100,
    "MaxRetries": 5
  }
}
```

**Register in `Program.cs`**:
```csharp
// Add DbContext
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("CrmDb")));

// Register background service
builder.Services.AddHostedService<OutboxPublisher>();
```

---

## 🧪 End-to-End Testing

### Test Scenario: Job Created Event

**1. Create a job via API**:
```bash
curl -X POST http://localhost:8080/api/crm/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000' \
  -H 'X-Tenant-Id: 12345678-1234-1234-1234-123456789012' \
  -d '{
    "accountId": "...",
    "title": "Test Job",
    "status": "Open"
  }'
```

**2. Check outbox table**:
```bash
docker exec postgres-crm psql -U crm -d crm -c \
  "SELECT id, type, occurred_at, published_at FROM outbox_events ORDER BY occurred_at DESC LIMIT 5;"
```

**Expected**:
```
 id |    type     |      occurred_at       |       published_at
----+-------------+------------------------+------------------------
  1 | JobCreated  | 2025-11-02 10:30:00+00 | 2025-11-02 10:30:05+00
```

**3. Check Kafka topic**:
```bash
docker exec kafka rpk topic consume aetherlink.events --format '%v\n' --num 1
```

**Expected**:
```json
{
  "Type": "JobCreated",
  "TenantId": "12345678-1234-1234-1234-123456789012",
  "JobId": "...",
  "Title": "Test Job",
  "Status": "Open",
  "Ts": "2025-11-02T10:30:00Z"
}
```

**4. Check Command Center**:
- Open http://localhost:3001/ops/crm-events
- See event appear in real-time with green background (Created event)
- Metadata shows: `aetherlink.events:0@1234`

**5. Test idempotency**:
```bash
# Send same request again (same Idempotency-Key)
curl -X POST http://localhost:8080/api/crm/jobs \
  -H 'Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000' \
  # ... same payload
```

**Expected**: HTTP 202 Accepted (cached response, no duplicate event)

---

## 📋 Validation Checklist

### Grafana Dashboard
- [ ] Dashboard imported successfully
- [ ] All 4 SLO panels show data
- [ ] Burn rate panels show thresholds (14.4x, 2.4x)
- [ ] Alert status table shows no firing alerts (normal state)

### CRM Events Service
- [ ] Service running: `docker ps | grep crm-events`
- [ ] Health check passes: `curl http://localhost:9010/`
- [ ] SSE connection works: `curl http://localhost:9010/crm-events`
- [ ] No errors in logs: `docker logs aether-crm-events`

### EF Core Migration
- [ ] Migration file exists: `peakpro/Migrations/20251102_Init_Outbox_Idempotency.cs`
- [ ] Migration applied: `dotnet ef migrations list` shows `Init_Outbox_Idempotency (Applied)`
- [ ] Tables exist: `psql` shows `outbox_events`, `idempotency_keys`
- [ ] Indexes created: `\di` shows 5 indexes

### Kafka Topic
- [ ] Topic exists: `rpk topic list` shows `aetherlink.events`
- [ ] 3 partitions: `rpk topic describe aetherlink.events`
- [ ] Can produce: `echo '{"test": true}' | rpk topic produce aetherlink.events`
- [ ] Can consume: `rpk topic consume aetherlink.events --num 1`

### Next.js Integration
- [ ] API proxy works: `curl http://localhost:3001/api/ops/crm-events`
- [ ] Page loads: http://localhost:3001/ops/crm-events
- [ ] Status shows "live" (green dot)
- [ ] Events appear in real-time when triggered

---

## 🐛 Troubleshooting

### Issue: Kafka topic creation fails
**Symptoms**: `rpk topic create` returns error
**Cause**: Kafka not running
**Fix**:
```powershell
docker ps | grep kafka  # Check if running
docker compose -f monitoring/docker-compose.yml up -d kafka
```

---

### Issue: EF migration fails
**Symptoms**: `dotnet ef database update` returns connection error
**Cause**: PostgreSQL not running or wrong connection string
**Fix**:
```powershell
docker ps | grep postgres-crm  # Check if running
docker logs postgres-crm  # Check for errors

# Test connection
docker exec postgres-crm psql -U crm -d crm -c "SELECT 1;"
```

---

### Issue: CRM Events service shows "down"
**Symptoms**: Status indicator is red
**Cause**: Service crashed or Kafka unreachable
**Fix**:
```powershell
docker logs aether-crm-events --tail 50  # Check for errors
docker compose -f monitoring/docker-compose.yml restart crm-events
```

---

### Issue: No events appear in Command Center
**Symptoms**: Page loads but shows "Waiting for events..."
**Cause**: No events in Kafka or consumer lag
**Fix**:
```powershell
# Check if events exist in Kafka
docker exec kafka rpk topic consume aetherlink.events --num 10

# Check consumer group lag
docker exec kafka rpk group describe crm-events-sse
```

---

### Issue: Grafana dashboard shows "No Data"
**Symptoms**: All panels show "No Data"
**Cause**: Prometheus not scraping or Autoheal not exposing metrics
**Fix**:
```powershell
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job == "autoheal")'

# Check Autoheal metrics
curl http://localhost:9009/metrics | Select-String "autoheal"
```

---

## 📚 References

- **Grafana Provisioning**: https://grafana.com/docs/grafana/latest/administration/provisioning/
- **FastAPI SSE**: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
- **EF Core Migrations**: https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/
- **Kafka Idempotence**: https://kafka.apache.org/documentation/#producerconfigs_enable.idempotence
- **Outbox Pattern**: https://microservices.io/patterns/data/transactional-outbox.html

---

## ✅ Success Criteria

**Ship Pack is complete when**:
1. ✅ Grafana dashboard shows all 4 SLOs with live data
2. ✅ Burn rate panels display fast/slow thresholds
3. ✅ CRM Events service health check passes
4. ✅ SSE endpoint streams events to Command Center
5. ✅ EF Core tables created with proper indexes
6. ✅ OutboxPublisher background service running
7. ✅ Kafka topic `aetherlink.events` has 3 partitions
8. ✅ End-to-end test: Job creation → outbox → Kafka → Command Center

---

**Deployment Status**: ✅ READY TO SHIP
**Validation Required**: Manual Grafana import + E2E test
**Next Steps**: Run `deploy-ship-pack.ps1`, import dashboard, trigger test event
