# 🧪 A/B Experimentation Framework - Complete Guide

## Overview

The CustomerOps AI Agent now includes a **production-grade A/B testing framework** for data-driven optimization. Test variants of enrichment models, follow-up timing, prediction thresholds, and more - with automatic statistical significance testing and winner promotion.

---

## 🎯 Key Features

✅ **Consistent Hashing** - Same tenant always gets same variant  
✅ **Per-Variant Metrics** - Conversion rates tracked automatically  
✅ **Statistical Significance** - Chi-square tests (p < 0.05)  
✅ **Auto-Promotion** - Winners automatically promoted to 100% traffic  
✅ **Sticky Sessions** - Variants persist across requests  
✅ **Zero Downtime** - Enable/disable experiments without deployment  

---

## 📊 Pre-Configured Experiments

### 1. **Enrichment Model** (`enrichment_model`)
**Question**: Does GPT-4 improve conversion rates vs GPT-3.5?

**Variants**:
- `control` - GPT-3.5-turbo (standard)
- `gpt4` - GPT-4 (higher quality)

**Config**:
```python
{
    "control": {"model": "gpt-3.5-turbo", "temperature": 0.0},
    "gpt4": {"model": "gpt-4", "temperature": 0.0}
}
```

**Traffic**: 50/50 split  
**Min Sample**: 50 per variant

---

### 2. **Follow-Up Timing** (`followup_timing`)
**Question**: Do aggressive follow-ups (5min) outperform conservative (30min)?

**Variants**:
- `control` - 30 minutes delay
- `aggressive` - 5 minutes delay

**Config**:
```python
{
    "control": {"delay_seconds": 1800},
    "aggressive": {"delay_seconds": 300}
}
```

**Traffic**: 50/50 split  
**Min Sample**: 100 per variant

---

### 3. **Prediction Threshold** (`prediction_threshold`)
**Question**: Should we only follow up on high-confidence leads (>70%)?

**Variants**:
- `control` - 50% threshold (follow up most leads)
- `high_confidence` - 70% threshold (follow up only strong leads)

**Config**:
```python
{
    "control": {"threshold": 0.5},
    "high_confidence": {"threshold": 0.7}
}
```

**Traffic**: 50/50 split  
**Min Sample**: 100 per variant

---

## 🚀 Quick Start

### Enable an Experiment

```python
# In api/experiments.py
EXPERIMENTS["followup_timing"].enabled = True
```

Or via environment variable (for production):
```bash
EXPERIMENT_FOLLOWUP_TIMING_ENABLED=true
```

### Check Experiment Status

```bash
curl http://localhost:8000/ops/experiments | jq '.'
```

**Response**:
```json
{
  "experiments": {
    "followup_timing": {
      "enabled": true,
      "description": "Test aggressive (5min) vs conservative (30min) follow-up delays",
      "promoted_variant": null,
      "variants": ["control", "aggressive"],
      "significance": {
        "significant": false,
        "p_value": 0.23,
        "winner": null,
        "variants": {
          "control": {"samples": 45, "conversions": 9, "rate": 0.20},
          "aggressive": {"samples": 48, "conversions": 12, "rate": 0.25}
        }
      }
    }
  }
}
```

### Promote Winner (Manual)

```bash
curl -X POST http://localhost:8000/ops/experiments/followup_timing/promote
```

**Response** (success):
```json
{
  "ok": true,
  "experiment": "followup_timing",
  "promoted": "aggressive",
  "p_value": 0.042,
  "chi_square": 4.21,
  "variants": {
    "control": {"samples": 150, "conversions": 30, "rate": 0.20},
    "aggressive": {"samples": 152, "conversions": 48, "rate": 0.316}
  }
}
```

**Response** (not ready):
```json
{
  "ok": false,
  "error": "No statistically significant winner yet",
  "p_value": 0.12
}
```

---

## 📈 Prometheus Metrics

### Experiment-Specific Metrics

```prometheus
# Total variant assignments
experiment_variant_assigned_total{experiment="followup_timing",variant="control"} 150
experiment_variant_assigned_total{experiment="followup_timing",variant="aggressive"} 152

# Outcomes per variant
experiment_outcome_total{experiment="followup_timing",variant="control",outcome="booked"} 30
experiment_outcome_total{experiment="followup_timing",variant="aggressive",outcome="booked"} 48

# Conversion rate per variant
experiment_conversion_rate{experiment="followup_timing",variant="control"} 0.20
experiment_conversion_rate{experiment="followup_timing",variant="aggressive"} 0.316

# Sample size per variant
experiment_sample_size{experiment="followup_timing",variant="control"} 150
experiment_sample_size{experiment="followup_timing",variant="aggressive"} 152
```

### Useful Queries

```promql
# Conversion rate difference (aggressive vs control)
experiment_conversion_rate{experiment="followup_timing",variant="aggressive"} 
- experiment_conversion_rate{experiment="followup_timing",variant="control"}

# Is winner statistically significant? (>100 samples + rate difference >5%)
(experiment_sample_size{experiment="followup_timing"} > 100) 
and (abs(experiment_conversion_rate{experiment="followup_timing",variant="aggressive"} 
- experiment_conversion_rate{experiment="followup_timing",variant="control"}) > 0.05)

# Total experiment outcomes by type
sum(experiment_outcome_total) by (experiment, outcome)
```

