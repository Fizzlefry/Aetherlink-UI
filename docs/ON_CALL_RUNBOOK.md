# 🚨 AetherLink Monitoring - On-Call Runbook

## Quick Reference
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **Quick Check**: `.\scripts\quick-check.ps1`
- **Maintenance Mode**: `.\scripts\maintenance-mode.ps1 -DurationMinutes 60`

---

## Alert Triage Matrix

| Alert | Severity | Response Time | First Actions |
|-------|----------|---------------|---------------|
| CacheEffectivenessDrop | general | 30 min | Check Redis, review traffic patterns |
| LowConfidenceSpike | general | 30 min | Inspect prompts, verify index freshness |
| LowConfidenceSpikeVIP | **CRITICAL** | **5 min** | Page on-call, escalate immediately |
| CacheEffectivenessDropVIP | **CRITICAL** | **5 min** | Page on-call, check VIP tenant health |
| HealthScoreDegradation | warning | 60 min | Investigate composite metrics |

---

## 🔥 CRITICAL ALERTS (Page Immediately)

### ❗ LowConfidenceSpikeVIP
**Trigger**: >40% low-confidence answers for VIP tenant, sustained 10+ min

**Impact**: Revenue risk, VIP customer experience degraded

**Triage Steps**:
1. **Identify Tenant**:
   ```promql
   aether:lowconfidence_pct:15m{tenant_id=~"vip-customer-123|partner-abc"}
   ```

2. **Check Recent Changes**:
   - Deployment in last 2 hours? → Rollback
   - Index updated? → Verify freshness: `docker logs aether-indexer | tail -20`
   - Prompt changes? → Review `pods/customer-ops/handlers/chat_handler.py`

3. **Sample Queries**:
   ```bash
   # Get last 10 VIP queries with confidence scores
   docker exec -it aether-api python -c "
   from api.crud import get_recent_queries
   for q in get_recent_queries(tenant='vip-customer-123', limit=10):
       print(f'{q.timestamp} | {q.query[:50]} | conf={q.confidence_score}')
   "
   ```

4. **Immediate Mitigations**:
   - Lower confidence threshold temporarily: Edit `chat_handler.py` line 42: `CONFIDENCE_THRESHOLD = 0.5` → `0.4`
   - Force rerank for VIP: `DEFAULT_RERANK = True` in tenant config

5. **Escalation**:
   - If confidence <30% for >20min → **Call ML team**
   - If query volume normal but confidence tanked → **Model drift suspected**

---

### ❗ CacheEffectivenessDropVIP
**Trigger**: VIP cache hit ratio <20%, sustained 10+ min

**Impact**: VIP latency spike, increased rerank costs

**Triage Steps**:
1. **Check Redis Health**:
   ```bash
   docker exec -it aether-redis redis-cli INFO stats
   # Look for: evicted_keys, used_memory_peak
   ```

2. **Verify Cache Config**:
   ```promql
   rate(aether_cache_hits_total{tenant_id=~"vip-.*"}[5m]) /
   rate(aether_cache_requests_total{tenant_id=~"vip-.*"}[5m])
   ```

3. **Common Causes**:
   - **Redis restart** → Cache cold, wait 15min for warmup
   - **Memory pressure** → Check `used_memory_rss` in Redis INFO
   - **Query diversity spike** → Normal during onboarding, monitor cost

4. **Immediate Actions**:
   - If Redis OOM → Increase `maxmemory` in `docker-compose.yml`
   - If cache cold → Consider prewarming: `.\scripts\cache-prewarm.ps1 -TenantId vip-customer-123`
   - If query diversity → Acceptable, monitor billing metric

---

## ⚠️ GENERAL ALERTS (30min SLA)

### CacheEffectivenessDrop
**Trigger**: Aggregate cache hit ratio <30% for 15min

**Triage**:
1. Check if **all** tenants affected or isolated:
   ```promql
   topk(5, aether:cache_hit_ratio:5m)
   bottomk(5, aether:cache_hit_ratio:5m)
   ```

2. If **all tenants**: System-wide issue
   - Redis crash? `docker ps | grep redis`
   - Cache clear? Check deployment logs for cache flush commands

3. If **isolated tenants**: Expected behavior
   - New tenant onboarding? (0% cache hit is normal initially)
   - Low traffic tenant? (traffic guard prevents false alert)

4. **No immediate action needed** unless costs spike
   - Watch: `aether:estimated_cost_30d_usd > 200` → Investigate

---

### LowConfidenceSpike
**Trigger**: >30% low-confidence answers for 15min

**Triage**:
1. **Check Traffic Composition**:
   ```promql
   rate(aether_rag_answers_total{confidence_bucket="low"}[15m]) by (tenant_id)
   ```

2. **Correlate with Deployments**:
   - Model update? → A/B test rollback
   - Index refresh? → Verify vector db health: `docker logs aether-vectordb`

