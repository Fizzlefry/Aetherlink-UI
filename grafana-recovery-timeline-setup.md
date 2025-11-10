# Grafana Recovery Timeline Setup

## Prerequisites
- Grafana with SQLite datasource plugin installed
- `monitoring/recovery_events.sqlite` exists (created by first remediation event)

## Step 1: Install SQLite Datasource Plugin

### Option A: Grafana Cloud / Docker
Already included in most distributions.

### Option B: Manual Install
```bash
grafana-cli plugins install frser-sqlite-datasource
# Then restart Grafana
```

### Option C: Docker Compose (if using)
Add to your Grafana environment:
```yaml
environment:
  - GF_INSTALL_PLUGINS=frser-sqlite-datasource
```

## Step 2: Configure SQLite Datasource

### Via UI
1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Search for **SQLite**
4. Configure:
   - **Name:** `Recovery Events`
   - **Path:** `/var/lib/grafana/recovery_events.sqlite` (adjust based on mount)
5. Click **Save & Test**

### Via Provisioning File

Create `monitoring/grafana/datasources/recovery-events.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Recovery Events
    type: frser-sqlite-datasource
    access: proxy
    isDefault: false
    jsonData:
      path: /var/lib/grafana/recovery_events.sqlite
    editable: true
```

### Docker Volume Mount
If running Grafana in Docker, mount the SQLite file:

```yaml
# docker-compose.yml
services:
  grafana:
    volumes:
      - ./monitoring/recovery_events.sqlite:/var/lib/grafana/recovery_events.sqlite:ro
```

Or for absolute path:
```yaml
volumes:
  - C:/Users/jonmi/OneDrive/Documents/AetherLink/monitoring/recovery_events.sqlite:/var/lib/grafana/recovery_events.sqlite:ro
```

## Step 3: Create Recovery Timeline Dashboard

### Dashboard JSON

Save as `monitoring/grafana/dashboards/recovery-timeline.json`:

```json
{
  "dashboard": {
    "title": "Recovery Timeline",
    "tags": ["aetherlink", "recovery", "autoheal"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Recent Remediation Events",
        "type": "table",
        "gridPos": { "x": 0, "y": 0, "w": 24, "h": 10 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT ts as Time, alertname as Alert, tenant as Tenant, action as Action, status as Status, details as Details FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours') ORDER BY id DESC LIMIT 100",
            "format": "table"
          }
        ],
        "fieldConfig": {
          "overrides": [
            {
              "matcher": { "id": "byName", "options": "Status" },
              "properties": [
                {
                  "id": "custom.cellOptions",
                  "value": { "type": "color-background" }
                },
                {
                  "id": "mappings",
                  "value": [
                    {
                      "type": "value",
                      "value": "success",
                      "displayText": "✓ Success",
                      "color": "green"
                    },
                    {
                      "type": "value",
                      "value": "error",
                      "displayText": "✗ Error",
                      "color": "red"
                    }
                  ]
                }
              ]
            }
          ]
        }
      },
      {
        "id": 2,
        "title": "Remediation Success Rate (24h)",
        "type": "stat",
        "gridPos": { "x": 0, "y": 10, "w": 6, "h": 4 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT CAST(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as value FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours')",
            "format": "table"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 80, "color": "yellow" },
                { "value": 95, "color": "green" }
              ]
            }
          }
        }
      },
      {
        "id": 3,
        "title": "Total Remediations (24h)",
        "type": "stat",
        "gridPos": { "x": 6, "y": 10, "w": 6, "h": 4 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT COUNT(*) as value FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours')",
            "format": "table"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "short"
          }
        }
      },
      {
        "id": 4,
        "title": "Remediations by Action Type (24h)",
        "type": "piechart",
        "gridPos": { "x": 12, "y": 10, "w": 6, "h": 4 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT action, COUNT(*) as count FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours') GROUP BY action",
            "format": "table"
          }
        ]
      },
      {
        "id": 5,
        "title": "Remediations by Tenant (24h)",
        "type": "piechart",
        "gridPos": { "x": 18, "y": 10, "w": 6, "h": 4 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT COALESCE(tenant, 'system') as tenant, COUNT(*) as count FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours') GROUP BY tenant",
            "format": "table"
          }
        ]
      },
      {
        "id": 6,
        "title": "Remediation Timeline",
        "type": "timeseries",
        "gridPos": { "x": 0, "y": 14, "w": 24, "h": 8 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT datetime(ts) as time, COUNT(*) as remediations FROM remediation_events WHERE datetime(ts) >= datetime('now', '-24 hours') GROUP BY strftime('%Y-%m-%d %H:%M', ts) ORDER BY time",
            "format": "time_series"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "custom": {
              "drawStyle": "bars",
              "fillOpacity": 80
            }
          }
        }
      },
      {
        "id": 7,
        "title": "Failed Remediations",
        "type": "table",
        "gridPos": { "x": 0, "y": 22, "w": 24, "h": 6 },
        "datasource": "Recovery Events",
        "targets": [
          {
            "rawSql": "SELECT ts as Time, alertname as Alert, tenant as Tenant, action as Action, details as Error FROM remediation_events WHERE status = 'error' AND datetime(ts) >= datetime('now', '-24 hours') ORDER BY id DESC LIMIT 50",
            "format": "table"
          }
        ]
      }
    ],
    "refresh": "30s",
    "time": {
      "from": "now-24h",
      "to": "now"
    }
  }
}
```

### Import Dashboard
1. Go to **Dashboards → Import**
2. Upload the JSON file
3. Select datasource: **Recovery Events**
4. Click **Import**

## Step 4: Sample Queries

