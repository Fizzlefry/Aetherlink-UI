# Tenant Metrics - Quick Verification Guide

## 🚀 Fast Verify Sequence (Copy-Paste)

### Automated Smoke Test (Recommended)
```powershell
# Set admin key (one time)
$env:API_ADMIN_KEY = "admin-secret-123"  # adjust to your actual admin key

# Run fully automated smoke test
.\scripts\tenant-smoke-test.ps1
```

**Or use VS Code Task:**  
`Ctrl+Shift+P` → Tasks: Run Task → **"Aether: Tenant Metrics Smoke Test"**

---

### Manual Verification (Step-by-Step)

```powershell
# 0) Make sure API is up
docker compose -f pods\customer_ops\docker-compose.yml ps
curl.exe -s http://localhost:8000/health

# 1) Grab a real editor API key that maps to a tenant
$env:API_ADMIN_KEY = "admin-secret-123"  # adjust if yours differs
$keys = curl.exe -s -H "x-admin-key: $env:API_ADMIN_KEY" http://localhost:8000/admin/apikeys | ConvertFrom-Json
$keys.items | Format-Table key,role,tenant_id

# 2) Export one of those editor keys to use as the "tenant"
$env:API_KEY_EXPERTCO = ($keys.items | Where-Object { $_.role -eq 'editor' } | Select-Object -First 1).key

# 3) Hit search/answer to bump the counters for that tenant
curl.exe -s -H "X-API-Key: $env:API_KEY_EXPERTCO" "http://localhost:8000/search?q=test&mode=hybrid" | Out-Null
curl.exe -s -H "X-API-Key: $env:API_KEY_EXPERTCO" "http://localhost:8000/answer?q=storm%20collar&mode=hybrid&rerank=true" | Out-Null
Start-Sleep -Seconds 1

# 4) Run your checker (or use VS Code task "Aether: Check Tenant Metrics")
.\scripts\quick-check-tenant-metrics.ps1

# 5) One-liner peek (optional)
curl.exe -s http://localhost:8000/metrics | Select-String 'aether_rag_.*tenant=' | Select-Object -First 8
```

---

## 🔍 Quick One-Liners

### Show All Tenant-Labeled Metrics
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String 'aether_rag_.*tenant='
```

### Per-Tenant Answers
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String 'aether_rag_answers_total\{.*tenant='
```

### Cache Metrics by Tenant
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String 'aether_rag_cache_.*tenant='
```

### Low Confidence by Tenant
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String 'lowconfidence_total\{tenant='
```

---

## 🐛 Troubleshooting

### If tenant labels still don't appear:

1. **Use a tenant API key (role: editor)**
   - Admin keys may fall back to `tenant="default"` depending on your auth code path
   - Get editor key: See step 1-2 in manual verification above

2. **Restart API to load new code**
   ```powershell
   docker compose -f pods\customer_ops\docker-compose.yml restart api
   Start-Sleep -Seconds 3
   ```

3. **Confirm label wiring in code**
   - Cache counters: `.labels(endpoint=..., tenant=tenant_id ?? "default").inc()`
   - Answer counters: `.labels(mode=..., rerank=..., tenant=...)`
   - Check: `pods/customer_ops/api/main.py` (search for `.labels(.*tenant=`)

4. **Verify auth middleware attaches tenant_id**
   - Ensure `tenant_id` is attached to `request.state` (or equivalent)
   - This happens in your `ApiKeyRequired` dependency when `X-API-Key` is present

5. **Check metrics endpoint is accessible**
   ```powershell
   curl.exe -s http://localhost:8000/metrics | Select-String "aether_rag"
   ```

---

## 📊 Prometheus/Grafana Queries

### Per-Tenant Answer Volume (Last 5m)
```promql
sum(rate(aether_rag_answers_total[5m])) by (tenant)
```

### Per-Tenant Cache Hit Ratio (Answer Endpoint)
```promql
sum(rate(aether_rag_cache_hits_total{endpoint="answer"}[5m])) by (tenant)
/ ignoring(endpoint) 
(sum(rate(aether_rag_cache_hits_total{endpoint="answer"}[5m])) by (tenant)
 + sum(rate(aether_rag_cache_misses_total{endpoint="answer"}[5m])) by (tenant))
```

