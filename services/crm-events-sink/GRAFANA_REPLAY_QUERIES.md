# Grafana Queries for Replay Tracking

## Panel: Original vs Replayed Events (Timeseries)

### Query 1: Original Events per Minute
```sql
SELECT
  $__timeGroupAlias(received_at, 1m),
  COUNT(*) as "Original Events"
FROM event_journal
WHERE
  $__timeFilter(received_at)
  AND replay_count = 0
GROUP BY 1
ORDER BY 1
```

### Query 2: Replayed Events per Minute
```sql
SELECT
  $__timeGroupAlias(received_at, 1m),
  COUNT(*) as "Replayed Events"
FROM event_journal
WHERE
  $__timeFilter(received_at)
  AND replay_count > 0
GROUP BY 1
ORDER BY 1
```

---

## Panel: Replay Sources (Pie Chart)

```sql
SELECT
  COALESCE(replay_source, 'original') as source,
  COUNT(*) as count
FROM event_journal
WHERE $__timeFilter(received_at)
GROUP BY replay_source
```

---

## Panel: Replay Activity by Topic (Table)

```sql
SELECT
  topic,
  SUM(CASE WHEN replay_count = 0 THEN 1 ELSE 0 END) as "Original",
  SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) as "Replayed",
  COUNT(*) as "Total"
FROM event_journal
WHERE $__timeFilter(received_at)
GROUP BY topic
ORDER BY "Replayed" DESC
```

---

## Panel: Recent Replay Events (Table)

```sql
SELECT
  id as "Event ID",
  topic as "Topic",
  tenant_id as "Tenant",
  replay_source as "Source",
  payload->>'_replayed_from_event_id' as "Original Event ID",
  received_at as "Replayed At"
FROM event_journal
WHERE
  $__timeFilter(received_at)
  AND replay_count > 0
ORDER BY received_at DESC
LIMIT 20
```

---

## Panel: Replay Rate (Gauge)

```sql
SELECT
  ROUND(
    100.0 * SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) / COUNT(*),
    2
  ) as "Replay Percentage"
FROM event_journal
WHERE $__timeFilter(received_at)
```

---

## Alert: High Replay Volume

**Condition**: If more than 20% of events in last 5 minutes are replays

```sql
SELECT
  CASE
    WHEN SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) > 0
      AND 100.0 * SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) / COUNT(*) > 20
    THEN 1
    ELSE 0
  END as alert_triggered
FROM event_journal
WHERE received_at > NOW() - INTERVAL '5 minutes'
```

**Action**: This could indicate:
- Operator is performing bulk replay
- Automated replay system is active
- Potential issue requiring investigation

---

## Useful Ad-Hoc Queries

### Find Most Replayed Original Event
```sql
SELECT
  payload->>'_replayed_from_event_id' as original_event_id,
  COUNT(*) as replay_count
FROM event_journal
WHERE replay_count > 0
GROUP BY payload->>'_replayed_from_event_id'
ORDER BY replay_count DESC
LIMIT 10;
```

### Compare Original Event to Replays
```sql
-- Original event
SELECT id, topic, tenant_id, payload, received_at, 'original' as type
FROM event_journal
WHERE id = 1
UNION ALL
-- All replays of that event
SELECT id, topic, tenant_id, payload, received_at, 'replay' as type
FROM event_journal
WHERE payload->>'_replayed_from_event_id' = '1'
ORDER BY received_at;
```

### Daily Replay Statistics
```sql
SELECT
  DATE(received_at) as date,
  topic,
  SUM(CASE WHEN replay_count = 0 THEN 1 ELSE 0 END) as original,
  SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) as replayed,
  ROUND(
    100.0 * SUM(CASE WHEN replay_count > 0 THEN 1 ELSE 0 END) / COUNT(*),
    2
  ) as replay_percentage
FROM event_journal
WHERE received_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(received_at), topic
ORDER BY date DESC, topic;
```

---

## Configuration in Grafana

### Step 1: Add PostgreSQL Data Source
1. Go to **Configuration > Data Sources**
2. Add **PostgreSQL**
3. Configure:
   - **Host**: `aether-crm-events-db:5432`
   - **Database**: `crm_events`
   - **User**: `crm_events`
   - **Password**: `crm_events`
   - **SSL Mode**: `disable` (for local dev)

### Step 2: Create Dashboard
1. **Dashboards > New Dashboard**
2. Add panels using queries above
3. Configure visualization types:
   - **Timeseries**: Query 1 & 2 (Original vs Replayed)
   - **Pie Chart**: Replay Sources
   - **Table**: Replay Activity by Topic, Recent Replay Events
   - **Gauge**: Replay Rate

### Step 3: Set Time Range Variables
- Use `$__timeFilter(received_at)` in all queries
- Dashboard default: Last 24 hours
- Refresh: Every 30 seconds (for live monitoring)

---

## Example Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Original vs Replayed Events (Timeseries)                   │
│  ──────────────────────────────────────────────────         │
│  │ Original (blue line)  ▁▂▃▅▆█▆▅▃▂▁                        │
│  │ Replayed (green line) ▁▁▁▁▃▅▃▁▁▁▁                        │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────────────────┐
│ Replay Sources (Pie) │  │ Replay Rate (Gauge)              │
│                      │  │                                  │
│ ●● operator_api 85%  │  │        5.2%                      │
│ ●  automated    15%  │  │  ▓▓▓▓░░░░░░░░░░░░░░░░░░          │
└──────────────────────┘  └──────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Recent Replay Events (Table)                               │
├────────┬──────────────────┬────────┬────────────┬──────────┤
│ ID     │ Topic            │ Tenant │ Source     │ From ID  │
├────────┼──────────────────┼────────┼────────────┼──────────┤
│ 12     │ leads.created    │ acme   │ operator   │ 1        │
│ 11     │ jobs.created     │ acme   │ automated  │ 7        │
└─────────────────────────────────────────────────────────────┘
```

---

## Performance Considerations

### Index Usage
The following indexes support these queries:
- `idx_event_journal_replay_count` - Filter original vs replayed
- `idx_event_journal_received_at_desc` - Time-based queries
- `idx_event_journal_topic_tenant` - Per-tenant/topic aggregation

### Query Optimization Tips
1. Always include `$__timeFilter(received_at)` to use time index
2. Use `LIMIT` on table panels to avoid large result sets
3. Consider materialized views for complex aggregations
4. For historical analysis, export to data warehouse

---

## Next Steps

1. **Import Dashboard Template**: Save these queries as a JSON dashboard
2. **Set Up Alerts**: Configure alert rules for high replay volumes
3. **Export Reports**: Create scheduled reports for daily replay statistics
4. **Automate Cleanup**: Archive old replayed events after 90 days
