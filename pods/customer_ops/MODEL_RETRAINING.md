# Model Retraining Pipeline 🔄

**Status**: ✅ Shipped  
**Impact**: Automated nightly model retraining with hot-reload (zero downtime)  
**Architecture**: GitHub Actions + `/ops/reload-model` endpoint + Prometheus monitoring  

---

## Overview

The Model Retraining Pipeline automatically improves prediction accuracy by:
1. **Exporting** outcome data nightly from production API
2. **Training** a new model with latest conversion signals
3. **Deploying** via hot-reload (no API restart required)
4. **Monitoring** model performance with Prometheus alerts

**Key Benefits**:
- 🔄 **Always Learning**: Model improves as more outcomes are recorded
- ⚡ **Zero Downtime**: Hot-reload without restarting API
- 📊 **Observable**: Prometheus metrics track AUC, version, training size
- 🚨 **Alerting**: Automatic alerts on model degradation
- 🤖 **Hands-Off**: Runs nightly at 03:17 UTC automatically

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  GitHub Actions (Nightly 03:17 UTC)                      │
│  ├─ 1. Export outcomes.csv from /ops/export/outcomes.csv │
│  ├─ 2. Train model (scripts/train_model.py)             │
│  ├─ 3. Validate model.json                              │
│  ├─ 4. Upload artifact                                   │
│  └─ 5. Hot-reload via POST /ops/reload-model            │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  API (predict.py)     │
              │  - Clear _MODEL cache │
              │  - Load new model.json│
              │  - Update metrics     │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Prometheus Metrics   │
              │  - lead_model_auc     │
              │  - lead_model_version │
              │  - lead_model_n_train │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Alerting (optional)  │
              │  - AUC < 0.65         │
              │  - Latency > 100ms    │
              └───────────────────────┘
```

---

## Components

### 1. GitHub Actions Workflow (`.github/workflows/model_retrain.yml`)

Automated nightly retraining job:

```yaml
name: nightly-model-retrain
on:
  schedule:
    - cron: "17 3 * * *"   # 03:17 UTC nightly
  workflow_dispatch: {}    # Manual trigger
```

**Steps**:
1. Export outcomes from API (`/ops/export/outcomes.csv`)
2. Train model (`scripts/train_model.py`)
3. Validate `model.json`
4. Upload artifact
5. Hot-reload via `/ops/reload-model`
6. Optionally commit updated model to repo

**Required Secrets**:
- `API_BASE`: Production/staging API URL (e.g., `https://api.example.com`)
- `API_KEY`: Optional API key if `/ops` routes require auth

### 2. Hot-Reload Endpoint (`/ops/reload-model`)

Zero-downtime model deployment:

```python
@app.post("/ops/reload-model", tags=["ops"])
def reload_model_endpoint():
    """Hot-reload prediction model from disk."""
    from .predict import reload_model
    result = reload_model()  # Clears cache, loads new model.json
    return result  # {"ok": True, "version": ..., "auc": ..., "n_train": ...}
```

**Usage**:
```bash
curl -X POST https://api.example.com/ops/reload-model \
  -H "x-api-key: your-api-key"
```

**Response**:
```json
{
  "ok": true,
  "version": 1730483820,
  "auc": 0.78,
  "n_train": 523,
  "load_time": 1730483825.123
}
```

### 3. Model Metrics (`api/predict.py`)

Prometheus gauges for monitoring:

```python
MODEL_AUC = Gauge("lead_model_auc", "Model AUC score from training")
MODEL_VERSION = Gauge("lead_model_version", "Model version timestamp")
MODEL_N_TRAIN = Gauge("lead_model_n_train", "Number of training samples")
```

**Updated on**:
- Initial model load (startup)
- Hot-reload via `/ops/reload-model`

### 4. Prometheus Alerts (`deploy/prometheus_alerts.yml`)

Automated monitoring rules:

```yaml
- alert: LeadModelAUCDegraded
  expr: lead_model_auc < 0.65
  for: 30m
  severity: warning
  
- alert: LeadModelAUCCritical
  expr: lead_model_auc < 0.55
  for: 10m
  severity: critical
  
- alert: LeadPredLatencyHigh
  expr: (rate(lead_pred_latency_seconds_sum[5m]) / ...) > 0.1
  for: 10m
  severity: warning
```

### 5. Backfill Script (`scripts/scrub_history.py`)

One-time script to redact PII in legacy conversation history:

