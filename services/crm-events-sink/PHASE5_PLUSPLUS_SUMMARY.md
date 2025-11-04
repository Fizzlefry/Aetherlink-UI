# Phase 5++ Complete: Replay Tracking Enhancement

## 🎯 Enhancement Overview

Added **replay tracking** to distinguish original events from replayed events in the event journal. This enables:
- **Analytics**: Separate original vs replayed event volumes
- **Audit trails**: Track which events were replayed and when
- **Grafana dashboards**: Visualize replay activity
- **Operational insights**: Monitor replay patterns and identify automation opportunities

---

## ✅ What Was Added

### 1. Database Schema Enhancement
**File**: `services/crm-events-sink/sql/003_replay_tracking.sql`

Added two columns to `event_journal`:
```sql
ALTER TABLE event_journal 
ADD COLUMN replay_count INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN replay_source TEXT DEFAULT NULL;
```

- **`replay_count`**: `0` = original event, `1` = replayed event
- **`replay_source`**: Tracks replay origin (`"operator_api"`, `"automated"`, etc.)
- **Index**: `idx_event_journal_replay_count` for efficient filtering

### 2. Payload Markers
**File**: `services/crm-events-sink/app/main.py` (replay_event function)

Replayed events now include metadata:
```python
payload["_replayed_from_event_id"] = event_id  # Original event ID
payload["_replay_source"] = "operator_api"     # Replay source
```

### 3. Enhanced Persistence
**File**: `services/crm-events-sink/app/main.py` (persist_event function)

```python
def persist_event(conn, tenant_id, topic, payload, replay_count=0, replay_source=None):
    # Stores replay_count and replay_source in database
```

### 4. Intelligent Detection
**File**: `services/crm-events-sink/app/main.py` (handle_event function)

```python
is_replay = "_replayed_from_event_id" in payload
replay_count = 1 if is_replay else 0
replay_source = payload.get("_replay_source") if is_replay else None
```

### 5. Enhanced Logging
Original events:
```
INFO - Persisted lead.created for tenant acme
```

Replayed events:
```
INFO - Persisted REPLAYED lead.created for tenant acme (from event 1)
```

---

## 📊 Verification Results

### Before Enhancement
```
Total Events: 11 (all original)
```

### After Enhancement
```
Original Events: 11
Replayed Events: 1

Replay Details:
ID: 12
Topic: apexflow.leads.created
Source: operator_api
Replayed From: Event #1
```

### Database Queries

**Count original vs replayed**:
```sql
SELECT 
  CASE WHEN replay_count = 0 THEN 'Original' ELSE 'Replayed' END AS type,
  COUNT(*) 
FROM event_journal 
GROUP BY type;
```

**Find all replays**:
```sql
SELECT 
  id, 
  topic, 
  replay_source, 
  payload->>'_replayed_from_event_id' as original_event_id
FROM event_journal 
WHERE replay_count > 0;
```

---

## 📈 Grafana Integration

### New Queries Available

1. **Original vs Replayed Events (Timeseries)**
   - Shows volume trends over time
   - Separate lines for original/replayed

2. **Replay Sources (Pie Chart)**
   - Distribution: operator_api, automated, etc.

3. **Replay Rate (Gauge)**
   - Percentage of events that are replays

4. **Recent Replay Events (Table)**
   - Shows last 20 replays with source event IDs

**Full documentation**: `services/crm-events-sink/GRAFANA_REPLAY_QUERIES.md`

---

## 🔍 Use Cases

### 1. Operational Analytics
**Question**: "How much of our event volume is organic vs replayed?"

**Query**:
```sql
SELECT 
  DATE(received_at),
  SUM(CASE WHEN replay_count = 0 THEN 1 ELSE 0 END) as original,
  SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) as replayed
FROM event_journal
GROUP BY DATE(received_at);
```

---

### 2. Audit Trail
**Question**: "What was replayed during the incident recovery?"

**Query**:
```sql
SELECT 
  id,
  topic,
  tenant_id,
  payload->>'_replayed_from_event_id' as source_event,
  received_at
FROM event_journal
WHERE 
  replay_count > 0 
  AND received_at BETWEEN '2025-11-03 14:00' AND '2025-11-03 15:00';
```

---

### 3. Replay Effectiveness
**Question**: "Did event #42 get successfully replayed?"

**Query**:
```sql
SELECT id, topic, received_at
FROM event_journal
WHERE payload->>'_replayed_from_event_id' = '42';
```

---

### 4. Automated vs Manual Replays
**Question**: "How many replays are manual vs automated?"

**Query**:
```sql
SELECT 
  replay_source,
  COUNT(*) 
FROM event_journal 
WHERE replay_count > 0
GROUP BY replay_source;
```

---

## 🗂️ Files Modified/Created

### Modified
1. `services/crm-events-sink/app/main.py`
   - Updated `persist_event()` signature with replay parameters
   - Added replay detection in `handle_event()`
   - Enhanced `replay_event()` to inject metadata
   - Improved logging for replayed events

