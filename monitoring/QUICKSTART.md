# Monitoring Stack - Quick Start & Troubleshooting

## 🚀 Quick Start (3 Steps)

### 1. Start the Monitoring Stack
```powershell
# Option A: Use script
.\scripts\start-monitoring.ps1

# Option B: Use VS Code task
# Ctrl+Shift+P → Tasks: Run Task → "Aether: Start Monitoring Stack"

# Option C: Manual
cd monitoring
docker compose up -d
```

### 2. Verify Services
```powershell
# Check containers
docker ps | Select-String "aether"

# Check Prometheus targets
curl.exe -s http://localhost:9090/api/v1/targets | ConvertFrom-Json

# Check Grafana health
curl.exe -s http://localhost:3000/api/health
```

### 3. Generate Metrics
```powershell
# Set admin key (one time)
$env:API_ADMIN_KEY = "admin-secret-123"

# Run smoke test
.\scripts\tenant-smoke-test.ps1
```

---

## 🌐 Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin/admin |
| **AetherLink API** | http://localhost:8000 | API key required |

---

## 🔍 Verify Everything Works

### Step 1: Check Prometheus Scraping
1. Open http://localhost:9090
2. Go to **Status → Targets**
3. Verify `aetherlink_api` target shows **UP**

**If DOWN:**
- Check API is running: `curl http://localhost:8000/health`
- On Linux, change `host.docker.internal` to your host IP in `prometheus-config.yml`
- Restart Prometheus: `docker restart aether-prom`

### Step 2: Query Metrics in Prometheus
1. Go to **Graph** tab
2. Run test queries:
   ```promql
   aether_rag_answers_total
   aether_rag_cache_hits_total
   sum(rate(aether_rag_answers_total[5m])) by (tenant)
   ```

**If no data:**
- Generate traffic: `.\scripts\tenant-smoke-test.ps1`
- Check API metrics endpoint: `curl http://localhost:8000/metrics | Select-String aether_rag`

### Step 3: Check Grafana Dashboard
1. Open http://localhost:3000
2. Login: `admin` / `admin`
3. Navigate: **Dashboards → AetherLink → AetherLink RAG - Tenant Metrics**
4. Select a tenant from the dropdown
5. Set time range to "Last 1 hour"

**If dashboard not found:**
- Check provisioning: `docker logs aether-grafana | Select-String provisioning`
- Manual import: **Dashboard → Import → Upload `monitoring/grafana-dashboard.json`**

**If panels are empty:**
- Verify Prometheus datasource: **Configuration → Data Sources → Prometheus**
- URL should be: `http://aether-prom:9090`
- Click "Save & Test"

---

## 🐛 Troubleshooting

### Problem: No tenant labels showing

**Symptoms:** Metrics exist but no `tenant=` labels

**Solution:**
```powershell
# 1. Use an editor API key (not admin)
$env:API_ADMIN_KEY = "admin-secret-123"
$keys = curl.exe -s -H "x-admin-key: $env:API_ADMIN_KEY" http://localhost:8000/admin/apikeys | ConvertFrom-Json
$env:API_KEY_EXPERTCO = ($keys.items | Where-Object { $_.role -eq 'editor' } | Select-Object -First 1).key

# 2. Make requests with that key
curl.exe -s -H "X-API-Key: $env:API_KEY_EXPERTCO" "http://localhost:8000/search?q=test&mode=hybrid" | Out-Null

# 3. Check metrics
curl.exe -s http://localhost:8000/metrics | Select-String 'tenant='
```

### Problem: Prometheus can't scrape API

**Symptoms:** Target shows **DOWN** in Prometheus

**Check 1: API is running**
```powershell
curl.exe -s http://localhost:8000/health
# Should return: {"status":"healthy"}
```

**Check 2: Network connectivity**
```powershell
# From Prometheus container
docker exec aether-prom wget -O- http://host.docker.internal:8000/metrics

# If fails on Linux, use host IP instead
docker exec aether-prom wget -O- http://192.168.1.100:8000/metrics
```

**Fix for Linux:**
Edit `monitoring/prometheus-config.yml`:
```yaml
static_configs:
  - targets: ['192.168.1.100:8000']  # Use your host IP
```
Restart: `docker restart aether-prom`

### Problem: Grafana dashboard empty

**Check 1: Time range**
- Dashboard defaults to "Last 1 hour"
- If no recent traffic, expand to "Last 6 hours" or "Last 24 hours"

**Check 2: Tenant filter**
- Tenant variable dropdown may be set to a tenant with no data
- Select **All** or choose a different tenant

**Check 3: Prometheus datasource**
```powershell
# Verify datasource
curl.exe -s -u admin:admin http://localhost:3000/api/datasources | ConvertFrom-Json
# Should show Prometheus with url: http://aether-prom:9090
```

**Check 4: Generate data**
```powershell
.\scripts\tenant-smoke-test.ps1
# Wait 30 seconds for scrape interval
# Refresh dashboard
```

### Problem: Alerts not firing

