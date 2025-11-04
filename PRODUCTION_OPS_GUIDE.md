# 🛡️ Production Operations Guide

## Quick Reference - Safety Switches

### 1. Emergency Rollback (Bad Model Deployed)

```bash
# Step 1: Download previous model from GitHub Actions artifacts
# Go to: GitHub → Actions → nightly-model-retrain → Recent successful run → Artifacts → model-json

# Step 2: Replace current model
cp model.json.backup pods/customer_ops/api/model.json

# Step 3: Hot-reload with validation
curl -X POST "http://localhost:8000/ops/reload-model?min_auc=0.70"

# Step 4: Verify rollback
curl http://localhost:8000/ops/model-status | jq '.version, .auc, .health'
```

### 2. Disable Nightly Retraining

```bash
# Temporary (keep manual trigger available):
# GitHub → Actions → nightly-model-retrain → ... → Disable workflow

# Permanent (delete workflow):
rm .github/workflows/model_retrain.yml
git commit -m "Disable automated retraining"
```

### 3. Lock Minimum AUC on Deploy

```bash
# Reject any model with AUC < 0.70
curl -X POST "http://localhost:8000/ops/reload-model?min_auc=0.70"

# Response if rejected:
# {
#   "ok": false,
#   "error": "Model AUC below threshold",
#   "auc": 0.68,
#   "min_auc": 0.70,
#   "rejected": true
# }
```

---

## Model Status Dashboard

### Check Current Model Health

```bash
curl http://localhost:8000/ops/model-status | jq '.'
```

**Example Response**:
```json
{
  "loaded": true,
  "version": 1730483820,
  "version_date": "2024-11-01T12:30:20Z",
  "auc": 0.78,
  "n_train": 523,
  "load_time": 1730483820.123,
  "age_hours": 24.5,
  "drift_score": 1.2,
  "health": "ok"
}
```

### Health Status Values

| Status | Meaning | Action |
|--------|---------|--------|
| `ok` | All metrics nominal | None |
| `warning_low_auc` | AUC between 0.55-0.65 | Schedule retrain |
| `critical_low_auc` | AUC < 0.55 | Immediate retrain |
| `warning_high_drift` | Drift > 3.0σ | Data distribution changed, retrain soon |
| `warning_stale` | Model > 48 hours old | Check if nightly retrain failed |
| `no_model` | Model not loaded | Check model.json exists |
| `error` | Exception occurred | Check logs |

---

## Prometheus Metrics

### Model Metrics

```prometheus
# Model performance (AUC score, 0-1 scale)
lead_model_auc 0.78

# Model version (Unix timestamp)
lead_model_version 1730483820

# Training sample count
lead_model_n_train 523

# Feature drift (standard deviations from training)
lead_model_drift_score 1.2

# Last reload timestamp
lead_model_last_reload_ts 1730570000
```

### Query Examples

```promql
# Hours since last model update
(time() - lead_model_version) / 3600

# Hours since last reload
(time() - lead_model_last_reload_ts) / 3600

# Days since model trained
(time() - lead_model_version) / 86400

# Is model stale? (>48h)
(time() - lead_model_version) > 172800

# Is drift concerning? (>3σ)
lead_model_drift_score > 3.0
```

---

## Alert Rules

### New Alerts Added

**LeadModelHighDrift** (warning):
- Trigger: `lead_model_drift_score > 3.0` for 1 hour
- Meaning: Production features are >3 standard deviations from training distribution
- Action: Check if data patterns changed, retrain with recent data

---

## Data Quality Checks

### Before Manual Retrain

```bash
# 1. Export outcomes
curl http://localhost:8000/ops/export/outcomes.csv > outcomes.csv

# 2. Validate sample count (should be >100)
wc -l outcomes.csv

# 3. Check class balance
awk -F',' 'NR>1 {print $NF}' outcomes.csv | sort | uniq -c

# 4. Check for null values
awk -F',' 'NR>1 {for(i=1;i<=NF;i++) if($i=="") print "Null in row "NR", col "i}' outcomes.csv

# 5. If looks good, train
cd pods/customer_ops
python scripts/train_model.py --input ../../outcomes.csv --output api/model.json
```

### After Retraining

```bash
# 1. Validate model.json exists
ls -lh pods/customer_ops/api/model.json

# 2. Check AUC in file
jq '.metrics.auc' pods/customer_ops/api/model.json

# 3. Hot-reload with validation
curl -X POST "http://localhost:8000/ops/reload-model?min_auc=0.65"

# 4. Verify metrics updated
curl http://localhost:8000/metrics | grep lead_model
```

---

## Backfill PII Redaction

### Weekly Automated Backfill

GitHub Action runs every Sunday at 02:00 UTC:
- `.github/workflows/pii_backfill.yml`
- Requires secret: `REDIS_URL_PROD`

### Manual Backfill

```bash
# 1. Always dry-run first!
cd pods/customer_ops
REDIS_URL=redis://localhost:6379/0 python scripts/scrub_history.py --dry-run

# 2. Review output (scanned/redacted counts)

# 3. If looks good, run for real
REDIS_URL=redis://localhost:6379/0 python scripts/scrub_history.py

# 4. Verify in Redis
redis-cli
> LRANGE mem:tenant1:chat1 0 -1
> # Should show [REDACTED] for PII
```

---

## Grafana Dashboard Queries

### Model Performance Panel

```promql
# AUC over time
lead_model_auc

# With threshold line at 0.65
lead_model_auc
lead_model_auc * 0 + 0.65
```

### Model Age Panel

```promql
# Hours since last update
(time() - lead_model_version) / 3600
```

### Drift Score Panel