---

## 🔬 How It Works

### 1. Variant Assignment (Consistent Hashing)

```python
from .experiments import get_variant

# Same tenant always gets same variant
variant = get_variant("acme_corp", "followup_timing")
# Returns: "aggressive"

# Different tenant might get different variant
variant = get_variant("beta_corp", "followup_timing")
# Returns: "control"
```

**Algorithm**:
1. Hash `tenant:experiment` with SHA-256
2. Convert to float in [0, 1]
3. Map to variant based on traffic weights

**Example**:
- Hash("acme_corp:followup_timing") = 0.73
- Cumulative weights: control=0.5, aggressive=1.0
- 0.73 > 0.5 → "aggressive"

### 2. Apply Variant Configuration

```python
from .experiments import get_variant_config

# Get variant-specific config
config = get_variant_config("acme_corp", "followup_timing")
# Returns: {"delay_seconds": 300}

# Use in follow-up scheduling
delay = config.get("delay_seconds", default_delay)
```

### 3. Track Outcomes

```python
from .experiments import track_outcome

# Automatically tracked when outcome recorded
track_outcome("acme_corp", "followup_timing", "aggressive", "booked")

# Updates Prometheus metrics:
# - experiment_outcome_total{experiment, variant, outcome}
# - experiment_conversion_rate{experiment, variant}
```

### 4. Statistical Significance Testing

```python
from .experiments import calculate_significance

result = calculate_significance("followup_timing")
# Returns:
# {
#     "significant": true,
#     "p_value": 0.042,
#     "chi_square": 4.21,
#     "winner": "aggressive",
#     "variants": {...}
# }
```

**Chi-Square Test**:
- Null hypothesis: No difference in conversion rates
- Alternative: Variants have different conversion rates
- Reject null if p < 0.05 (95% confidence)

**Requirements**:
- Minimum 100 samples per variant (configurable)
- At least 2 variants with data
- Valid outcome data

---

## 🎨 Creating Custom Experiments

### Example: Test Message Templates

```python
# In api/experiments.py
EXPERIMENTS["message_template"] = Experiment(
    name="message_template",
    description="Test friendly vs professional follow-up messages",
    enabled=True,
    start_date=int(time.time()),
    variants=[
        ExperimentVariant(
            name="control",
            traffic_weight=0.5,
            config={
                "template": "Hi {name}, just following up on your quote request. Any questions?"
            }
        ),
        ExperimentVariant(
            name="friendly",
            traffic_weight=0.5,
            config={
                "template": "Hey {name}! 👋 Wanted to check in about your project. Need any help?"
            }
        ),
    ],
    min_sample_size=200,
    auto_promote=True,
)
```

### Use in Code

```python
# In tasks_followup.py
from .experiments import get_variant_config

config = get_variant_config(tenant, "message_template")
template = config.get("template", default_template)
message = template.format(name=lead_name)
```

---

## 📊 Grafana Dashboard

### Panel 1: Conversion Rate by Variant

```promql
# Query
experiment_conversion_rate{experiment="followup_timing"}

# Panel type: Time series
# Legend: {{variant}}
```

### Panel 2: Sample Size Progress

```promql
# Query
experiment_sample_size{experiment="followup_timing"}

# Panel type: Gauge
# Threshold: Min sample size (100)
```

### Panel 3: Statistical Significance

```promql
# Query (requires recording)
experiment_significance{experiment="followup_timing"}

# Panel type: Stat
# Values: p_value, winner
```

### Panel 4: Outcome Breakdown

```promql
# Query
sum(experiment_outcome_total{experiment="followup_timing"}) by (variant, outcome)

# Panel type: Stacked bar chart
```

---

## 🛡️ Best Practices

### 1. **Always Set Minimum Sample Size**
```python
min_sample_size=100  # Don't test significance until 100 samples/variant
```

### 2. **Use Consistent Traffic Weights**
```python
# Good: Equal split
traffic_weight=0.5

# Good: 90/10 (control/test)
control: 0.9, test: 0.1

# Bad: Unequal but close (hard to detect difference)
control: 0.52, test: 0.48
```

### 3. **One Variable at a Time**
❌ Bad: Test "GPT-4 + 5min delay" vs "GPT-3.5 + 30min delay"  
✅ Good: Test "GPT-4" vs "GPT-3.5" (keep delay same)

### 4. **Run Long Enough**
- Minimum: 1 week (capture weekly cycles)
- Ideal: 2-4 weeks (capture monthly patterns)
- Avoid: Stopping early when winning

### 5. **Monitor Guardrail Metrics**
Track not just conversion, but also:
- Ghost rate (should not increase)
- Follow-up response rate
- Customer satisfaction (if available)

### 6. **Document Why You're Testing**
```python
description="Hypothesis: Faster follow-ups capture hot leads before they cool"
```

