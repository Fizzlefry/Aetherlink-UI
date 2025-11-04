# CRM Events Sink - Operator Quick Reference

## 🛠 Quick Actions

### 1. Check Sink Health
```bash
curl http://localhost:9106/health
```
**Expected**: `{"status":"healthy","service":"crm-events-sink"}`

---

### 2. See Latest Events in Journal
```bash
curl http://localhost:9106/events/latest?limit=20
```
**Use this** to grab the `id` you want to replay.

**Example Response**:
```json
[
  {"id": 42, "tenant_id": "acme", "topic": "apexflow.leads.created", "received_at": "2025-11-03T20:03:58+00:00"},
  {"id": 41, "tenant_id": "acme", "topic": "apexflow.jobs.created", "received_at": "2025-11-03T20:02:15+00:00"}
]
```

---

### 3. Replay Event Back to Kafka
```bash
# Replace 42 with the event_id from /events/latest
curl -X POST http://localhost:9106/replay/42
```

**PowerShell**:
```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:9106/replay/42
```

**Expected**: `{"status":"replayed","event_id":42,"topic":"apexflow.leads.created","tenant_id":"acme"}`

Within **1-2 seconds**, the event will be re-ingested and show up in Prometheus metrics.

---

### 4. Verify Metrics Increased
```bash
curl http://localhost:9105/metrics | grep crm_events_ | head -n 20
```

**PowerShell**:
```powershell
(Invoke-WebRequest http://localhost:9105/metrics).Content | Select-String 'crm_events_'
```

**Look for**:
- `crm_events_ingested_total{tenant_id="acme",topic="apexflow.leads.created"}` ← should increment
- `crm_events_persisted_total{tenant_id="acme",topic="apexflow.leads.created"}` ← should increment

---

### 5. Check DB Counts (Optional / Deeper)
```bash
docker exec aether-crm-events-db \
  psql -U crm_events -d crm_events \
  -c "SELECT topic, COUNT(*) AS events FROM event_journal GROUP BY topic ORDER BY topic;"
```

**PowerShell**:
```powershell
docker exec aether-crm-events-db psql -U crm_events -d crm_events -c "SELECT topic, COUNT(*) AS events FROM event_journal GROUP BY topic ORDER BY topic;"
```

Counts should match what Prometheus is telling you.

---

## 🧯 Dead Letter Queue (DLQ)

If the sink can't write an event to Postgres (schema change, bad JSON, network blip), it lands in DLQ.

### 1. View DLQ via API
```bash
curl http://localhost:9106/dlq
```

**PowerShell**:
```powershell
curl http://localhost:9106/dlq | ConvertFrom-Json
```

---

### 2. View DLQ in Database (Deeper)
```bash
docker exec aether-crm-events-db \
  psql -U crm_events -d crm_events \
  -c "SELECT id, topic, received_at, left(error,120) AS error FROM event_dlq ORDER BY id DESC LIMIT 20;"
```

---

### 3. Typical Op Flow

1. **Check DLQ**: `curl http://localhost:9106/dlq`
2. **Fix root cause**: Schema issue? Sink logic bug? Network blip?
3. **Replay original from journal**: `curl -X POST http://localhost:9106/replay/{id}`

**Remember**: DLQ is the symptom log — `event_journal` is the source of truth.

---

## 📈 Grafana / Alerts

### Dashboard: **CRM Events Pipeline**
- **URL**: `http://localhost:3000` (Grafana)
- **Panels**:
  - **Panel 20**: CRM Events Ingested (by topic)
  - **Panel 21**: Top Tenants by CRM Events (5m)
  - **Panel 22**: Persisted vs Ingested

### Alert: **CrmEventsPersistenceStalled**
- **Fires if**: `ingested > 0` but `persisted == 0` for 10m
- **Translation**: "We're reading from Kafka but not writing to DB"
- **Action**: Check sink logs, verify Postgres connection

---

## 🧠 Mental Model for the Team

