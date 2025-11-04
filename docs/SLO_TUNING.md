# 🎯 SLO TUNING GUIDE

## Current Baseline (v1.0)

### Recording Rules
```yaml
# Cache efficiency (per-tenant + aggregate)
aether:cache_hit_ratio:5m         # 5min window
aether:cache_hit_ratio:5m:all     # Aggregate

# Rerank cost guard (per-tenant + aggregate)
aether:rerank_utilization_pct:15m     # % queries using rerank
aether:rerank_utilization_pct:15m:all

# Quality signal (per-tenant + aggregate)
aether:lowconfidence_pct:15m          # % low-confidence answers
aether:lowconfidence_pct:15m:all

# Business KPIs
aether:estimated_cost_30d_usd         # $0.001 base + $0.006 rerank
aether:health_score:15m               # 50% cache + 30% quality + 20% efficiency
```

### Alert Thresholds
```yaml
# General alerts (15min duration)
CacheEffectivenessDrop:     <30% cache hit ratio
LowConfidenceSpike:         >30% low confidence

# VIP alerts (10min duration, critical severity)
CacheEffectivenessDropVIP:  <20% cache hit ratio
LowConfidenceSpikeVIP:      >40% low confidence

# Composite health (15min duration, warning)
HealthScoreDegradation:     <60 health score
```

---

## 📈 Tuning Methodology

### Phase 1: Baseline (Week 1-2)
**Goal**: Collect real traffic data, measure false positive rate

**Actions**:
1. Monitor alert frequency:
   ```bash
   # Check how often each alert fires
   curl -s http://localhost:9090/api/v1/query --data-urlencode \
     'query=ALERTS{alertstate="firing"}' | jq '.data.result[] | {alert: .metric.alertname, value: .value[1]}'
   ```

2. Track traffic guard effectiveness:
   ```promql
   # Queries that would have fired without traffic guard
   (aether:cache_hit_ratio:5m:all < 30) and sum(rate(aether_cache_requests_total[5m])) == 0
   ```

3. Collect SLO compliance:
   ```promql
   # % of time cache hit ratio met target (>50%)
   avg_over_time((aether:cache_hit_ratio:5m:all > 50)[7d:5m]) * 100
   ```

**Expected Results**:
- Zero false alerts (traffic guards working)
- 1-3 genuine alerts per week (normal for new system)
- 85-95% SLO compliance on cache hit ratio

---

### Phase 2: Tighten VIP Sensitivity (Week 3-4)
**Goal**: Catch VIP degradation earlier with more specific tenant filters

#### Current VIP Filter
```yaml
tenant_id=~"vip-.*|partner-.*"  # Regex match
```

#### Recommended: Explicit VIP List
```yaml
# Replace regex with exact tenant names
tenant_id=~"vip-customer-123|vip-customer-456|partner-abc"

# Benefits:
# - No false matches on "vip-test-123"
# - Explicit contract: add new VIPs intentionally
# - Easier to trace which VIP triggered alert
```

#### Implementation
```yaml
# In prometheus-alerts.yml
- alert: LowConfidenceSpikeVIP
  expr: |
    (
      aether:lowconfidence_pct:15m{tenant_id=~"vip-customer-123|vip-customer-456"} > 35
    ) and sum(rate(aether_rag_answers_total{tenant_id=~"vip-customer-123|vip-customer-456"}[15m])) > 0
  for: 8m  # TUNED: Reduced from 10m to 8m for faster detection
```

**Rationale**: VIP alerts should fire **earlier** (8min vs 10min) since impact is revenue-critical.

---

### Phase 3: Rerank Cost Guard (Week 5-6)
**Goal**: Prevent cost explosions from over-reliance on reranking

#### Current Threshold
```yaml
# No alert on rerank % (only used in health score)
aether:rerank_utilization_pct:15m:all  # Tracked but not alerted
```

#### Recommended: Two-Tier Alert
```yaml
# Warning: Rerank usage creeping up
- alert: RerankUtilizationHigh
  expr: |
    (
      aether:rerank_utilization_pct:15m:all > 50
    ) and sum(rate(aether_rag_answers_total[15m])) > 0
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Rerank usage at {{ $value }}% (target <50%)"
    description: |
      High rerank utilization increases costs 6x ($0.006 vs $0.001).

      Impact: 30-day cost = ${{ query "aether:estimated_cost_30d_usd" | first | value }}

      Possible causes:
      - Confidence thresholds too aggressive
      - Index quality degraded (more reranking needed)
      - Traffic shift to complex queries

      Actions:
      - Review confidence cutoffs in chat_handler.py
      - Check index freshness: last update timestamp
      - Analyze query complexity distribution

# Critical: Rerank usage exceeds acceptable cost
- alert: RerankUtilizationCritical
  expr: |
    (
      aether:rerank_utilization_pct:15m:all > 80
    ) and sum(rate(aether_rag_answers_total[15m])) > 0
  for: 15m
  labels:
    severity: critical
  annotations:
    summary: "🚨 Rerank usage at {{ $value }}% - cost explosion risk"
    description: |
      Rerank usage critically high. Estimated 30-day cost: ${{ query "aether:estimated_cost_30d_usd" | first | value }}

      Immediate action required:
      1. Check for runaway tenant: topk(5, rate(aether_rag_answers_total{rerank="true"}[15m]) by (tenant_id))
      2. Consider temporary rerank disable for non-VIP tenants
      3. Page finance team if cost >$500/month
```

**Rationale**: Rerank is 6x more expensive. Need early warning (50%) and hard limit (80%).

---

### Phase 4: Health Score Reweighting (Week 7-8)
**Goal**: Bias health score toward quality over efficiency