```promql
# Drift score over time
lead_model_drift_score

# With warning threshold at 3.0
lead_model_drift_score * 0 + 3.0
```

### Training Data Growth Panel

```promql
# Sample count over time
lead_model_n_train
```

---

## Troubleshooting

### Problem: Model reload rejected (AUC too low)

**Symptoms**:
```json
{"ok": false, "error": "Model AUC below threshold", "auc": 0.60, "rejected": true}
```

**Root Cause**: New model trained on bad/insufficient data

**Fix**:
1. Check outcomes export: `curl /ops/export/outcomes.csv | wc -l`
2. If <100 samples, wait for more data
3. If class imbalance >90%, need more conversions
4. If data looks good, lower threshold temporarily: `?min_auc=0.55`

---

### Problem: High drift score (>3.0)

**Symptoms**:
- `lead_model_drift_score` = 4.5
- Alert: `LeadModelHighDrift`

**Root Cause**: Production data distribution changed vs training

**Fix**:
1. Check recent leads: Are they different types?
2. New tenant with different patterns?
3. Seasonal shift (e.g., holiday traffic)?
4. Retrain with recent data to adapt:
   ```bash
   # Trigger manual retrain
   gh workflow run nightly-model-retrain.yml
   ```

---

### Problem: Model not reloading in production

**Symptoms**:
- GitHub Action succeeds
- But `lead_model_version` unchanged

**Root Cause**: Hot-reload endpoint unreachable or failing

**Debug**:
```bash
# 1. Check if API is up
curl http://your-api.com/health

# 2. Test reload manually
curl -X POST http://your-api.com/ops/reload-model -H "x-api-key: $API_KEY"

# 3. Check API logs for errors
docker-compose logs api | grep model_reload

# 4. Verify GitHub secret API_BASE is correct
# GitHub → Settings → Secrets → Actions → API_BASE
```

---

### Problem: Weekly PII backfill failing

**Symptoms**:
- GitHub Action fails
- Error: "Redis connection refused"

**Root Cause**: `REDIS_URL_PROD` secret not set or incorrect

**Fix**:
```bash
# 1. Add/update secret in GitHub
# Settings → Secrets → Actions → REDIS_URL_PROD
# Value: redis://user:pass@redis.example.com:6379/0

# 2. Test locally first
REDIS_URL=redis://... python scripts/scrub_history.py --dry-run

# 3. Re-run workflow manually
# Actions → weekly-pii-backfill → Run workflow
```

---

## Best Practices

### 1. Always Validate Before Deploy

```bash
# Bad (blind deploy):
curl -X POST /ops/reload-model

# Good (check AUC first):
jq '.metrics.auc' api/model.json  # Verify >0.65
curl -X POST "/ops/reload-model?min_auc=0.65"
```

### 2. Keep Model Backups

```bash
# Before manual retrain, backup current
cp api/model.json api/model.json.$(date +%Y%m%d_%H%M%S)

# Or download from GitHub artifacts (automatic)
```

### 3. Monitor Drift Weekly

```bash
# Add to cron or monitoring script
curl http://localhost:8000/ops/model-status | jq '.drift_score'
# If >2.5, plan a retrain
```

### 4. Test in Staging First

```bash
# Deploy to staging
curl -X POST https://staging-api.com/ops/reload-model

# Run smoke test
curl -X POST https://staging-api.com/v1/lead -d '{"name":"Test","phone":"555","details":"test"}'

# If OK, deploy to prod
curl -X POST https://prod-api.com/ops/reload-model
```

---

## Maintenance Schedule

| Task | Frequency | Automation | Manual |
|------|-----------|------------|--------|
| Model retraining | Nightly (03:17 UTC) | ✅ GitHub Actions | Optional trigger |
| PII backfill | Weekly (Sun 02:00 UTC) | ✅ GitHub Actions | Optional trigger |
| Model status check | Daily | ✅ Prometheus alerts | `/ops/model-status` |
| Drift monitoring | Daily | ✅ Prometheus alerts | Dashboard review |
| Model backups | Per deploy | ✅ GitHub artifacts | Manual download |
| Rollback drill | Monthly | ❌ | Test manually |
| Alert review | Weekly | ❌ | Check Alertmanager |

---

## Security Notes

### API Key Required

All `/ops/*` endpoints require `x-api-key` header or `?api_key=` query param:

```bash
# Header (preferred)
curl -H "x-api-key: your-key" /ops/model-status

# Query param (fallback)
curl "/ops/model-status?api_key=your-key"
```

### GitHub Secrets

Required secrets for workflows:

| Secret | Used By | Example |
|--------|---------|---------|
| `API_BASE` | model_retrain.yml | `https://api.example.com` |
| `API_KEY` | model_retrain.yml | `prod-key-abc123` (optional) |
| `REDIS_URL_STAGING` | pii_backfill.yml | `redis://staging:6379/0` |
| `REDIS_URL_PROD` | pii_backfill.yml | `redis://prod:6379/0` |

---

## Next-Level Upgrades

### A) Model Governance & Cards

Add `/ops/model-card` endpoint exposing:
- Training window (date range)
- Feature descriptions
- Fairness notes
- Known limitations
- Signed model digest (security)
- Stale data alerts

### B) A/B Experimentation

- Feature flag buckets (memory/enrichment/prediction/follow-up timing)
- Per-bucket metrics tracking
- Auto-promote winning variants
- Statistical significance tests

### C) Multi-Channel Follow-Ups

- Pluggable providers (Twilio SMS, SendGrid email, WhatsApp)
- Templated messages per channel
- Per-tenant rate limiting
- Delivery metrics (open/click/reply rates)

---

**Status**: Production-ready autonomous learning system with full safety controls 🚀
