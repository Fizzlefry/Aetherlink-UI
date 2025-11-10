# Grafana Recovery Timeline - Quick Start

## 🚀 5-Minute Setup

### Step 1: Generate Test Data (Optional)
```bash
python generate_test_recovery_events.py 100
```

This creates 100 sample recovery events for testing the dashboard.

### Step 2: Install SQLite Datasource Plugin

#### Docker Compose Method
Add to your Grafana service in `docker-compose.yml`:
```yaml
services:
  grafana:
    environment:
      - GF_INSTALL_PLUGINS=frser-sqlite-datasource
    volumes:
      - ./monitoring/recovery_events.sqlite:/var/lib/grafana/recovery_events.sqlite:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
```

Then restart:
```bash
docker-compose down && docker-compose up -d grafana
```

#### Manual Installation (Local Grafana)
```bash
grafana-cli plugins install frser-sqlite-datasource
# Then restart Grafana service
```

### Step 3: Configure Datasource

#### Option A: Auto-Provisioning (Recommended)
The datasource config is already in `monitoring/grafana/datasources/recovery-events.yml`.

Just update the path if needed:
```yaml
jsonData:
  path: /var/lib/grafana/recovery_events.sqlite  # Docker path
  # OR
  path: C:/Users/jonmi/OneDrive/Documents/AetherLink/monitoring/recovery_events.sqlite  # Windows absolute
```

#### Option B: Manual Configuration
1. Open Grafana → **Configuration → Data Sources**
2. Click **Add data source**
3. Search for **SQLite**
4. Configure:
   - **Name:** `Recovery Events`
   - **Path:** Full path to `monitoring/recovery_events.sqlite`
5. Click **Save & Test**

### Step 4: Import Dashboard
1. Open Grafana → **Dashboards → Import**
2. Click **Upload JSON file**
3. Select: `monitoring/grafana/dashboards/recovery-timeline.json`
4. Select datasource: **Recovery Events**
5. Click **Import**

### Step 5: View Dashboard
Navigate to **Dashboards → AetherLink Recovery Timeline**

You should see:
- ✅ Recent remediation events table
- ✅ Success rate stat
- ✅ Total remediations counter
- ✅ Pie charts by action and tenant
- ✅ Timeline graph
- ✅ Failed events table

## 🔍 Verification

### Check Database Has Data
```bash
sqlite3 monitoring/recovery_events.sqlite "SELECT COUNT(*) FROM remediation_events"
```

Should show > 0 if you generated test data or have real events.

### Test Datasource
In Grafana Explore:
```sql
SELECT COUNT(*) as total FROM remediation_events
```

Should return a number.

### Test Query
```sql
SELECT * FROM remediation_events ORDER BY id DESC LIMIT 5
```

Should show recent events.

## 🎨 Dashboard Panels

### 1. Recent Remediation Events
**Type:** Table
**Shows:** Last 100 events with color-coded status

### 2. Success Rate (24h)
**Type:** Stat
**Thresholds:**
- 🔴 Red: < 80%
- 🟡 Yellow: 80-95%
- 🟢 Green: > 95%

### 3. Total Remediations (24h)
**Type:** Stat
**Shows:** Count of all remediation attempts

### 4. By Action Type (24h)
**Type:** Pie Chart
**Shows:** Distribution of auto_ack, replay, escalate, defer

### 5. By Tenant (24h)
**Type:** Pie Chart
**Shows:** Which tenants trigger most remediations

### 6. Remediation Timeline
**Type:** Time Series (Bars)
**Shows:** Remediation volume over time

### 7. Failed Remediations
**Type:** Table
**Shows:** Only failed events with error details

## 🔧 Troubleshooting

### "Database file not found"
**Fix:** Check the path in datasource config matches where SQLite file exists.

For Docker:
```yaml
volumes:
  - ./monitoring/recovery_events.sqlite:/var/lib/grafana/recovery_events.sqlite:ro
```