| Component | Purpose |
|-----------|---------|
| **Kafka** | "Live stream right now" |
| **Postgres `event_journal`** | "Everything that ever happened" |
| **`POST /replay/{id}`** | "Send that old thing back onto the live stream" |
| **DLQ** | "Things we couldn't store, please look" |

This is exactly how mature event platforms operate.

---

## 🔍 Common Scenarios

### Scenario 1: Replay Missing Events
**Problem**: Downstream consumer was down for 1 hour, missed 150 events.

**Solution**:
```bash
# 1. Find event IDs in the time range
curl http://localhost:9106/events/latest?limit=200

# 2. Replay each (or script it)
for id in {42..192}; do
  curl -X POST http://localhost:9106/replay/$id
  sleep 0.1
done
```

---

### Scenario 2: Debug Event Processing
**Problem**: Downstream service is crashing on a specific event.

**Solution**:
```bash
# 1. List recent events
curl http://localhost:9106/events/latest

# 2. Replay the suspicious event
curl -X POST http://localhost:9106/replay/42

# 3. Watch downstream logs
docker logs aether-downstream-consumer --follow
```

---

### Scenario 3: New Consumer Onboarding
**Problem**: New analytics consumer needs last 7 days of events.

**Solution**:
```sql
-- 1. Get event IDs from last 7 days
SELECT id FROM event_journal
WHERE received_at >= NOW() - INTERVAL '7 days'
ORDER BY id;

-- 2. Replay via API (can be scripted)
```

---

### Scenario 4: Check DLQ After Schema Change
**Problem**: You just deployed a schema change, want to verify no failures.

**Solution**:
```bash
# Check if any events landed in DLQ
curl http://localhost:9106/dlq

# If DLQ is empty: ✅ All good
# If DLQ has entries: ❌ Investigate error messages
```

---

## 🚨 Troubleshooting

### Issue: Replay Not Working
```bash
# 1. Check sink logs
docker logs aether-crm-events-sink --tail 50

# 2. Verify Kafka producer is connected
curl http://localhost:9106/health

# 3. Check Kafka broker health
docker exec kafka rpk cluster info
```

---

### Issue: Metrics Not Updating
```bash
# 1. Verify Prometheus is scraping
curl http://localhost:9105/metrics

# 2. Check Prometheus targets
# Open: http://localhost:9090/targets

# 3. Verify sink consumer is running
docker logs aether-crm-events-sink --tail 20
```

---

### Issue: DLQ Growing
```bash
# 1. Check recent errors
curl http://localhost:9106/dlq

# 2. View database errors
docker exec aether-crm-events-db \
  psql -U crm_events -d crm_events \
  -c "SELECT error, COUNT(*) FROM event_dlq GROUP BY error ORDER BY COUNT(*) DESC;"

# 3. Common causes:
#    - Schema mismatch (missing columns)
#    - Network interruption to Postgres
#    - Disk full on database
```

---

## 📞 Port Reference

| Port | Service | Endpoint |
|------|---------|----------|
| **9105** | Prometheus Metrics | `GET /metrics` |
| **9106** | HTTP API | `GET /health`, `GET /events/latest`, `POST /replay/{id}`, `GET /dlq` |
| **5446** | PostgreSQL | `crm_events` database |
| **9092** | Kafka | Event broker |

---

## 🎯 Key Takeaways

1. **Replay creates duplicates** - This is intentional for audit trails
2. **Metrics track everything** - Both original and replayed events increment counters
3. **DLQ is append-only** - Never auto-deletes, manual cleanup only
4. **Journal is source of truth** - Always replay from `event_journal`, not DLQ
5. **No authentication** - Assumes internal network, add auth for production

---

## 📚 Related Documentation

- **Full Replay Guide**: `services/crm-events-sink/REPLAY_GUIDE.md`
- **Implementation Summary**: `services/crm-events-sink/PHASE5_PLUS_SUMMARY.md`
- **Database Schema**: `services/crm-events-sink/sql/001_event_journal.sql`, `002_event_dlq.sql`
