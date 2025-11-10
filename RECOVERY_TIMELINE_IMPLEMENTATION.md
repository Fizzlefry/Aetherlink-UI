# Recovery Timeline Implementation

## Overview
Tracks all autonomous remediation actions (auto-acks, auto-heals, etc.) in a SQLite database for auditing, analysis, and visualization.

## Implementation Summary

### 1. Database Layer
**File:** `monitoring/recovery_events.sqlite`

**Schema:**
```sql
CREATE TABLE remediation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,           -- ISO timestamp with 'Z'
    alertname TEXT,             -- Alert type (e.g., "HighFailureRate")
    tenant TEXT,                -- Tenant identifier
    action TEXT,                -- Action taken (e.g., "auto_ack", "replay", "escalate")
    status TEXT,                -- "success" or "error"
    details TEXT                -- Additional context (max 500 chars)
)
```

### 2. Writer Function
**Location:** `services/command-center/main.py:25-66`

```python
def record_remediation_event(
    alertname: str,
    tenant: str,
    action: str,
    status: str,
    details: str = "",
) -> None:
    """Record a remediation event to SQLite for Grafana recovery timeline."""
```

**Features:**
- Auto-creates database and table on first write
- Thread-safe SQLite operations
- Automatic directory creation
- 500-char detail truncation
- ISO timestamp format with 'Z' suffix

### 3. Integration Points

**Adaptive Auto-Responder** (`_apply_adaptive_action`):
- Logs every auto-ack attempt (success and failure)
- Extracts alertname from `alert_type` or `alertname` field
- Falls back to "unknown_alert" if neither present

**Lines:** `services/command-center/main.py:771-815`

```python
# On success
record_remediation_event(
    alertname=alertname,
    tenant=tenant,
    action="auto_ack",
    status="success",
    details=f"Auto-acknowledged alert {alert_id}",
)

# On failure
record_remediation_event(
    alertname=alertname,
    tenant=tenant,
    action="auto_ack",
    status="error",
    details=str(e),
)
```

### 4. REST API Endpoint
**Endpoint:** `GET /ops/remediate/history`

**Location:** `services/command-center/main.py:1047-1101`

**Query Parameters:**
- `limit` (int, default=100, max=500): Number of records to return
- `tenant` (str, optional): Filter by tenant
- `alertname` (str, optional): Filter by alert type

**Response Format:**
```json
{
  "items": [
    {
      "id": 1,
      "ts": "2025-11-09T19:54:23.776586Z",
      "alertname": "HighFailureRate",
      "tenant": "acme-corp",
      "action": "auto_ack",
      "status": "success",
      "details": "Auto-acknowledged alert alert_12345"
    }
  ],
  "total": 1
}
```

**Example Usage:**
```bash
# Get last 100 events
curl http://localhost:8010/ops/remediate/history

# Filter by tenant
curl 'http://localhost:8010/ops/remediate/history?tenant=acme-corp'

# Filter by alert type
curl 'http://localhost:8010/ops/remediate/history?alertname=HighFailureRate'

# Limit results
curl 'http://localhost:8010/ops/remediate/history?limit=20'
```

## Testing

### Manual Database Test
```bash
python -c "import sqlite3; from pathlib import Path; conn = sqlite3.connect('monitoring/recovery_events.sqlite'); cur = conn.cursor(); cur.execute('SELECT ts, alertname, tenant, action, status FROM remediation_events ORDER BY id DESC LIMIT 10'); rows = cur.fetchall(); [print(r) for r in rows]; conn.close()"
```

### Test Scripts
1. **Python Test:** `test_remediation_history.py`
   ```bash
   python test_remediation_history.py
   ```

2. **Shell Test:** `test_remediation_endpoint.sh`
   ```bash
   ./test_remediation_endpoint.sh
   ```

### Verification Steps
1. Trigger an auto-ack action in Command Center
2. Query the database:
   ```bash
   sqlite3 monitoring/recovery_events.sqlite "SELECT * FROM remediation_events ORDER BY id DESC LIMIT 5"
   ```
3. Test the API endpoint:
   ```bash
   curl http://localhost:8010/ops/remediate/history?limit=5
   ```

## Future Enhancements

### Grafana Integration
Create a SQLite datasource pointing to `monitoring/recovery_events.sqlite`:

**Dashboard Query:**
```sql
SELECT
  ts as time,
  alertname,
  tenant,
  action,
  status,
  details
FROM remediation_events
WHERE $__timeFilter(ts)
ORDER BY ts DESC
```

**Panel Types:**
- **Table:** Recent remediation events
- **Stat:** Success rate (COUNT(*) WHERE status='success')
- **Time Series:** Actions over time by type
- **Bar Chart:** Actions by tenant

### Additional Action Types
Current: `auto_ack`

Future additions:
- `replay` - Delivery replay actions
- `escalate` - Escalations to operators
- `defer` - Deferred actions
- `scale` - Auto-scaling actions
- `restart` - Service restarts

### Extended Metadata
Consider adding columns:
- `alert_id` - Alertmanager alert identifier
- `operator_id` - If manually triggered
- `confidence` - ML confidence score
- `duration_ms` - Action execution time

### Retention Policy
Add a cleanup job to maintain database size:
```python
# Delete records older than 90 days
DELETE FROM remediation_events
WHERE datetime(ts) < datetime('now', '-90 days')
```

## Architecture Notes

### Why SQLite?
- ✅ No external dependencies
- ✅ Zero configuration
- ✅ Fast local queries
- ✅ Perfect for audit logs
- ✅ Easy Grafana integration
- ✅ File-based (easy backups)

### Thread Safety
- Each write opens a new connection
- Auto-commits after insert
- Connections properly closed in finally block
- SQLite handles concurrent reads automatically

### Error Handling
- Writer function never raises exceptions (logs to console)
- API endpoint returns empty list if DB doesn't exist
- Graceful degradation if writes fail

## Monitoring

### Key Metrics to Track
1. **Write Success Rate:** Monitor console for DB write errors
2. **API Response Time:** Track endpoint performance
3. **Database Size:** Monitor file growth
4. **Event Volume:** Track events per hour/day

### Alerting
Consider alerts for:
- High failure rate (status='error')
- No events in 24h (possible recording failure)
- Database size > 1GB (retention cleanup needed)

## Integration with Existing Systems

### Phase VIII M10 (Operator Audit Trail)
- Complements operator audit with autonomous actions
- Provides "what the system did" vs "what operators did"

### Phase XXIII (Adaptive Auto-Response)
- Records all adaptive actions
- Provides feedback for learning models
- Enables pattern analysis

### Phase X (Auto-Healing)
- Future integration point for replay/escalate/defer actions
- Unified remediation ledger

## Files Modified
- `services/command-center/main.py` (helper function + endpoint)

## Files Created
- `test_remediation_history.py` (Python test script)
- `test_remediation_endpoint.sh` (Shell test script)
- `RECOVERY_TIMELINE_IMPLEMENTATION.md` (this file)

## Database Location
```
monitoring/recovery_events.sqlite
```
- Auto-created on first write
- Relative path from project root
- Backed up with regular file backups
- Can be queried directly with any SQLite client

## Status
✅ **Implementation Complete**
- Writer function: Done
- API endpoint: Done
- Integration with auto-ack: Done
- Test scripts: Done
- Documentation: Done

**Next Steps:**
1. Trigger real auto-acks to populate data
2. Build Grafana dashboard
3. Add additional action types as needed
4. Implement retention policy if needed