### Recent Events (Last 100)
```sql
SELECT
  ts as Time,
  alertname as Alert,
  tenant as Tenant,
  action as Action,
  status as Status,
  details as Details
FROM remediation_events
ORDER BY id DESC
LIMIT 100
```

### Success Rate (24h)
```sql
SELECT
  CAST(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as success_rate
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-24 hours')
```

### Events by Action Type
```sql
SELECT
  action,
  COUNT(*) as count
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-7 days')
GROUP BY action
ORDER BY count DESC
```

### Events by Tenant
```sql
SELECT
  COALESCE(tenant, 'system') as tenant,
  COUNT(*) as count
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-7 days')
GROUP BY tenant
ORDER BY count DESC
```

### Failed Events Only
```sql
SELECT
  ts as Time,
  alertname as Alert,
  tenant as Tenant,
  action as Action,
  details as Error
FROM remediation_events
WHERE status = 'error'
  AND datetime(ts) >= datetime('now', '-24 hours')
ORDER BY id DESC
```

### Hourly Remediation Rate
```sql
SELECT
  strftime('%Y-%m-%d %H:00', ts) as hour,
  COUNT(*) as count,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failures
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-24 hours')
GROUP BY hour
ORDER BY hour
```

### Top Alerts by Remediation Count
```sql
SELECT
  alertname,
  COUNT(*) as total_remediations,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failures
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-7 days')
GROUP BY alertname
ORDER BY total_remediations DESC
LIMIT 10
```

## Step 5: Panel Configuration Tips

### Table Panel
- **Transform:** Use field name mapping for cleaner column headers
- **Cell Display Mode:** Use color-background for Status column
- **Column Width:** Set Time to fixed width (180px)

### Stat Panel
- **Thresholds:**
  - Red: < 80% success rate
  - Yellow: 80-95%
  - Green: > 95%
- **Unit:** Percent for success rate, Short for counts

### Time Series Panel
- **Draw Style:** Bars (better for discrete events)
- **Fill Opacity:** 80%
- **Stacking:** Normal (if showing multiple series)

### Pie Chart
- **Legend:** Show on right
- **Values:** Show absolute + percentage
- **Limit:** Top 10 only

## Step 6: Alerting (Optional)

### Alert: No Remediations in 24h
```sql
SELECT COUNT(*) as count
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-24 hours')
```
**Condition:** `count < 1` → May indicate logging failure

### Alert: High Failure Rate
```sql
SELECT
  CAST(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as failure_rate
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-1 hour')
```
**Condition:** `failure_rate > 50` → Investigate remediation issues

### Alert: Specific Alert Failing Repeatedly
```sql
SELECT
  alertname,
  COUNT(*) as failures
FROM remediation_events
WHERE status = 'error'
  AND datetime(ts) >= datetime('now', '-1 hour')
GROUP BY alertname
HAVING failures > 5
```
**Condition:** `failures > 5` → Alert pattern needs attention

## Troubleshooting

### Datasource Shows "Database file not found"
- Check file path in datasource config
- Verify Docker volume mount (if using containers)
- Ensure file has read permissions for Grafana user

### No Data in Panels
- Verify recovery events are being written:
  ```bash
  sqlite3 monitoring/recovery_events.sqlite "SELECT COUNT(*) FROM remediation_events"
  ```
- Check time range in dashboard (default: last 24h)
- Trigger a test remediation event

### Queries Slow
- Add indexes:
  ```sql
  CREATE INDEX idx_ts ON remediation_events(ts);
  CREATE INDEX idx_status ON remediation_events(status);
  CREATE INDEX idx_alertname ON remediation_events(alertname);
  ```

### Time Display Issues
- SQLite stores timestamps as TEXT (ISO format)
- Use `datetime(ts)` for time filtering
- Grafana's time picker works with ISO timestamps

## Testing the Setup

### 1. Verify Database Access
```bash
sqlite3 monitoring/recovery_events.sqlite "SELECT * FROM remediation_events LIMIT 5"
```

### 2. Test Datasource in Grafana
- Go to datasource settings
- Click "Save & Test"
- Should show green checkmark

### 3. Run Test Query
In Grafana Explore:
```sql
SELECT COUNT(*) FROM remediation_events
```

### 4. Generate Test Data
```bash
python -c "
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import random

db = Path('monitoring/recovery_events.sqlite')
conn = sqlite3.connect(db)
cur = conn.cursor()

actions = ['auto_ack', 'replay', 'escalate']
statuses = ['success', 'success', 'success', 'error']  # 75% success
tenants = ['acme-corp', 'test-tenant', 'demo-co']
alerts = ['HighFailureRate', 'ServiceDown', 'LatencySpike']

for i in range(50):
    ts = (datetime.utcnow() - timedelta(hours=random.randint(0, 24))).isoformat() + 'Z'
    cur.execute('''
        INSERT INTO remediation_events (ts, alertname, tenant, action, status, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        ts,
        random.choice(alerts),
        random.choice(tenants),
        random.choice(actions),
        random.choice(statuses),
        f'Test event {i}'
    ))

conn.commit()
print(f'Created 50 test events')
conn.close()
"
```

## Next Steps

1. **Add to existing dashboards** - Embed recovery panels in Command Center dashboard
2. **Create alerts** - Set up notifications for high failure rates
3. **Add annotations** - Mark remediation events on other time series panels
4. **Extend schema** - Add confidence scores, execution times, etc.
5. **Retention policy** - Implement cleanup for old events

## References
- [Grafana SQLite Datasource Plugin](https://github.com/fr-ser/grafana-sqlite-datasource)
- [SQLite Date/Time Functions](https://www.sqlite.org/lang_datefunc.html)
- [Grafana Table Panel](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/table/)
