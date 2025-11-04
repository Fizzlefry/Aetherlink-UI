# AetherLink v1.0 - Health Verification Script
# Run this to validate all services are operational

Write-Host "🚀 AetherLink v1.0 Health Check" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# 1. Check running containers
Write-Host "1️⃣ Checking running services..." -ForegroundColor Yellow
docker ps --filter "name=aether" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-Object -First 20
Write-Host ""

# 2. AI Summarizer health
Write-Host "2️⃣ Testing AI Summarizer health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:9108/health" -Method Get
    Write-Host "✅ AI Summarizer: $($health.status)" -ForegroundColor Green
}
catch {
    Write-Host "❌ AI Summarizer: FAILED" -ForegroundColor Red
}
Write-Host ""

# 3. Test AI extraction (stub mode)
Write-Host "3️⃣ Testing AI extraction endpoint..." -ForegroundColor Yellow
try {
    $extractBody = @{
        tenant_id = "acme"
        raw_text  = "Jane Doe, VP Operations, Acme Corp, jane@acme.com, +1-555-123-4567"
    } | ConvertTo-Json

    $extract = Invoke-RestMethod -Uri "http://localhost:9108/summaries/extract-lead" `
        -Method Post `
        -ContentType "application/json" `
        -Body $extractBody

    Write-Host "✅ AI Extract: email=$($extract.email), name=$($extract.name)" -ForegroundColor Green
}
catch {
    Write-Host "❌ AI Extract: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# 4. Notifications service
Write-Host "4️⃣ Testing Notifications hot-reload..." -ForegroundColor Yellow
try {
    $reload = Invoke-RestMethod -Uri "http://localhost:9107/rules/reload" -Method Post
    Write-Host "✅ Notifications: $($reload.message) - $($reload.count) rules loaded" -ForegroundColor Green
}
catch {
    Write-Host "❌ Notifications: FAILED" -ForegroundColor Red
}
Write-Host ""

# 5. Check for recent errors in logs
Write-Host "5️⃣ Checking recent service logs..." -ForegroundColor Yellow
$services = @("aether-ai-summarizer", "aether-notifications-consumer", "aether-crm-events-sink")
foreach ($service in $services) {
    Write-Host "  Checking $service..." -ForegroundColor Gray
    $logs = docker logs $service --tail 5 2>&1 | Select-String -Pattern "error|ERROR|failed|FAILED" -SimpleMatch
    if ($logs) {
        Write-Host "  ⚠️  Found errors in $service" -ForegroundColor Yellow
    }
    else {
        Write-Host "  ✅ No recent errors in $service" -ForegroundColor Green
    }
}
Write-Host ""

# 6. Summary
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Health Check Complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Quick Access URLs:" -ForegroundColor White
Write-Host "  UI:            http://localhost:5173" -ForegroundColor Gray
Write-Host "  Grafana:       http://localhost:3000" -ForegroundColor Gray
Write-Host "  AI Summarizer: http://localhost:9108/health" -ForegroundColor Gray
Write-Host "  Notifications: http://localhost:9107/rules" -ForegroundColor Gray
Write-Host ""
Write-Host "📖 Docs:" -ForegroundColor White
Write-Host "  Release Notes: docs/RELEASE_NOTES_v1.0_AetherLink.md" -ForegroundColor Gray
Write-Host "  Ops Guide:     services/notifications-consumer/OPS-QUICK-CARD.md" -ForegroundColor Gray
Write-Host ""
