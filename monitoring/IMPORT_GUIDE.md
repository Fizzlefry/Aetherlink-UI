# Quick Import Guide - Enhanced Dashboard

## 🚀 One-Minute Import

### Option 1: Via Grafana UI (Recommended)

1. **Start monitoring stack** (if not already running):
   ```powershell
   .\scripts\start-monitoring.ps1
   ```

2. **Open Grafana**:
   - URL: http://localhost:3000
   - Login: `admin` / `admin`

3. **Import dashboard**:
   - Click **Dashboards** (left sidebar, four-square icon)
   - Click **Import** button (top right)
   - Click **Upload JSON file**
   - Select: `monitoring/grafana-dashboard-enhanced.json`
   - Click **Import**

4. **Done!** Dashboard is now available in the "AetherLink" folder

---

### Option 2: Via curl (Grafana API)

```powershell
# Set Grafana API key (or use admin:admin)
$grafanaUrl = "http://localhost:3000"
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))

# Import dashboard
$dashboard = Get-Content monitoring/grafana-dashboard-enhanced.json -Raw | ConvertFrom-Json
$body = @{
    dashboard = $dashboard
    overwrite = $true
    folderId = 0
} | ConvertTo-Json -Depth 100

Invoke-RestMethod -Uri "$grafanaUrl/api/dashboards/db" `
    -Method Post `
    -Headers @{ Authorization = "Basic $auth" } `
    -ContentType "application/json" `
    -Body $body
```

---

### Option 3: Auto-Provision (Permanent)

To make the enhanced dashboard auto-load on every Grafana start:

1. **Copy dashboard to provisioning directory**:
   ```powershell
   Copy-Item monitoring/grafana-dashboard-enhanced.json monitoring/dashboards/
   ```

2. **Update provisioning config** (`monitoring/grafana-provisioning.yml`):
   ```yaml
   apiVersion: 1
   providers:
   - name: 'AetherLink Dashboards'
     orgId: 1
     folder: 'AetherLink'
     type: file
     options:
       path: /etc/grafana/provisioning/dashboards
   ```

3. **Update Docker Compose** (`monitoring/docker-compose.yml`):
   ```yaml
   grafana:
     volumes:
       - ./dashboards:/etc/grafana/provisioning/dashboards:ro
       - ./grafana-provisioning.yml:/etc/grafana/provisioning/dashboards/aetherlink.yml:ro
   ```

4. **Restart Grafana**:
   ```powershell
   .\scripts\start-monitoring.ps1 -Restart
   ```

---

## 📊 What You Get

### Enhanced Dashboard Includes:

#### **Top Row - Key Health Gauges (3 new panels)**
1. **Answer Cache Hit Ratio** - Health proxy indicator
   - Red <30%, Yellow 30-60%, Green >60%
2. **Rerank Utilization %** - Cost signal
   - Green <30%, Yellow 30-60%, Red >60%
3. **Low-Confidence Share** - Quality signal
   - Green <10%, Yellow 10-20%, Red >20%
4. **Answer Requests by Tenant** - Time series

#### **Middle Row - Cache & Mode Analysis**
5. **Cache Hit Ratio by Tenant** - Overall gauge
6. **Cache Activity by Endpoint** - Stacked area
7. **Answers by Search Mode** - Bar chart

#### **Bottom Row - Quality & Stats**
8. **Low Confidence Answers** - Time series
9. **Reranking Usage** - Percentage stack
10-13. **Total Stats** - Answers, hits, misses, low confidence

#### **Tenant Variable**
- Dropdown with all available tenants
- "All" option to view aggregate
- Auto-refresh from Prometheus

---

## 🎯 Verification Steps

### 1. Generate Test Data
```powershell
$env:API_ADMIN_KEY = "admin-secret-123"
.\scripts\tenant-smoke-test.ps1
```

### 2. Check Metrics Exist
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String "aether_rag_.*tenant=" | Select-Object -First 10
```

### 3. Verify Prometheus Scraping
Open: http://localhost:9090/targets
- Should see `aetherlink_api` target as **UP**

### 4. Open Enhanced Dashboard
- URL: http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced
- OR navigate: Dashboards → AetherLink → AetherLink RAG – Tenant Metrics (Enhanced)

### 5. Select Tenant
- Use dropdown at top to filter by tenant
- Try "All" to see aggregate view

---

## 🔍 Troubleshooting

### Dashboard Shows "No Data"

**Check Prometheus scraping:**
```powershell
curl.exe http://localhost:9090/api/v1/targets | ConvertFrom-Json
```

**Check if metrics exist:**
```powershell
curl.exe http://localhost:8000/metrics | Select-String "aether_rag"
```

**Check Grafana datasource:**
- Go to Configuration → Data Sources
- Click "Prometheus"
- Should show URL: `http://aether-prom:9090`
- Click "Save & Test" → should see green checkmark