3. **Sample Analysis**:
   ```bash
   # Export last 50 low-confidence queries for review
   docker exec aether-api python -c "
   from api.crud import get_low_confidence_queries
   import csv
   with open('/tmp/low_conf.csv', 'w') as f:
       writer = csv.writer(f)
       writer.writerow(['timestamp', 'tenant', 'query', 'confidence'])
       for q in get_low_confidence_queries(limit=50):
           writer.writerow([q.timestamp, q.tenant_id, q.query, q.confidence_score])
   "
   docker cp aether-api:/tmp/low_conf.csv ./logs/
   ```

4. **Common Patterns**:
   - Ambiguous queries → User education, prompt tuning
   - Out-of-domain questions → Index coverage gap
   - Adversarial testing → Rate limit abusive tenant

---

### HealthScoreDegradation
**Trigger**: Composite health <60 for 15min

**Triage**:
1. **Decompose Health Score**:
   ```promql
   # Health = 50% cache + 30% quality + 20% efficiency
   aether:cache_hit_ratio:5m:all          # Target: >50%
   aether:lowconfidence_pct:15m:all       # Target: <30%
   aether:rerank_utilization_pct:15m:all  # Target: <60%
   ```

2. **Identify Root Cause**:
   - Cache <30%? → See **CacheEffectivenessDrop**
   - Low-confidence >40%? → See **LowConfidenceSpike**
   - Rerank >80%? → Cost explosion, tighten thresholds

3. **Holistic Assessment**:
   - If only **one** component degraded → Targeted fix
   - If **multiple** components → System-wide incident

4. **Auto-Recovery**:
   - Most health degradation is **transient** (traffic spikes, cold cache)
   - Monitor for 30min, escalate if sustained

---

## 🛠️ Common Operations

### Silence Alerts During Deploy
```powershell
.\scripts\maintenance-mode.ps1 -DurationMinutes 30 -Comment "Rolling deploy v2.3.0"
```

### Check Recording Rule Output
```bash
# Verify all 8 rules evaluating
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'

# Sample current values
curl -s http://localhost:9090/api/v1/query --data-urlencode 'query=aether:health_score:15m' | jq
```

### Force Alert (Testing)
```bash
# Trigger CacheEffectivenessDrop
curl -X POST http://localhost:9090/api/v1/admin/tsdb/delete_series \
  -d 'match[]=aether_cache_hits_total'
```

### Backup Before Changes
```powershell
.\scripts\backup-monitoring.ps1
git add .\monitoring\backups\
git commit -m "backup: pre-deploy $(Get-Date -Format 'yyyy-MM-dd')"
```

---

## 📊 SLO Reference

| Metric | Target | Critical |
|--------|--------|----------|
| Cache Hit Ratio (Agg) | >50% | <30% |
| Low-Confidence % (Agg) | <20% | >30% |
| Rerank Utilization | <50% | >80% |
| Health Score | >80 | <60 |
| VIP Cache Hit Ratio | >30% | <20% |
| VIP Low-Confidence % | <30% | >40% |

---

## 🔍 Investigation Queries

### Top Tenants by Volume
```promql
topk(10, sum(rate(aether_rag_answers_total[1h])) by (tenant_id))
```

### Costliest Tenants (Rerank)
```promql
topk(5, sum(increase(aether_rag_answers_total{rerank="true"}[24h])) by (tenant_id))
```

### Latency Percentiles (if instrumented)
```promql
histogram_quantile(0.95, rate(aether_query_duration_seconds_bucket[5m]))
```

### VIP Tenant Health Check
```promql
{
  cache: aether:cache_hit_ratio:5m{tenant_id="vip-customer-123"},
  quality: 100 - aether:lowconfidence_pct:15m{tenant_id="vip-customer-123"},
  efficiency: 100 - aether:rerank_utilization_pct:15m{tenant_id="vip-customer-123"}
}
```

---

## 🚀 Escalation Paths

1. **VIP Alert Fires** → Page on-call immediately
2. **General Alert >1hr** → Ping #aether-ops Slack
3. **Cost >$200/30d** → Email VP Engineering + Finance
4. **Health <40 sustained** → Incident Commander activation

---

## 📝 Post-Incident Actions

1. **Silence resolved alerts**: Check http://localhost:9093/#/silences
2. **Export incident data**:
   ```bash
   # Get timeseries during incident
   START=$(date -u -d '2 hours ago' +%s)
   END=$(date -u +%s)
   curl "http://localhost:9090/api/v1/query_range?query=aether:health_score:15m&start=$START&end=$END&step=60s" > incident_data.json
   ```
3. **Update runbook**: Add new patterns/mitigations
4. **Tune alert**: If false positive, adjust threshold or add context filter

---

**Last Updated**: 2024-01-XX
**Version**: 1.0
**Owner**: Platform Ops Team
