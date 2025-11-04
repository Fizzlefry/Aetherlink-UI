# 🔧 A/B Experiments - Troubleshooting Guide

## Quick Diagnostics

### 1. Check All Services Status
```powershell
# API
try { Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing | Select-Object StatusCode } catch { Write-Host "❌ API DOWN" }

# Redis
docker ps --filter "name=aether-redis"

# Experiment enabled?
Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing | Select-Object enabled
```

---

## Common Issues & Fixes

### ❌ API won't start - Import errors
**Error**: `ModuleNotFoundError: No module named 'backoff'` or similar

**Fix**:
```powershell
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
.\.venv\Scripts\pip.exe install -r pods\customer_ops\requirements.txt
.\.venv\Scripts\pip.exe install backoff scikit-learn scipy numpy
```

**Verify**:
```powershell
.\.venv\Scripts\python.exe -c "import backoff, sklearn, scipy; print('✅ OK')"
```

---

### ❌ API won't start - Import path error
**Error**: `ImportError: attempted relative import beyond top-level package`

**Fix**: Ensure `PYTHONPATH` is set to repo root:
```powershell
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT
$env:PYTHONPATH = $ROOT
.\.venv\Scripts\python.exe -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### ❌ Port 8000 already in use
**Error**: `[Errno 10048] Only one usage of each socket address...`

**Find the process**:
```powershell
netstat -ano | findstr :8000
```

**Kill it**:
```powershell
# If PID is 12345:
taskkill /PID 12345 /F
```

---

### ❌ Redis not reachable
**Error**: `redis.exceptions.ConnectionError: Error connecting to localhost:6379`

**Check if running**:
```powershell
docker ps --filter "name=aether-redis"
```

**Restart**:
```powershell
docker rm -f aether-redis
docker run -d --name aether-redis -p 6379:6379 redis:7
```

**Verify**:
```powershell
docker logs aether-redis
```

---

### ❌ Execution policy blocks scripts
**Error**: `File cannot be loaded because running scripts is disabled on this system`

**Fix (temporary - current session only)**:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
```