---

### Panels Show "N/A" or Error

**Check tenant variable:**
- Dashboard Settings → Variables → tenant
- Query should be: `label_values(aether_rag_answers_total, tenant)`
- Refresh: "On Dashboard Load"

**Check PromQL syntax:**
- Click panel title → Edit
- In Query tab, click "Query Inspector"
- Look for PromQL errors

---

### Gauges Not Color-Coded

**Check thresholds:**
- Edit panel → Field tab → Thresholds
- Should show:
  - Cache ratio: Red <0.3, Yellow 0.3-0.6, Green >0.6
  - Rerank: Green <30, Yellow 30-60, Red >60
  - Confidence: Green <10, Yellow 10-20, Red >20

---

### Tenant Dropdown Empty

**Generate metrics first:**
```powershell
.\scripts\tenant-smoke-test.ps1
```

**Check if labels exist in Prometheus:**
```promql
# Open Prometheus at http://localhost:9090
# Run query:
aether_rag_answers_total
```

Should show results with `tenant="..."` labels.

---

## 📱 Side-by-Side Comparison

You can import **both** dashboards:
- **Original:** `monitoring/grafana-dashboard.json`
- **Enhanced:** `monitoring/grafana-dashboard-enhanced.json`

They have different UIDs so won't conflict:
- Original UID: `aetherlink_rag_tenant_metrics`
- Enhanced UID: `aetherlink_rag_tenant_metrics_enhanced`

---

## 🎨 Customization Tips

### Change Refresh Rate
- Dashboard Settings → Time Options → Auto Refresh
- Default: 10s
- Options: 5s, 10s, 30s, 1m, 5m

### Add Custom Panel
1. Click **Add Panel** (top right)
2. Choose visualization type (Gauge, Time Series, Stat, etc.)
3. Enter PromQL query
4. Configure thresholds/colors in Field tab
5. Add to tenant variable: `{tenant=~"$tenant"}`

### Export Modified Dashboard
- Dashboard Settings → JSON Model → Copy to clipboard
- Save to new file: `monitoring/grafana-dashboard-custom.json`

---

## 🚀 Next Steps

### 1. Add Recording Rules
For faster dashboard performance, see:
- `monitoring/ENHANCED_FEATURES.md` → "Recording Rules" section

### 2. Set Up Alertmanager
For Slack/email notifications, see:
- `monitoring/ENHANCED_FEATURES.md` → "Alert Routing" section

### 3. Add Billing Panel
Track costs per tenant, see:
- `monitoring/ENHANCED_FEATURES.md` → "Advanced Use Cases" section

---

## ✅ Quick Checklist

- [ ] Monitoring stack running (`.\scripts\start-monitoring.ps1`)
- [ ] Test data generated (`.\scripts\tenant-smoke-test.ps1`)
- [ ] Enhanced dashboard imported (via Grafana UI or API)
- [ ] Dashboard shows data (select tenant from dropdown)
- [ ] All 3 gauges display correctly (cache, rerank, confidence)
- [ ] Alerts loaded in Prometheus (http://localhost:9090/alerts)

---

## 📚 Related Documentation

- **Setup Guide:** `monitoring/README.md`
- **Troubleshooting:** `monitoring/QUICKSTART.md`
- **Enhanced Features:** `monitoring/ENHANCED_FEATURES.md`
- **Alert Rules:** `monitoring/prometheus-alerts.yml`
- **Verification:** `TENANT_METRICS_VERIFY.md`

---

## 🎉 Done!

Your enhanced dashboard is now ready with:
- ✅ 3 color-coded health/cost/quality gauges
- ✅ 14 total panels (vs 11 in original)
- ✅ Fully wired tenant variable
- ✅ 10-second auto-refresh
- ✅ Production-ready thresholds

**Import URL:** `monitoring/grafana-dashboard-enhanced.json`

**Direct access:** http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced

🚀 **Happy monitoring!**