### Created
1. `services/crm-events-sink/sql/003_replay_tracking.sql`
   - Schema migration for replay tracking columns
   
2. `services/crm-events-sink/GRAFANA_REPLAY_QUERIES.md`
   - Complete Grafana query reference
   - Dashboard layout examples
   - Alert configurations

3. `services/crm-events-sink/OPERATOR_QUICKREF.md`
   - Operator-facing quick reference
   - Common scenarios and solutions

---

## 🎯 Benefits

### Before (Phase 5)
- ✅ Events persisted
- ✅ Replay possible
- ❌ No way to distinguish replays from originals
- ❌ No audit trail for replay activity

### After (Phase 5++)
- ✅ Events persisted
- ✅ Replay possible
- ✅ **Clear distinction between original and replayed events**
- ✅ **Full audit trail with source tracking**
- ✅ **Grafana dashboards show replay activity**
- ✅ **Enhanced logging identifies replays**

---

## 🚀 Example Workflow

### Scenario: Recovering from 30-minute outage

1. **Identify missing events**:
   ```bash
   curl http://localhost:9106/events/latest?limit=100
   ```

2. **Replay affected range**:
   ```bash
   for id in {100..150}; do
     Invoke-RestMethod -Method POST -Uri "http://localhost:9106/replay/$id"
   done
   ```

3. **Verify in Grafana**:
   - Check "Original vs Replayed Events" panel
   - Should see spike in replayed events (green line)

4. **Audit in database**:
   ```sql
   SELECT 
     payload->>'_replayed_from_event_id' as source,
     COUNT(*) as replays
   FROM event_journal
   WHERE replay_count > 0 
     AND received_at > NOW() - INTERVAL '1 hour'
   GROUP BY source;
   ```

5. **Result**: Clear evidence of recovery operation in audit log

---

## 🔒 Data Integrity

### Replay Detection Logic
```python
# Automatic detection via payload markers
is_replay = "_replayed_from_event_id" in payload

# No manual flags to forget
# No race conditions
# Works across service restarts
```

### Immutable Audit Trail
- `replay_count` and `replay_source` set at insert time
- Never modified after persistence
- Full history preserved forever

### Source Event Linkage
- Original event ID preserved in payload
- Can trace replay lineage
- Supports forensic analysis

---

## 📊 Current System State

```
Event Journal:
├─ Original Events: 11
└─ Replayed Events: 1
   └─ Source: operator_api (from event #1)

Dead Letter Queue:
└─ Entries: 0 (all events processed successfully)

HTTP API:
├─ Health: ✅ Healthy
├─ Metrics: ✅ Exporting (port 9105)
└─ Endpoints: ✅ All operational (port 9106)

Database:
├─ Schema: ✅ v003 (with replay tracking)
├─ Indexes: ✅ 6 indexes (including replay_count)
└─ Size: 12 events (11 original + 1 replay)
```

---

## 🎓 Key Insights

### 1. Replay Tracking is Passive
- No operator action required
- Automatic detection via payload markers
- Works seamlessly with existing infrastructure

### 2. Backward Compatible
- Existing events automatically marked as `replay_count=0`
- No data migration needed
- Old consumers unaffected

### 3. Future-Proof
- `replay_source` field allows multiple sources
- Can add: `"automated"`, `"scheduled"`, `"webhook"`, etc.
- Extensible for future automation

### 4. Production-Ready
- Indexed for performance
- Logged for visibility
- Queryable in Grafana
- Auditable in database

---

## 🏆 Final Summary

**Phase 5++ is complete.** The event-driven platform now includes:

✅ Event publishing (ApexFlow → Kafka)  
✅ Event persistence (Sink → PostgreSQL)  
✅ Event metrics (Prometheus)  
✅ Event visualization (Grafana)  
✅ Event replay (HTTP API → Kafka)  
✅ Dead letter queue (Error capture)  
✅ **Replay tracking (Original vs Replayed)** ⭐ NEW  
✅ **Audit trail (Source tracking)** ⭐ NEW  
✅ **Enhanced observability (Grafana queries)** ⭐ NEW  

This is a **mature, production-grade, event-sourced platform** with:
- Full recovery capabilities
- Complete audit trails
- Operational visibility
- Self-service tooling

**The platform is now operator-friendly and audit-ready.** 🚀

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| `OPERATOR_QUICKREF.md` | Quick reference for daily operations |
| `REPLAY_GUIDE.md` | Comprehensive replay documentation |
| `GRAFANA_REPLAY_QUERIES.md` | Grafana dashboard queries |
| `PHASE5_PLUS_SUMMARY.md` | Phase 5 implementation summary |
| `PHASE5_PLUSPLUS_SUMMARY.md` | This document (Phase 5++ summary) |

---

## 🔮 Optional Next Steps

1. **Automated Replay**: Cron job to retry DLQ events
2. **Batch Replay API**: `POST /replay/batch` with ID array
3. **Time-Range Replay**: `POST /replay/range?start=X&end=Y`
4. **Replay Scheduling**: Schedule bulk replays for off-hours
5. **Webhook Integration**: Trigger replays from external systems