---

## 🔧 Troubleshooting

### Problem: Variants Not Assigned

**Symptoms**:
- All tenants getting "control"
- `experiment_variant_assigned_total` not incrementing

**Causes**:
1. Experiment not enabled
2. Traffic weights sum != 1.0
3. No variants defined

**Fix**:
```python
# Check enabled
EXPERIMENTS["followup_timing"].enabled = True

# Check weights
sum(v.traffic_weight for v in EXPERIMENTS["followup_timing"].variants)
# Should equal 1.0
```

---

### Problem: Significance Not Calculated

**Symptoms**:
- `significance.significant = false`
- `significance.error = "Need at least 2 variants with data"`

**Causes**:
1. Insufficient samples (<min_sample_size)
2. Only one variant has data
3. scipy not installed

**Fix**:
```bash
# Install scipy
pip install scipy

# Check sample sizes
curl http://localhost:8000/ops/experiments | jq '.experiments.followup_timing.significance.variants'
```

---

### Problem: Winner Not Promoted

**Symptoms**:
- `/ops/experiments/{name}/promote` returns error
- `promoted_variant` remains null

**Causes**:
1. p-value > 0.05 (not significant)
2. Minimum sample size not reached
3. Auto-promotion disabled

**Fix**:
```python
# Check if significant
result = calculate_significance("followup_timing")
print(f"p-value: {result['p_value']}, significant: {result['significant']}")

# Enable auto-promotion
EXPERIMENTS["followup_timing"].auto_promote = True

# Or manually promote (bypasses checks)
EXPERIMENTS["followup_timing"].promoted_variant = "aggressive"
```

---

## 🎓 Statistical Background

### Chi-Square Test Explained

**What it tests**: Do variants have different conversion rates?

**Example**:
```
           Booked  Not Booked  Total
Control       30        120     150
Aggressive    48        104     152
```

**Expected** (if no difference):
```
           Booked  Not Booked
Control      39.3     110.7
Aggressive   38.7     113.3
```

**Chi-square statistic**:
```
χ² = Σ [(Observed - Expected)² / Expected]
   = (30-39.3)²/39.3 + (120-110.7)²/110.7 + ...
   = 4.21
```

**P-value**: 0.042 (probability this difference is random)

**Decision**: p < 0.05 → Reject null → Variants ARE different!

---

### Power Analysis

**How many samples do I need?**

```python
# For 80% power, α=0.05:
n_per_variant = 16 * (p1 * (1-p1) + p2 * (1-p2)) / (p1 - p2)²

# Example: Detect 20% → 25% lift
p1, p2 = 0.20, 0.25
n = 16 * (0.20*0.80 + 0.25*0.75) / (0.05)²
  = 16 * 0.3475 / 0.0025
  = 2224 per variant
```

**Rule of thumb**:
- Small effect (5% lift): ~2000/variant
- Medium effect (10% lift): ~600/variant
- Large effect (20% lift): ~200/variant

---

## 📚 API Reference

### `get_variant(tenant, experiment_name) → str`
Get assigned variant for a tenant.

**Returns**: Variant name (e.g., "control", "aggressive")

---

### `get_variant_config(tenant, experiment_name) → dict`
Get configuration for assigned variant.

**Returns**: Config dict (e.g., `{"delay_seconds": 300}`)

---

### `track_outcome(tenant, experiment, variant, outcome)`
Record experiment outcome.

**Args**:
- `outcome`: "booked" | "ghosted" | "qualified" | "callback" | "nurture" | "lost"

---

### `calculate_significance(experiment_name) → dict`
Calculate statistical significance via chi-square test.

**Returns**:
```python
{
    "significant": bool,
    "p_value": float,
    "chi_square": float,
    "winner": str | None,
    "variants": {variant: {"rate": float, "samples": int, "conversions": int}}
}
```

---

### `promote_winner(experiment_name) → dict`
Promote winning variant to 100% traffic.

**Returns**:
```python
{
    "ok": bool,
    "promoted": str,
    "p_value": float,
    "variants": {...}
}
```

---

### `list_experiments() → dict`
List all experiments with status.

---

## 🚀 Next Steps

1. **Enable first experiment**: Start with `followup_timing` (fastest results)
2. **Wait for data**: Let run for 1-2 weeks
3. **Check significance**: Monitor `/ops/experiments` dashboard
4. **Promote winner**: Use `/ops/experiments/{name}/promote`
5. **Iterate**: Create next experiment based on learnings

---

## 🎖️ Production Checklist

- [ ] Enable experiment in `api/experiments.py`
- [ ] Verify traffic weights sum to 1.0
- [ ] Set appropriate `min_sample_size`
- [ ] Configure Grafana dashboard panels
- [ ] Set up alerts for anomalies
- [ ] Document hypothesis and expected outcome
- [ ] Run for minimum 1 week
- [ ] Check statistical significance before promoting
- [ ] Monitor guardrail metrics (ghost rate, etc.)
- [ ] Document results and learnings

---

**Status**: Production-ready A/B testing framework with automatic winner promotion! 🧪
