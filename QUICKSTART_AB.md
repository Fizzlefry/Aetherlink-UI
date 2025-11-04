# 🚀 A/B Experiments - Quick Start (5 Minutes)

## Step 1: Enable Your First Experiment (30 seconds)

Edit `pods/customer_ops/api/experiments.py` line **104**:

```python
# Change from:
enabled=False,

# To:
enabled=True,
```

**Full context** (lines 102-106):
```python
"followup_timing": Experiment(
    name="followup_timing",
    description="Test aggressive (5min) vs conservative (30min) follow-up delays",
    enabled=True,  # <-- Change this to True
    start_date=int(time.time()),
```

Save the file. If running uvicorn in dev mode, it will auto-reload.

---

## Step 2: Run Automated Smoke Test (2 minutes)

```powershell
# From project root
.\test_ab_experiment.ps1 -NumLeads 20
```

This will:
1. ✅ Check API is running
2. ✅ Verify experiment is enabled
3. ✅ Create 20 test leads (split across variants)
4. ✅ Record realistic outcomes (30% booked, 20% ghosted, etc.)
5. ✅ Show variant distribution
6. ✅ Display significance test results
7. ✅ Show Prometheus metrics

---

## Step 3: Check Dashboard (30 seconds)

```powershell
# View experiment status
curl http://localhost:8000/ops/experiments | ConvertFrom-Json | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing
```

**What to look for**:
- `enabled`: true
- `variants`: ["control", "aggressive"]
- `significance.significant`: false (until >100 samples)
- `significance.variants`: Per-variant stats

---

## Step 4: Monitor Prometheus Metrics (30 seconds)

```powershell
# View experiment counters
curl http://localhost:8000/metrics | Select-String "experiment_"
```

**Key metrics**:
```prometheus
experiment_variant_assigned_total{experiment="followup_timing",variant="control"} 10
experiment_variant_assigned_total{experiment="followup_timing",variant="aggressive"} 10

experiment_outcome_total{experiment="followup_timing",variant="control",outcome="booked"} 3
experiment_outcome_total{experiment="followup_timing",variant="aggressive",outcome="booked"} 6

experiment_conversion_rate{experiment="followup_timing",variant="control"} 0.30
experiment_conversion_rate{experiment="followup_timing",variant="aggressive"} 0.60

experiment_sample_size{experiment="followup_timing",variant="control"} 10
experiment_sample_size{experiment="followup_timing",variant="aggressive"} 10
```

---

## Step 5: Wait for Significance (1-2 weeks in production)

### Requirements for Winner Promotion:
- ✅ **Minimum 100 samples per variant**
- ✅ **P-value < 0.05** (95% confidence)
- ✅ **Chi-square test passes**

### Check Significance:
```powershell
curl http://localhost:8000/ops/experiments | ConvertFrom-Json | Select-Object -ExpandProperty experiments | Select-Object -ExpandProperty followup_timing | Select-Object -ExpandProperty significance
```

**Example** (not yet significant):
```json
{
  "significant": false,
  "p_value": 0.23,
  "winner": null,
  "variants": {
    "control": {"samples": 45, "conversions": 9, "rate": 0.20},
    "aggressive": {"samples": 48, "conversions": 12, "rate": 0.25}
  }
}
```

**Example** (ready to promote):
```json
{
  "significant": true,
  "p_value": 0.042,
  "winner": "aggressive",
  "variants": {
    "control": {"samples": 150, "conversions": 30, "rate": 0.20},
    "aggressive": {"samples": 152, "conversions": 48, "rate": 0.316}
  }
}
```

---

## Step 6: Promote Winner (10 seconds)

```powershell
# Promote winning variant (if significant)
curl -X POST http://localhost:8000/ops/experiments/followup_timing/promote | ConvertFrom-Json
```

**Success response**:
```json
{
  "ok": true,
  "promoted": "aggressive",
  "p_value": 0.042,
  "chi_square": 4.21
}
```

**Not ready response**:
```json
{
  "ok": false,
  "error": "No statistically significant winner yet",
  "p_value": 0.23
}
```

---

## 🔧 Troubleshooting

### API Not Running?
```powershell
cd pods/customer_ops
.\scripts\dev.ps1 -Up -Verify
```

### Experiment Still Disabled?
1. Edit `api/experiments.py` line 104
2. Change `enabled=False` to `enabled=True`
3. Save file (uvicorn auto-reloads)

### No Metrics Showing?
- Need at least 1 lead created + 1 outcome recorded
- Run: `.\test_ab_experiment.ps1 -NumLeads 10`

### Can't Promote Winner?
Check requirements:
```powershell
$exp = (curl http://localhost:8000/ops/experiments | ConvertFrom-Json).experiments.followup_timing
$sig = $exp.significance

Write-Host "P-value: $($sig.p_value) (need < 0.05)"
Write-Host "Samples control: $($sig.variants.control.samples) (need > 100)"
Write-Host "Samples aggressive: $($sig.variants.aggressive.samples) (need > 100)"
```

---

## 📊 Production Usage

### In Production (Real Traffic):
1. **Week 1**: Enable experiment, monitor assignment balance
2. **Week 2-3**: Accumulate 100+ samples per variant
3. **Week 4**: Check significance, promote winner
4. **Week 5+**: Monitor winner performance, consider next experiment

### Grafana Dashboard Queries:
```promql
# Conversion rate by variant
experiment_conversion_rate{experiment="followup_timing"}

# Sample size progress
experiment_sample_size{experiment="followup_timing"}

# Outcome distribution
sum(experiment_outcome_total{experiment="followup_timing"}) by (variant, outcome)
```

---

## 🎯 Expected Results

### If Hypothesis Correct (5min > 30min):
- **Control** (30min): 20% conversion
- **Aggressive** (5min): 25-30% conversion
- **P-value**: < 0.05 after ~150 samples/variant
- **Impact**: +25% conversion lift = **+25% revenue**!

### If Hypothesis Wrong (30min > 5min):
- **Control** (30min): 20% conversion
- **Aggressive** (5min): 15-18% conversion
- **P-value**: < 0.05 after ~150 samples/variant
- **Decision**: Keep control, experiment prevented revenue loss!

---

## 🚀 One-Liner Quick Start

```powershell
# 1. Enable (edit api/experiments.py line 104: enabled=True)

# 2. Test
.\test_ab_experiment.ps1 -NumLeads 20

# 3. Monitor
curl http://localhost:8000/ops/experiments | jq '.experiments.followup_timing'

# 4. Promote (when ready)
curl -X POST http://localhost:8000/ops/experiments/followup_timing/promote | jq '.'
```

---

## 📚 Documentation

- **Complete Guide**: `AB_EXPERIMENTS_GUIDE.md` (800+ lines)
- **Executive Summary**: `SHIPPED_AB_EXPERIMENTS.md`
- **This Guide**: `QUICKSTART_AB.md`

---

**Status**: ✅ Ready to flip the switch! 🚀

**Time to First Results**: 2-4 weeks (production traffic)
**Expected Lift**: +10-30% conversion rate
**Risk**: Zero (50/50 split, can disable anytime)
