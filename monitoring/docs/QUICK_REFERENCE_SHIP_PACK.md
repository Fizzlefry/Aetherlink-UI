# Aetherlink Ship Pack - Quick Reference

## 🚀 What Got Shipped

✅ **Grafana Dashboard** - Error budget + SLO visualization (12 panels)
✅ **Kafka Consumer SSE** - Real-time event stream (Python + FastAPI)
✅ **EF Core Tables** - Outbox + Idempotency pattern (.NET migrations)
✅ **Next.js Page** - CRM Events live dashboard (React + SSE)

**Total**: 1,737 lines of code across 13 files

---

## 📂 Key Files

```
monitoring/grafana/dashboards/
  └── autoheal_oidc_error_budget.json   # Import this in Grafana

pods/crm-events/
  ├── main.py                            # FastAPI SSE service
  ├── requirements.txt                   # Python dependencies
  └── Dockerfile                         # Container definition

peakpro/Domain/
  ├── Outbox/OutboxEvent.cs             # Event entity
  └── Idempotency/IdempotencyKey.cs     # Idempotency entity

peakpro/Infrastructure/
  ├── AppDbContext.cs                    # EF Core DbContext
  └── Outbox/OutboxPublisher.cs         # Background publisher

peakpro/Migrations/
  └── 20251102_Init_Outbox_Idempotency.cs  # Database migration

apps/command-center/app/ops/
  └── crm-events/page.tsx                # Live events dashboard
```

---

## 🎯 3-Minute Deploy

```powershell
# 1. Import Grafana dashboard
Start-Process "http://localhost:3000"
# Upload: monitoring/grafana/dashboards/autoheal_oidc_error_budget.json

# 2. Create Kafka topic
docker exec kafka rpk topic create aetherlink.events --partitions 3 --replicas 1

# 3. Apply EF migration (optional - if using .NET CRM)
cd peakpro
dotnet ef database update
cd ..

# 4. Verify CRM events service
docker logs aether-crm-events --tail 10
# Expected: "Application startup complete"

# 5. Open dashboards
Start-Process "http://localhost:3000/d/autoheal-oidc-error-budget"  # Grafana
Start-Process "http://localhost:3001/ops/crm-events"                # Command Center
```

---

## 🔍 Validation

```powershell
# Check service status
docker ps | grep crm-events
# Expected: aether-crm-events   Up X seconds   0.0.0.0:9010->9010/tcp

# Check Kafka topic
docker exec kafka rpk topic list | grep aetherlink
# Expected: aetherlink.events

# Check database tables (if migration applied)
docker exec postgres-crm psql -U crm -d crm -c "\dt" | grep -E "(outbox|idempotency)"
# Expected: outbox_events, idempotency_keys

# Check Grafana dashboard
curl -s http://localhost:3000/api/dashboards/uid/autoheal-oidc-error-budget | jq .dashboard.title
# Expected: "Autoheal OIDC + Error Budget"
```

---

## 📊 Dashboard Panels

### SLO Panels (Top Row)
1. **Autoheal Status** - up/down indicator (green/red)
2. **Heartbeat Age** - <300s threshold (green < 300s, red > 300s)
3. **Failure Rate** - <0.1% target (green < 0.0003/s)
4. **Audit Write p95** - <100ms target (green < 0.08s)

### Timeseries Panels
5. **SLO-1: Heartbeat Age** - Freshness trend
6. **SLO-2: Failure Rate** - Error rate over time
7. **Error Budget Burn (Fast)** - 14.4x threshold (5% in 1h)
8. **Error Budget Burn (Slow)** - 2.4x threshold (10% in 6h)
9. **SLO-3: Availability** - Uptime percentage (>99.9%)
10. **SLO-4: Audit Latency** - p50, p95, p99 percentiles

### Info Panels
11. **Active Burn Alerts** - Count of firing alerts
12. **Service Labels** - Autoheal metadata table

---

## 🧪 Test Event Flow

```bash
# 1. Create test job (triggers domain event)
curl -X POST http://localhost:8080/api/crm/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: test-123' \
  -H 'X-Tenant-Id: 12345678-1234-1234-1234-123456789012' \
  -d '{"title": "Test", "status": "Open"}'

# 2. Check outbox (event persisted)
docker exec postgres-crm psql -U crm -d crm -c \
  "SELECT type, occurred_at, published_at FROM outbox_events ORDER BY id DESC LIMIT 1;"

# 3. Check Kafka (event published)
docker exec kafka rpk topic consume aetherlink.events --num 1

# 4. Check Command Center (event displayed)
# http://localhost:3001/ops/crm-events
# Should show: JobCreated event with green background
```

---

## 🐛 Quick Troubleshooting

| Problem | Command | Expected |
|---------|---------|----------|
| Service not running | `docker ps \| grep crm-events` | aether-crm-events Up |
| Service crashed | `docker logs aether-crm-events` | "startup complete" |
| Topic missing | `docker exec kafka rpk topic list` | aetherlink.events |
| No events | `docker exec kafka rpk topic consume aetherlink.events --num 1` | JSON event |
| Dashboard 404 | Open Grafana → Dashboards → Import → Upload JSON | Dashboard imported |

---

## 📱 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| CRM Events | http://localhost:9010 | SSE health check |
| CRM Events SSE | http://localhost:9010/crm-events | Event stream |
| Command Center | http://localhost:3001/ops/crm-events | Live dashboard |
| Grafana | http://localhost:3000/d/autoheal-oidc-error-budget | SLO dashboard |
| Prometheus | http://localhost:9090/graph | Metrics query |

---

## 💡 Pro Tips

**Grafana**: Use `$__interval` variable for flexible time ranges
**SSE**: EventSource auto-reconnects on connection drop
**Idempotency**: Send same Idempotency-Key header for duplicate detection
**Outbox**: Events published within 5 seconds (configurable)
**Burn Alerts**: Fast burn = 14.4x = 5% monthly budget in 1 hour

---

## 📚 Full Documentation

- **Complete Guide**: `monitoring/docs/SHIP_PACK_COMPLETE.md`
- **Shipped Summary**: `monitoring/docs/SHIPPED_SHIP_PACK.md`
- **Deployment Script**: `monitoring/scripts/deploy-ship-pack-simple.ps1`

---

**Status**: ✅ SHIPPED (13/13 components complete)
**Manual Steps**: 3 (Grafana import, Kafka topic, EF migration)
**Ready For**: Production deployment + End-to-end testing
