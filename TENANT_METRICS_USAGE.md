# Quick Tenant Metrics Checker - Ready to Use!

## ✅ What's Installed

### 1. PowerShell Script (UTF-8 Safe)
**Location:** `scripts/quick-check-tenant-metrics.ps1`

**Features:**
- ASCII-encoded (no weird character issues)
- Automatically falls back to API_ADMIN_KEY if API_KEY_EXPERTCO not set
- Color-coded output
- Optional tenant filtering

### 2. VS Code Task
**Task Name:** "Aether: Check Tenant Metrics"  
**Access:** `Ctrl+Shift+P` → "Tasks: Run Task" → "Aether: Check Tenant Metrics"

## 🚀 Usage

### Option 1: Run Script Directly
```powershell
# Basic usage
$env:API_KEY_EXPERTCO = "your-key-here"
.\scripts\quick-check-tenant-metrics.ps1

# With tenant filter
.\scripts\quick-check-tenant-metrics.ps1 -TenantLabelFilter 'tenant="expertco"'

# Custom API URL
.\scripts\quick-check-tenant-metrics.ps1 -BaseUrl "http://localhost:8001"
```

### Option 2: VS Code Task (One Click)
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Select "Aether: Check Tenant Metrics"
4. View output in integrated terminal

### Option 3: Quick One-Liners

**Kick request and check labels:**
```powershell
curl.exe -s -H "X-API-Key: xk-test-1234" "http://localhost:8000/search?q=test&mode=hybrid" | Out-Null
Start-Sleep -Seconds 1
curl.exe -s "http://localhost:8000/metrics" | Select-String 'aether_rag_.*tenant=' | Select-Object -First 8
```

**Show per-tenant answers:**
```powershell
curl.exe -s "http://localhost:8000/metrics" | Select-String 'aether_rag_answers_total\{.*tenant='
```

**Show cache metrics by tenant:**
```powershell
curl.exe -s "http://localhost:8000/metrics" | Select-String 'aether_rag_cache_.*tenant='
```

## 🔍 Expected Output

### When Working:
```
Nudging API to generate metrics...
Fetching metrics...

========== TENANT METRICS ==========
aether_rag_cache_misses_total{endpoint="search",tenant="expertco"} 5.0
aether_rag_cache_hits_total{endpoint="search",tenant="expertco"} 12.0
aether_rag_answers_total{mode="hybrid",rerank="true",tenant="expertco"} 8.0
====================================
```

### When No Metrics:
```
========== TENANT METRICS ==========
No tenant-labeled metrics found.
Check that requests include an API key that resolves to a tenant_id.
====================================
```

## 🐛 Troubleshooting

### If tenant labels don't show up:

1. **Verify API is restarted with new code:**
   ```powershell
   docker compose restart api
   Start-Sleep -Seconds 3
   ```

2. **Make sure you're using a real API key:**
   ```powershell
   # Check environment
   $env:API_KEY_EXPERTCO
   $env:API_ADMIN_KEY
   
   # Admin keys may label as tenant="default" depending on your auth logic
   ```

3. **Confirm the auth dependency attaches tenant_id:**
   - Check that `request.state.tenant_id` is set in ApiKeyRequired dependency
   - Verify it's passed to cache functions: `_cache_get("search", cache_key, tenant=tenant_id)`

4. **Check metrics endpoint is accessible:**
   ```powershell
   curl.exe -s "http://localhost:8000/metrics" | Select-String "aether_rag"
   ```

5. **Verify code changes were applied:**
   - Check `pods/customer_ops/api/main.py` for tenant labels in Counter definitions
   - Look for `.labels(endpoint=..., tenant=...)` calls

## 📊 Complete Test Suite

### Run All Validations:
```powershell
# Standard quick-wins tests (11 tests)
.\scripts\validate-quick-wins.ps1

# With red team security tests (14 tests total)
.\scripts\validate-quick-wins.ps1 -Strict

# Check tenant metrics
.\scripts\quick-check-tenant-metrics.ps1
```

### VS Code Task Sequence:
1. **Aether: Setup Sample Data + Validate** - Full E2E test
2. **Aether: Check Tenant Metrics** - Verify labels
3. **Aether: Teardown Sample Data** - Clean up

## 🎯 What to Look For

### Success Indicators:
✅ Metrics show `tenant="<your-tenant>"` labels  
✅ Different API keys produce different tenant labels  
✅ Cache hits/misses tracked separately per tenant  
✅ ANSWERS_TOTAL includes tenant dimension  
✅ LOWCONF_TOTAL has tenant label  

### Prometheus Query Examples:
```promql
# Cache hit rate per tenant
rate(aether_rag_cache_hits_total{tenant="acme"}[5m]) 
/ rate(aether_rag_cache_misses_total{tenant="acme"}[5m])

# Answer volume by tenant
rate(aether_rag_answers_total{tenant="expertco"}[1h])

# Low confidence rate per tenant
rate(aether_rag_lowconfidence_total{tenant="vip"}[15m])
```

## ✨ Next Steps

1. **Create Grafana Dashboard** with tenant selector
2. **Set up Prometheus Alerts** for per-tenant SLAs
3. **Monitor in Production** - track usage patterns by customer
4. **Bill by Usage** - use metrics for cost allocation

All set! 🚀