#### Current Formula
```promql
0.5 * cache_hit_ratio:5m:all          # 50% weight
+ 0.3 * (100 - lowconfidence_pct:15m:all)  # 30% weight
+ 0.2 * (100 - rerank_utilization_pct:15m:all)  # 20% weight
```

**Problem**: Cache hit ratio too heavily weighted. Low confidence is more critical.

#### Recommended: Quality-First Formula
```promql
0.4 * cache_hit_ratio:5m:all          # 40% weight (was 50%)
+ 0.4 * (100 - lowconfidence_pct:15m:all)  # 40% weight (was 30%)
+ 0.2 * (100 - rerank_utilization_pct:15m:all)  # 20% weight (unchanged)
```

**Rationale**:
- **Cold cache** (low hit ratio) is annoying but **self-healing**
- **Low confidence** (quality issue) directly impacts user experience
- **Rerank %** (cost) is important but tertiary

#### Implementation
```yaml
# In prometheus-recording-rules.yml
- record: aether:health_score:15m
  expr: |
    clamp_max(
      clamp_min(
          0.4 * aether:cache_hit_ratio:5m:all
        + 0.4 * (100 - aether:lowconfidence_pct:15m:all)
        + 0.2 * (100 - aether:rerank_utilization_pct:15m:all)
      , 0)
    , 100)
```

**Before/After Example**:
| Scenario | Cache | Quality | Efficiency | Old Score | New Score | Impact |
|----------|-------|---------|------------|-----------|-----------|--------|
| Cold cache, high quality | 10% | 90% | 80% | 48 | 57 | +9 (less alarming) |
| Good cache, low quality | 80% | 50% | 90% | 73 | 70 | -3 (more sensitive) |
| Balanced | 60% | 80% | 70% | 80 | 82 | +2 (minor) |

**Tuning**: Adjust weights based on business priority:
- **Startup/Growth**: Bias quality (40-40-20) ← **Recommended**
- **Cost-conscious**: Bias efficiency (40-30-30)
- **High-traffic mature**: Bias cache (50-30-20) ← Current

---

## 🎛️ Advanced Tuning: Dynamic Thresholds

### Use Case: Tenant-Specific SLOs
Some VIP tenants may have stricter requirements than others.

#### Example: Multi-Tier VIP Alerts
```yaml
# Tier 1 VIP (enterprise contract, 99.5% SLA)
- alert: LowConfidenceSpikeVIP_Tier1
  expr: |
    (
      aether:lowconfidence_pct:15m{tenant_id=~"vip-enterprise-.*"} > 25  # Stricter: 25% vs 40%
    ) and sum(rate(aether_rag_answers_total{tenant_id=~"vip-enterprise-.*"}[15m])) > 0
  for: 5m  # Faster: 5min vs 10min
  labels:
    severity: critical
    tier: "1"
    sla: "99.5"

# Tier 2 VIP (standard contract, 95% SLA)
- alert: LowConfidenceSpikeVIP_Tier2
  expr: |
    (
      aether:lowconfidence_pct:15m{tenant_id=~"vip-standard-.*"} > 40
    ) and sum(rate(aether_rag_answers_total{tenant_id=~"vip-standard-.*"}[15m])) > 0
  for: 10m
  labels:
    severity: warning
    tier: "2"
    sla: "95"
```

---

## 📊 Monitoring Tuning Effectiveness

### Dashboard Queries

#### Alert Fire Rate (weekly)
```promql
sum(increase(ALERTS{alertstate="firing"}[7d])) by (alertname)
```

#### SLO Compliance (30 days)
```promql
# Cache hit ratio >50% for 95% of time
quantile_over_time(0.05, aether:cache_hit_ratio:5m:all[30d])  # Should be >50

# Low confidence <30% for 95% of time
quantile_over_time(0.95, aether:lowconfidence_pct:15m:all[30d])  # Should be <30
```

#### False Positive Rate
```promql
# Alerts that resolved in <5min (likely transient/false)
count_over_time((ALERTS{alertstate="firing"} offset 5m == 1 and ALERTS{alertstate="firing"} == 0)[7d:1h])
```

### Tuning Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| False positive rate | <5% | TBD | 📊 Measure in Week 2 |
| Genuine alert response time | <15min | TBD | 📊 Measure in Week 3 |
| SLO compliance (cache) | >90% | TBD | 📊 Measure in Week 4 |
| VIP incident catch rate | 100% | TBD | 📊 Measure in Month 2 |

---

## 🔧 Quick Tuning Commands

### Test Alert Firing
```bash
# Lower threshold temporarily to test alert
curl -X POST http://localhost:9090/api/v1/admin/tsdb/delete_series \
  -d 'match[]=aether_cache_hits_total{tenant_id="test-tenant"}'

# Should fire CacheEffectivenessDrop within 15min
```

### Hot-Reload After Tuning
```bash
# Edit prometheus-alerts.yml or prometheus-recording-rules.yml
# Then reload without restart:
curl -X POST http://localhost:9090/-/reload
```

### Verify New Thresholds
```bash
# Check alert expressions loaded correctly
curl -s http://localhost:9090/api/v1/rules | \
  jq '.data.groups[].rules[] | select(.type=="alerting") | {alert: .name, expr: .query}'
```

---

## 📅 Tuning Schedule

**Week 1-2**: Baseline measurement
**Week 3-4**: VIP sensitivity tuning
**Week 5-6**: Rerank cost guards
**Week 7-8**: Health score reweighting
**Month 3+**: Tenant-specific SLOs (if needed)

**Review Cadence**: Monthly SLO review, quarterly alert tuning

---

**Version**: 1.0
**Last Updated**: 2024-01-XX
**Owner**: Platform Ops + ML Team
