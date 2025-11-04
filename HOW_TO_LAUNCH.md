# 🚀 A/B Experiments - Launch Instructions

## Quick Start (Recommended)

### Option 1: One-Command Launch (Easiest!)
```powershell
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
.\LAUNCH_AB_SYSTEM.ps1
```

This will:
- ✅ Start Redis
- ✅ Install dependencies
- ✅ Open API window (green)
- ✅ Open Worker window (magenta)
- ✅ Run validation automatically

**Then wait for "Ready to run validation!" and press ENTER.**

---

### Option 2: Manual Step-by-Step

If you want more control, run these in order:

#### **Window 1: Control** (your current window)
```powershell
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
.\preflight_control.ps1          # Preflight checks
.\step1_model.ps1                # Optional: Train model
```

#### **Window 2: API Server** (open new PowerShell)
```powershell
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
.\step2_api.ps1                  # Start API (keep open!)
```

#### **Window 3: RQ Worker** (open new PowerShell)
```powershell
cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
.\step3_worker.ps1               # Start worker (keep open!)
```

#### **Back to Window 1: Run Validation**
```powershell
.\step4_7_validation.ps1         # Validate & smoke test
```

---

## What You'll See

### ✅ Successful Launch

**API Window** (green header):
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
INFO:     Application startup complete.
```

**Worker Window** (magenta header):
```
INFO: Starting RQ worker...
INFO: Worker connected to redis://localhost:6379/0
INFO: Watching queue: followup_queue
```

**Control Window** (validation output):
```
✅ Step 0: API is healthy
✅ Step 2: Experiment 'followup_timing' is ENABLED
   Variants: control (50.0%), aggressive (50.0%)

🔄 Step 3: Creating 20 test leads...
   ✅ Distribution: control=10, aggressive=10

📊 Step 5: Experiment Stats:
   Control:    10 samples, 3 conversions (30.0%)
   Aggressive: 10 samples, 6 conversions (60.0%)
   P-value: 0.23 (not significant - need 100+ samples)

✅ System is LIVE and collecting A/B data!
```

---

## What to Share Back

After running validation, copy and paste these 3 outputs:

### 1. Last ~10 lines of smoke test
```powershell
# Should show variant distribution and p-value
```

### 2. Experiment JSON
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" | ConvertTo-Json -Depth 10
```

### 3. Experiment Metrics
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/metrics" | Select-Object -ExpandProperty Content | Select-String "experiment_variant_assigned_total|experiment_outcome_total|experiment_conversion_rate"
```

---

## Troubleshooting

### ❌ API won't start
- Check API window for import errors
- Ensure: `$env:PYTHONPATH = $ROOT` is set
- Verify: `.\.venv\Scripts\python.exe -c "import backoff"`

### ❌ Port 8000 in use
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### ❌ Redis not reachable
```powershell
docker ps --filter "name=aether-redis"
docker restart aether-redis
```

### 📚 Full Troubleshooting Guide
See: **TROUBLESHOOTING_AB.md**

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `.\LAUNCH_AB_SYSTEM.ps1` | One-command launch (easiest) |
| `.\step4_7_validation.ps1` | Run validation after manual setup |
| `.\test_ab_experiment.ps1 -NumLeads 20` | Smoke test only |
| `http://localhost:8000/ops/experiments` | Dashboard |
| `http://localhost:8000/metrics` | Prometheus metrics |

---

## Files Created

✅ **LAUNCH_AB_SYSTEM.ps1** - Master launcher (recommended)
✅ **preflight_control.ps1** - Preflight checks
✅ **step1_model.ps1** - Model training
✅ **step2_api.ps1** - API server
✅ **step3_worker.ps1** - RQ worker
✅ **step4_7_validation.ps1** - Validation & smoke test
✅ **test_ab_experiment.ps1** - Smoke test (standalone)
✅ **TROUBLESHOOTING_AB.md** - Complete troubleshooting guide

---

## 🎯 You're Ready!

**Recommended**: Just run `.\LAUNCH_AB_SYSTEM.ps1` and you're done! 🚀