### Per-Tenant Cache Hit Ratio (All Endpoints)
```promql
sum(rate(aether_rag_cache_hits_total[5m])) by (tenant)
/
(sum(rate(aether_rag_cache_hits_total[5m])) by (tenant) 
 + sum(rate(aether_rag_cache_misses_total[5m])) by (tenant))
```

### Low Confidence Rate by Tenant
```promql
rate(aether_rag_lowconfidence_total[15m])
```

### Answers by Mode and Tenant
```promql
sum(rate(aether_rag_answers_total[5m])) by (tenant, mode)
```

### Reranking Usage by Tenant
```promql
sum(rate(aether_rag_answers_total{rerank="true"}[5m])) by (tenant)
```

### Top 5 Tenants by Cache Misses
```promql
topk(5, sum(rate(aether_rag_cache_misses_total[5m])) by (tenant))
```

### Total Requests per Tenant (Cache Activity)
```promql
sum(rate(aether_rag_cache_hits_total[5m]) + rate(aether_rag_cache_misses_total[5m])) by (tenant)
```

---

## 🎯 Grafana Dashboard Variables

Create a dashboard with tenant selector:

```yaml
# Variable: tenant
Type: Query
Query: label_values(aether_rag_answers_total, tenant)
Refresh: On Dashboard Load
```

Then use in panels:
```promql
# Answer rate for selected tenant
rate(aether_rag_answers_total{tenant="$tenant"}[5m])

# Cache efficiency for selected tenant
sum(rate(aether_rag_cache_hits_total{tenant="$tenant"}[5m])) 
/ (sum(rate(aether_rag_cache_hits_total{tenant="$tenant"}[5m])) 
   + sum(rate(aether_rag_cache_misses_total{tenant="$tenant"}[5m])))
```

---

## ✅ VS Code Tasks Available

1. **Aether: Tenant Metrics Smoke Test** ⭐ (Fully automated)
   - Auto-fetches editor API key
   - Makes test requests
   - Shows tenant-labeled metrics
   - No env setup required (just API_ADMIN_KEY)

2. **Aether: Check Tenant Metrics** (Manual with env key)
   - Uses `$env:API_KEY_EXPERTCO` or `$env:API_ADMIN_KEY`
   - Quick metrics check
   - Requires pre-set API key

3. **Aether: Validate Quick Wins** (Full validation suite)
   - 11 standard tests
   - Add `-Strict` for 3 red team tests

4. **Aether: Setup ► Validate (Chained)** (E2E test)
   - Ingests sample data
   - Runs full validation
   - Shows metrics snapshot

---

## 🎉 Expected Output (Smoke Test)

```
========================================
  TENANT METRICS SMOKE TEST
========================================

[1/6] Checking API health...
  ✓ API is healthy

[2/6] Fetching editor API key...
  ✓ Found editor key for tenant: expertco
    Key: xk-expertco-...

[3/6] Making search request...
  ✓ Search request completed

[4/6] Making answer request...
  ✓ Answer request completed

[5/6] Fetching metrics...
  ✓ Found tenant-labeled metrics

[6/6] Tenant Metrics Summary:
  Tenant: expertco
  ----------------------------------------

  Cache Hits:
    aether_rag_cache_hits_total{endpoint="search",tenant="expertco"} 5.0

  Cache Misses:
    aether_rag_cache_misses_total{endpoint="search",tenant="expertco"} 12.0

  Answers:
    aether_rag_answers_total{mode="hybrid",rerank="true",tenant="expertco"} 2.0

========================================
  ✓ SMOKE TEST PASSED
========================================
```

---

## 📝 Quick Validation Checklist

- [ ] API is healthy: `curl.exe -s http://localhost:8000/health`
- [ ] Admin key is set: `$env:API_ADMIN_KEY = "..."`
- [ ] Smoke test passes: `.\scripts\tenant-smoke-test.ps1`
- [ ] Tenant labels appear in metrics
- [ ] Different API keys show different tenant values
- [ ] Cache metrics have tenant dimension
- [ ] Answer metrics include tenant, mode, rerank
- [ ] Low confidence metrics have tenant label

**All green?** You're ready for production! 🚀

---

## 🔗 Related Documentation

- **Implementation Guide:** `TENANT_METRICS_COMPLETE.md`
- **Usage Examples:** `TENANT_METRICS_USAGE.md`
- **Performance Docs:** `PERFORMANCE_QUICK_WINS.md`
- **Validation Suite:** `scripts/validate-quick-wins.ps1 -?`
