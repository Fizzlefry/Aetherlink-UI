# ============================================================================
# FINAL DEPLOYMENT - Command Reference
# ============================================================================

Write-Host "`n=== NEXT STEPS - Light Up Dashboards ===" -ForegroundColor Cyan

Write-Host "`n1️⃣  Start the AetherLink API" -ForegroundColor Yellow
Write-Host "   cd pods\customer-ops" -ForegroundColor Gray
Write-Host "   docker compose up -d" -ForegroundColor Gray
Write-Host "   Start-Sleep -Seconds 15" -ForegroundColor Gray

Write-Host "`n2️⃣  Verify metrics endpoint" -ForegroundColor Yellow
Write-Host "   curl http://localhost:8000/metrics | Select-String aether_" -ForegroundColor Gray

Write-Host "`n3️⃣  Open monitoring interfaces" -ForegroundColor Yellow
Write-Host "   Start-Process 'http://localhost:9090/rules'" -ForegroundColor Gray
Write-Host "   Start-Process 'http://localhost:9090/graph'" -ForegroundColor Gray
Write-Host "   Start-Process 'http://localhost:3000'" -ForegroundColor Gray

Write-Host "`n=== PromQL Spot Checks ===" -ForegroundColor Cyan
Write-Host "Run these in Prometheus Graph (http://localhost:9090/graph):`n" -ForegroundColor Gray

Write-Host "📊 Core Metrics (per-tenant):" -ForegroundColor Yellow
Write-Host "   aether:cache_hit_ratio:5m" -ForegroundColor White
Write-Host "   aether:rerank_utilization_pct:15m" -ForegroundColor White
Write-Host "   aether:lowconfidence_pct:15m" -ForegroundColor White

Write-Host "`n📊 Aggregate Metrics (all tenants):" -ForegroundColor Yellow
Write-Host "   aether:cache_hit_ratio:5m:all" -ForegroundColor White
Write-Host "   aether:rerank_utilization_pct:15m:all" -ForegroundColor White
Write-Host "   aether:lowconfidence_pct:15m:all" -ForegroundColor White

Write-Host "`n💰 Billing & Cost:" -ForegroundColor Yellow
Write-Host "   aether:estimated_cost_30d_usd" -ForegroundColor White
Write-Host "   # Shows estimated 30-day cost based on answer volume" -ForegroundColor DarkGray

Write-Host "`n🏥 Health Score (0-100):" -ForegroundColor Yellow
Write-Host "   aether:health_score:15m" -ForegroundColor White
Write-Host "   # Weighted: 50% cache + 30% quality + 20% efficiency" -ForegroundColor DarkGray

Write-Host "`n=== Optional: Enable Slack Notifications ===" -ForegroundColor Cyan
Write-Host "`n# 1. Set webhook URL" -ForegroundColor Gray
Write-Host "   `$env:SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/XXX/YYY/ZZZ'" -ForegroundColor White

Write-Host "`n# 2. Edit monitoring/alertmanager.yml" -ForegroundColor Gray
Write-Host "   # Add slack receiver with api_url" -ForegroundColor White
Write-Host "   # Change route receiver from 'default' to 'slack'" -ForegroundColor White

Write-Host "`n# 3. Restart Alertmanager" -ForegroundColor Gray
Write-Host "   cd monitoring; docker compose restart alertmanager" -ForegroundColor White

Write-Host "`n=== Grafana Enhancements ===" -ForegroundColor Cyan

Write-Host "`n📊 Add Billing Panel:" -ForegroundColor Yellow
Write-Host "   1. Open dashboard (http://localhost:3000)" -ForegroundColor Gray
Write-Host "   2. Add panel → Stat visualization" -ForegroundColor Gray
Write-Host "   3. Query: aether:estimated_cost_30d_usd" -ForegroundColor Gray
Write-Host "   4. Unit: currency (USD)" -ForegroundColor Gray
Write-Host "   5. Title: '30-Day Estimated Cost'" -ForegroundColor Gray

Write-Host "`n🏥 Add Health Score Gauge:" -ForegroundColor Yellow
Write-Host "   1. Add panel → Gauge visualization" -ForegroundColor Gray
Write-Host "   2. Query: aether:health_score:15m" -ForegroundColor Gray
Write-Host "   3. Min: 0, Max: 100" -ForegroundColor Gray
Write-Host "   4. Thresholds: 60 (yellow), 80 (green)" -ForegroundColor Gray
Write-Host "   5. Title: 'System Health Score'" -ForegroundColor Gray

Write-Host "`n🔒 Security Hardening:" -ForegroundColor Yellow
Write-Host "   1. Change Grafana password: Settings → Users → admin" -ForegroundColor Gray
Write-Host "   2. Verify VIP regex: vip-.*|premium-.* matches your tenants" -ForegroundColor Gray

Write-Host "`n=== Quick Verification ===" -ForegroundColor Cyan
Write-Host "   .\scripts\quick-check.ps1" -ForegroundColor White
Write-Host ""