For Windows:
```yaml
jsonData:
  path: C:/Users/YOUR_USER/path/to/monitoring/recovery_events.sqlite
```

### "No data" in panels
**Causes:**
1. No events in database yet
2. Time range too narrow
3. Datasource not connected

**Fixes:**
1. Run `python generate_test_recovery_events.py` to create test data
2. Expand time range to "Last 24 hours" or "Last 7 days"
3. Go to datasource settings and click "Save & Test"

### Queries timing out
**Fix:** Add indexes to speed up queries:
```sql
CREATE INDEX idx_ts ON remediation_events(ts);
CREATE INDEX idx_status ON remediation_events(status);
CREATE INDEX idx_tenant ON remediation_events(tenant);
CREATE INDEX idx_alertname ON remediation_events(alertname);
```

### Time display issues
SQLite stores timestamps as TEXT in ISO format. Queries use `datetime(ts)` for proper filtering.

## 📊 Sample Queries

### All Events
```sql
SELECT * FROM remediation_events ORDER BY id DESC LIMIT 100
```

### Success Rate
```sql
SELECT
  CAST(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as rate
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-24 hours')
```

### By Action Type
```sql
SELECT action, COUNT(*) as count
FROM remediation_events
WHERE datetime(ts) >= datetime('now', '-7 days')
GROUP BY action
ORDER BY count DESC
```

### Failed Events Only
```sql
SELECT ts, alertname, tenant, action, details
FROM remediation_events
WHERE status = 'error'
ORDER BY id DESC
LIMIT 50
```

### Top Alerts
```sql
SELECT
  alertname,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failures
FROM remediation_events
GROUP BY alertname
ORDER BY total DESC
LIMIT 10
```

## 🎯 Next Steps

### Add Alerting
Create alerts in Grafana for:
- High failure rate (> 50% errors in 1 hour)
- No remediations in 24 hours (possible logging issue)
- Specific alerts failing repeatedly

### Extend Schema
Add columns for richer analytics:
```sql
ALTER TABLE remediation_events ADD COLUMN confidence REAL;
ALTER TABLE remediation_events ADD COLUMN duration_ms INTEGER;
ALTER TABLE remediation_events ADD COLUMN operator_id TEXT;
```

### Add Retention Policy
Clean up old events automatically:
```sql
DELETE FROM remediation_events
WHERE datetime(ts) < datetime('now', '-90 days')
```

### Integrate with Other Dashboards
- Add recovery panels to main Command Center dashboard
- Create annotations on time series from recovery events
- Link alerts to recovery history

## 📁 Files Reference

| File | Purpose |
|------|---------|
| `monitoring/recovery_events.sqlite` | SQLite database (auto-created) |
| `monitoring/grafana/datasources/recovery-events.yml` | Datasource config |
| `monitoring/grafana/dashboards/recovery-timeline.json` | Dashboard JSON |
| `generate_test_recovery_events.py` | Test data generator |
| `grafana-recovery-timeline-setup.md` | Detailed setup guide |
| `services/command-center/main.py` | Recovery event writer |

## ✅ Success Checklist

- [ ] SQLite datasource plugin installed
- [ ] Database file exists with test data
- [ ] Datasource configured and tested
- [ ] Dashboard imported successfully
- [ ] All panels showing data
- [ ] Time range selector working
- [ ] Refresh rate set (default: 30s)
- [ ] Colors and thresholds displaying correctly

## 🆘 Getting Help

If you run into issues:
1. Check Grafana logs for errors
2. Verify SQLite file permissions (must be readable by Grafana)
3. Test SQL queries directly in SQLite CLI
4. Review datasource path configuration
5. Ensure recovery events are being written by Command Center

## 🎉 You're Done!

Your Recovery Timeline dashboard is now live. Every autonomous action taken by AetherLink will appear here, giving you complete visibility into the self-healing system.