**Check 1: Alert rules loaded**
```powershell
# Check Prometheus loaded the rules
curl.exe -s http://localhost:9090/api/v1/rules | ConvertFrom-Json
# Should show aetherlink_rag.rules group
```

**Check 2: Manually trigger alert**
```powershell
# Generate low confidence answers
for ($i=0; $i -lt 20; $i++) {
  curl.exe -s -H "X-API-Key: $env:API_KEY_EXPERTCO" "http://localhost:8000/answer?q=gibberish$i" | Out-Null
}

# Wait 10 minutes for HighLowConfidenceRate alert
# Check: http://localhost:9090/alerts
```

**Check 3: Reload rules**
```powershell
# Hot reload without restart
curl.exe -X POST http://localhost:9090/-/reload
```

---

## 📊 Manual Verification Queries

### Cache Effectiveness by Tenant
```promql
sum(rate(aether_rag_cache_hits_total[5m])) by (tenant)
/
(sum(rate(aether_rag_cache_hits_total[5m])) by (tenant) + sum(rate(aether_rag_cache_misses_total[5m])) by (tenant))
```

### Answer Volume by Tenant (last 5 minutes)
```promql
sum(rate(aether_rag_answers_total[5m])) by (tenant)
```

### Low Confidence Rate
```promql
rate(aether_rag_lowconfidence_total[10m])
```

### Reranking Usage Percentage
```promql
sum(rate(aether_rag_answers_total{rerank="true"}[5m])) by (tenant)
/
sum(rate(aether_rag_answers_total[5m])) by (tenant)
```

---

## 🔧 Management Commands

### Restart Stack
```powershell
.\scripts\start-monitoring.ps1 -Restart
# Or: cd monitoring; docker compose restart
```

### Stop Stack
```powershell
.\scripts\start-monitoring.ps1 -Stop
# Or: cd monitoring; docker compose down
```

### View Logs
```powershell
.\scripts\start-monitoring.ps1 -Logs
# Or: cd monitoring; docker compose logs -f
```

### View Specific Service Logs
```powershell
docker logs aether-prom -f    # Prometheus
docker logs aether-grafana -f # Grafana
```

### Hot Reload Prometheus Config
```powershell
# After editing prometheus-config.yml or prometheus-alerts.yml
curl.exe -X POST http://localhost:9090/-/reload
```

### Reset Grafana (delete data)
```powershell
cd monitoring
docker compose down -v  # -v removes volumes
docker compose up -d
```

---

## ✅ Health Check Checklist

Run through this checklist to verify everything:

- [ ] **API Running:** `curl http://localhost:8000/health` returns healthy
- [ ] **Prometheus Running:** `curl http://localhost:9090/-/healthy` returns 200
- [ ] **Grafana Running:** `curl http://localhost:3000/api/health` returns ok
- [ ] **Target UP:** http://localhost:9090/targets shows `aetherlink_api` as UP
- [ ] **Metrics Present:** `curl http://localhost:8000/metrics | Select-String aether_rag` shows data
- [ ] **Tenant Labels:** `curl http://localhost:8000/metrics | Select-String tenant=` shows tenant-labeled metrics
- [ ] **Dashboard Loads:** http://localhost:3000 → AetherLink folder visible
- [ ] **Panels Show Data:** Select a tenant, see graphs populate
- [ ] **Alerts Loaded:** http://localhost:9090/alerts shows rules

---

## 🎯 Quick Test Sequence

```powershell
# 1. Start everything
.\scripts\start-monitoring.ps1

# 2. Generate test data
$env:API_ADMIN_KEY = "admin-secret-123"
.\scripts\tenant-smoke-test.ps1

# 3. Verify in Prometheus
Start-Process "http://localhost:9090/graph?g0.expr=sum(rate(aether_rag_answers_total%5B5m%5D))%20by%20(tenant)"

# 4. View in Grafana
Start-Process "http://localhost:3000/d/aetherlink_rag_tenant_metrics"

# 5. Check alerts
Start-Process "http://localhost:9090/alerts"
```

---

## 🔗 Related Documentation

- **Monitoring Setup:** `monitoring/README.md`
- **Smoke Test:** `scripts/tenant-smoke-test.ps1`
- **Verification Guide:** `TENANT_METRICS_VERIFY.md`
- **Dashboard JSON:** `monitoring/grafana-dashboard.json`
- **Alert Rules:** `monitoring/prometheus-alerts.yml`

---

## 💡 Pro Tips

1. **Persistent Data:** Monitoring data is stored in Docker volumes (`prometheus-data`, `grafana-data`)
2. **Hot Reload:** Use `curl -X POST http://localhost:9090/-/reload` to reload Prometheus config without restart
3. **Time Range:** Default dashboard range is 1 hour - expand if you need historical data
4. **Tenant Filter:** Use the tenant variable dropdown to focus on a specific customer
5. **Multi-Query:** Hold Shift in Prometheus graph to add multiple queries for comparison
6. **Export Dashboard:** Grafana UI → Dashboard Settings → JSON Model → Copy for backup

---

**All green?** You're monitoring like a pro! 🎉