```bash
cd pods/customer_ops
REDIS_URL=redis://localhost:6379/0 python scripts/scrub_history.py --dry-run
```

---

## Configuration

### GitHub Secrets

Add to repository settings → Secrets and variables → Actions:

| Secret | Value | Example |
|--------|-------|---------|
| `API_BASE` | Production/staging API URL | `https://api.example.com` |
| `API_KEY` | API key for /ops endpoints | `prod-key-abc123` (optional) |

### Workflow Schedule

Default: **03:17 UTC** daily

To change:
```yaml
on:
  schedule:
    - cron: "30 2 * * *"  # 02:30 UTC instead
```

### Manual Trigger

Run retraining on-demand:
1. Go to GitHub Actions → `nightly-model-retrain`
2. Click "Run workflow" → "Run workflow"
3. Monitor logs for export → train → deploy steps

---

## Operations

### Monitor Retraining

**GitHub Actions**:
- https://github.com/YOUR_ORG/AetherLink/actions/workflows/model_retrain.yml
- Check run history, logs, artifacts

**Prometheus Metrics**:
```promql
# Current model AUC
lead_model_auc

# Model version (timestamp)
lead_model_version

# Training sample count
lead_model_n_train

# Last update time
changes(lead_model_version[1h])  # Should be 1 after retraining
```

**API Endpoint**:
```bash
# Check current model info
curl https://api.example.com/metrics | grep lead_model
```

### Manual Retraining

If workflow fails or you need immediate retrain:

```bash
# 1. Export outcomes
curl https://api.example.com/ops/export/outcomes.csv > outcomes.csv

# 2. Train model locally
cd pods/customer_ops
python scripts/train_model.py --input outcomes.csv --output api/model.json

# 3. Deploy via hot-reload
curl -X POST https://api.example.com/ops/reload-model \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d @api/model.json
```

### Rollback Model

If new model performs poorly:

```bash
# 1. Download previous artifact from GitHub Actions
# (Go to previous successful run → Artifacts → Download)

# 2. Replace model.json
cp customer-ops-model-123.json pods/customer_ops/api/model.json

# 3. Hot-reload
curl -X POST https://api.example.com/ops/reload-model -H "x-api-key: your-key"
```

### Disable Retraining

Temporarily pause automated retraining:

```yaml
# In .github/workflows/model_retrain.yml
on:
  # schedule:
  #   - cron: "17 3 * * *"  # Commented out
  workflow_dispatch: {}      # Keep manual trigger
```

---

## Monitoring

### Key Metrics

**Model Performance**:
```promql
# AUC over time
lead_model_auc

# Alert if AUC < 0.65 for 30m
ALERTS{alertname="LeadModelAUCDegraded"}
```

**Retraining Cadence**:
```promql
# Model updates per day
changes(lead_model_version[24h])

# Time since last update
(time() - lead_model_version)
```

**Training Data Growth**:
```promql
# Training sample count
lead_model_n_train

# Growth rate
rate(lead_model_n_train[7d])
```

**Prediction Quality**:
```promql
# Prediction latency (should stay <50ms)
histogram_quantile(0.95, rate(lead_pred_latency_seconds_bucket[5m]))

# Prediction rate
rate(lead_pred_prob_histogram_count[5m])
```

### Dashboards

**Grafana Panel Examples**:

1. **Model AUC Trend**:
   ```promql
   lead_model_auc
   ```

2. **Training Data Growth**:
   ```promql
   lead_model_n_train
   ```

3. **Retraining History**:
   ```promql
   changes(lead_model_version[30d])
   ```

4. **Prediction Latency**:
   ```promql
   histogram_quantile(0.95, rate(lead_pred_latency_seconds_bucket[5m]))
   ```

---

## Troubleshooting

### Issue: Workflow fails at export step

**Symptom**: GitHub Actions log shows "Missing API_BASE secret"

**Fix**:
1. Add `API_BASE` secret: Settings → Secrets → New repository secret
2. Value: `https://your-api-domain.com`
3. Re-run workflow

### Issue: Training fails with "insufficient data"

**Symptom**: `train_model.py` exits with "Need at least 50 samples"

**Fix**:
1. Check outcome count: `curl https://api.example.com/ops/export/outcomes.csv | wc -l`
2. If < 50, continue collecting data (record more outcomes via `/v1/lead/{id}/outcome`)
3. Workflow will succeed once ≥50 outcomes recorded