**Fix (permanent - requires admin)**:
```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### ❌ Experiment shows enabled=False
**Check the file**:
```powershell
Select-String -Path "pods\customer_ops\api\experiments.py" -Pattern "followup_timing" -Context 0,5
```

**Manual edit**:
1. Open: `pods\customer_ops\api\experiments.py`
2. Find line ~104: `"followup_timing": Experiment(`
3. Change: `enabled=False` → `enabled=True`
4. Save (uvicorn auto-reloads)

**Verify**:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing | Select-Object enabled, variants
```

---

### ❌ No variants being assigned
**Symptom**: All leads show same behavior, no metrics incrementing

**Checklist**:
1. ✅ Experiment enabled? (see above)
2. ✅ API reloaded? Try: `Invoke-RestMethod -Method POST -Uri "http://localhost:8000/ops/experiments/followup_timing/promote"`
3. ✅ Creating leads via correct endpoint? Must use `/v1/lead` endpoint
4. ✅ Check metrics:
   ```powershell
   Invoke-WebRequest -Uri "http://localhost:8000/metrics" | Select-Object -ExpandProperty Content | Select-String "experiment_variant_assigned"
   ```

---

### ❌ No Prometheus metrics showing
**Symptom**: `/metrics` returns empty or missing experiment counters

**Causes**:
- No leads created yet → Create at least 1 lead
- Experiment not enabled → Check experiments.py
- No outcomes recorded → Record at least 1 outcome

**Test**:
```powershell
# Create a test lead
$body = @{
    phone = "+15555551234"
    enrichment_text = "Test lead for metrics"
    tenant_id = "test_tenant"
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/lead" -Body $body -ContentType "application/json" -Headers @{"X-API-Key"="test-key-123"}

# Check metrics
Invoke-WebRequest -Uri "http://localhost:8000/metrics" | Select-Object -ExpandProperty Content | Select-String "experiment_"
```

---

### ❌ Model warnings/errors
**Warning**: `Model not trained` or `Model file not found`

**Fix**: Train initial model (creates synthetic data):
```powershell
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT
$env:PYTHONPATH = $ROOT
.\.venv\Scripts\python.exe pods\customer_ops\scripts\train_model.py
```

**Verify**:
```powershell
Test-Path "pods\customer_ops\api\model.json"
```

**Note**: API will fail-open if model missing (still functional, just no predictions)

---

### ❌ Worker not processing follow-ups
**Symptom**: Follow-ups scheduled but never execute

**Check worker is running**:
```powershell
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Where-Object { $_.CommandLine -like "*worker.py*" }
```

**Start worker**:
```powershell
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT
$env:PYTHONPATH = $ROOT
$env:REDIS_URL = "redis://localhost:6379/0"
.\.venv\Scripts\python.exe pods\customer_ops\worker.py
```

**Check queue**:
```powershell
# In Python
.\.venv\Scripts\python.exe -c @"
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
print(f'Queue length: {r.llen(\"followup_queue\")}')
"@
```

---

### ❌ test_ab_experiment.ps1 fails
**Common causes**:

1. **API not running**:
   ```powershell
   try { Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing } catch { Write-Host "❌ Start API first!" }
   ```

2. **Experiment not enabled**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing | Select-Object enabled
   ```

3. **Invalid API key**: Check if your API requires authentication

4. **Tenant isolation**: Ensure consistent `tenant_id` across requests

---

### ❌ Can't promote winner
**Error**: `No statistically significant winner yet`

**Requirements**:
- ✅ P-value < 0.05 (95% confidence)
- ✅ Minimum sample size (default: 100 per variant)
- ✅ Chi-square test passes

**Check status**:
```powershell
$exp = Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing
$sig = $exp.significance

Write-Host "P-value: $($sig.p_value) (need < 0.05)"
Write-Host "Samples control: $($sig.variants.control.samples) (need ≥ 100)"
Write-Host "Samples aggressive: $($sig.variants.aggressive.samples) (need ≥ 100)"
Write-Host "Significant: $($sig.significant)"
Write-Host "Winner: $($sig.winner)"
```

**Workaround for testing** (not recommended for production):
- Temporarily lower `min_sample_size` in `experiments.py`
- Or wait for real traffic to accumulate

---

## Health Check Endpoints

```powershell
# Basic health
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# Model status
Invoke-RestMethod -Uri "http://localhost:8000/ops/model-status" | ConvertTo-Json

# Experiment dashboard
Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | ConvertTo-Json -Depth 10

# Prometheus metrics
Invoke-WebRequest -Uri "http://localhost:8000/metrics" | Select-Object -ExpandProperty Content
```

---

## Reset Everything (Nuclear Option)

```powershell
# Stop all services
Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force
Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*worker.py*" } | Stop-Process -Force

# Remove Redis container
docker rm -f aether-redis

# Clean Python cache
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Remove-Item -Recurse -Force pods\customer_ops\api\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force pods\customer_ops\api\*.pyc -ErrorAction SilentlyContinue

# Re-run setup
.\setup_and_run_ab.ps1
```

---

## Still Stuck?

### Collect diagnostic info:
```powershell
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT

Write-Host "=== Python Version ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe --version

Write-Host "`n=== Installed Packages ===" -ForegroundColor Cyan
.\.venv\Scripts\pip.exe list | Select-String "fastapi|uvicorn|redis|backoff|sklearn|scipy"

Write-Host "`n=== Docker Status ===" -ForegroundColor Cyan
docker ps

Write-Host "`n=== Port 8000 Status ===" -ForegroundColor Cyan
netstat -ano | findstr :8000

Write-Host "`n=== Experiment File Check ===" -ForegroundColor Cyan
Select-String -Path "pods\customer_ops\api\experiments.py" -Pattern "followup_timing.*enabled" -Context 0,2

Write-Host "`n=== API Health ===" -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing | Select-Object StatusCode, Content
} catch {
    Write-Host "❌ API not responding: $($_.Exception.Message)"
}
```

### Share the output for debugging!

---

## Quick Reference

| Issue | Command |
|-------|---------|
| Restart API | Kill python.exe, re-run uvicorn command |
| Restart Redis | `docker restart aether-redis` |
| Check logs | Check uvicorn terminal / worker terminal |
| View metrics | `http://localhost:8000/metrics` |
| View dashboard | `http://localhost:8000/ops/experiments` |
| Enable experiment | Edit `experiments.py` line 104 → `enabled=True` |
| Promote winner | `POST http://localhost:8000/ops/experiments/followup_timing/promote` |

---

**💡 Pro Tip**: Keep uvicorn and worker terminals open in separate windows so you can see real-time logs!
