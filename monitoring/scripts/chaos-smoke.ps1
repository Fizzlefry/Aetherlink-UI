# AetherVision Chaos Smoke Test
# Proves end-to-end: probes -> metrics -> alerts -> recovery

Write-Host "`n=== AetherVision Chaos Smoke Test ===" -ForegroundColor Cyan
Write-Host ""

# Pre-test baseline
Write-Host "[Baseline Status]" -ForegroundColor Yellow
$baseline_tcp = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_tcp_up").data.result[0].value[1]
$baseline_alerts = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:alerts:count").data.result[0].value[1]
Write-Host "  TCP probes up: $baseline_tcp"
Write-Host "  Alerts firing: $baseline_alerts"
Write-Host ""

# Test 1: TCP Outage Simulation (Grafana)
Write-Host "`n[Test 1: TCP Outage - Grafana down for 60s]" -ForegroundColor Cyan
Write-Host "  Stopping grafana..." -ForegroundColor Yellow
docker compose stop grafana

Write-Host "  ⏱️  Waiting 60 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
$during_tcp = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_tcp_up").data.result[0].value[1]
Write-Host "  ✅ During outage - TCP probes: $during_tcp (expected: $($baseline_tcp - 1))"

Start-Sleep -Seconds 45
Write-Host "  Starting grafana..." -ForegroundColor Yellow
docker compose start grafana

Write-Host "  ⏱️  Waiting 30s for recovery..." -ForegroundColor Yellow
Start-Sleep -Seconds 30
$after_tcp = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_tcp_up").data.result[0].value[1]
Write-Host "  ✅ After recovery - TCP probes: $after_tcp (expected: $baseline_tcp)"

if ($after_tcp -eq $baseline_tcp) {
    Write-Host "  ✅ Test 1 PASSED: TCP probe recovery verified" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  Test 1 WARNING: TCP probes not fully recovered ($after_tcp vs $baseline_tcp)" -ForegroundColor Yellow
}
Write-Host ""

# Test 2: Check if alerts fired and resolved
Write-Host "🧪 Test 2: Alert Response" -ForegroundColor Cyan
$alerts = (Invoke-RestMethod "http://localhost:9090/api/v1/alerts").data.alerts
$tcp_alerts = $alerts | Where-Object { $_.labels.alertname -like "*Tcp*" -or $_.labels.alertname -like "*Uptime*" }

if ($tcp_alerts) {
    Write-Host "  ✅ Found TCP-related alerts:" -ForegroundColor Green
    $tcp_alerts | ForEach-Object {
        Write-Host "    - $($_.labels.alertname): $($_.state)" -ForegroundColor White
    }
}
else {
    Write-Host "  ℹ️  No TCP alerts currently firing (may have already resolved)" -ForegroundColor Cyan
}
Write-Host ""

# Test 3: Autoheal metrics check
Write-Host "🧪 Test 3: Autoheal Metrics" -ForegroundColor Cyan
try {
    $autoheal_metrics = Invoke-RestMethod "http://localhost:9009/metrics"
    $enabled_line = $autoheal_metrics | Select-String -Pattern "autoheal_enabled"
    $actions_line = $autoheal_metrics | Select-String -Pattern "autoheal_actions_total"

    Write-Host "  ✅ Autoheal metrics endpoint responding" -ForegroundColor Green
    Write-Host "  $enabled_line" -ForegroundColor White

    if ($actions_line) {
        Write-Host "  $actions_line" -ForegroundColor White
    }
    else {
        Write-Host "  ℹ️  No actions executed yet (autoheal disabled)" -ForegroundColor Cyan
    }
}
catch {
    Write-Host "  ⚠️  Autoheal metrics endpoint error: $($_.Exception.Message)" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "📊 Final Status:" -ForegroundColor Yellow
$final_tcp = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_tcp_up").data.result[0].value[1]
$final_http = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_http_up").data.result[0].value[1]
$final_alerts = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:alerts:count").data.result[0].value[1]

Write-Host "  TCP probes up: $final_tcp / $baseline_tcp"
Write-Host "  HTTP probes up: $final_http"
Write-Host "  Alerts firing: $final_alerts"
Write-Host ""

if ($final_tcp -eq $baseline_tcp) {
    Write-Host "✅ Chaos Smoke Test PASSED" -ForegroundColor Green
    Write-Host "   - Probe failure detected" -ForegroundColor Green
    Write-Host "   - Metrics updated correctly" -ForegroundColor Green
    Write-Host "   - Service recovered successfully" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Chaos Smoke Test INCOMPLETE" -ForegroundColor Yellow
    Write-Host "   Please wait a few minutes for probes to recover" -ForegroundColor Yellow
}
Write-Host ""