### Issue: Hot-reload fails with 500 error

**Symptom**: `/ops/reload-model` returns `{"ok": false, "error": "..."}`

**Fix**:
1. Check API logs: `docker-compose logs api | grep model_reload_failed`
2. Common causes:
   - Invalid `model.json` (check JSON syntax)
   - Missing file permissions
   - Model version mismatch
3. Validate model locally:
   ```bash
   python -c "import json; json.load(open('api/model.json'))"
   ```

### Issue: Model AUC degraded alert firing

**Symptom**: Prometheus alert `LeadModelAUCDegraded` active

**Fix**:
1. Check training data quality:
   ```bash
   curl https://api.example.com/ops/export/outcomes.csv > outcomes.csv
   head -20 outcomes.csv  # Inspect first 20 rows
   ```
2. Look for:
   - Insufficient outcome diversity (all `booked` or all `ghosted`)
   - Missing enrichment features (intent/sentiment/urgency all `unknown`)
   - Tenant hash collision (multiple tenants hashing to same value)
3. If data looks bad, investigate lead creation flow
4. If data looks good, wait for more samples (AUC improves with more data)

### Issue: Prediction latency high

**Symptom**: Alert `LeadPredLatencyHigh` firing (p95 > 100ms)

**Fix**:
1. Check model size:
   ```bash
   ls -lh api/model.json  # Should be <100KB
   ```
2. If >1MB, model may have too many features (check train_model.py feature list)
3. Check CPU usage: `docker stats aetherlink-customerops-api`
4. Consider scaling API if CPU consistently >80%

---

## Best Practices

### Data Quality

**✅ Do**:
- Record outcomes consistently (`booked`, `ghosted`, `qualified`, etc.)
- Use enrichment (intent/sentiment/urgency) for all leads
- Maintain diverse tenant representation
- Track at least 100 outcomes before trusting model

**❌ Don't**:
- Record only positive outcomes (creates bias)
- Skip enrichment (model needs features)
- Delete historical outcomes (hurts retraining)
- Retrain with <50 samples (overfitting risk)

### Retraining Frequency

**Recommended**: Nightly (default 03:17 UTC)

**When to increase**:
- High-volume environments (>1000 leads/day) → Consider 2x daily
- Fast-changing conversion patterns → Consider 4x daily

**When to decrease**:
- Low-volume environments (<100 leads/day) → Consider weekly
- Stable conversion patterns → Consider 2-3x weekly

### Model Validation

Before deploying to production:

```bash
# 1. Test on staging first
API_BASE=https://staging.example.com python scripts/train_model.py

# 2. Compare AUC to previous version
# Old AUC: Check Prometheus or model.json
# New AUC: Check training output

# 3. If new AUC > old AUC + 1%, deploy
curl -X POST https://staging.example.com/ops/reload-model

# 4. Monitor for 24h, then promote to prod
```

---

## Future Enhancements

### Phase 2: A/B Testing
- [ ] Train multiple model variants
- [ ] Split traffic between models
- [ ] Track conversion by model version
- [ ] Auto-promote best performer

### Phase 3: Advanced Retraining
- [ ] Incremental learning (avoid full retrain)
- [ ] Feature importance tracking
- [ ] Automated hyperparameter tuning
- [ ] Multi-model ensemble

### Phase 4: Drift Detection
- [ ] Monitor input feature distributions
- [ ] Detect concept drift (outcome patterns change)
- [ ] Auto-trigger retrain on significant drift
- [ ] Alert on anomalous prediction distributions

---

## References

- **GitHub Actions**: https://docs.github.com/en/actions
- **Prometheus Alerting**: https://prometheus.io/docs/alerting/latest/
- **scikit-learn Logistic Regression**: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- **Model Deployment Best Practices**: https://ml-ops.org/

---

## Changelog

### v1.0.0 (Current)
- ✅ GitHub Actions workflow (nightly 03:17 UTC)
- ✅ `/ops/reload-model` endpoint (hot-reload)
- ✅ Prometheus metrics (MODEL_AUC, MODEL_VERSION, MODEL_N_TRAIN)
- ✅ Automated alerts (AUC degradation, latency)
- ✅ PII redaction backfill script
- ✅ Manual retrain support
- ✅ Artifact archiving (GitHub Actions)

---

## License

Internal use only. Part of AetherLink CustomerOps AI Agent.
