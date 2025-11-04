# AetherVision Quick Verification Script
# Run this to check all AetherVision metrics are operational

Write-Host "`n=== AetherVision Quick Status ===" -ForegroundColor Cyan
Write-Host ""

# Check recording rules
Write-Host "Recording Rules:" -ForegroundColor Yellow
try {
    $alerts_count = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:alerts:count").data.result[0].value[1]
    Write-Host "  ✅ alerts:count: $alerts_count" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  alerts:count: N/A" -ForegroundColor Red
}

try {
    $http_up = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_http_up").data.result[0].value[1]
    Write-Host "  ✅ probes_http_up: $http_up" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  probes_http_up: N/A" -ForegroundColor Red
}

try {
    $tcp_up = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:probes_tcp_up").data.result[0].value[1]
    Write-Host "  ✅ probes_tcp_up: $tcp_up" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  probes_tcp_up: N/A" -ForegroundColor Red
}

try {
    $days_breach = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:days_to_breach").data.result[0].value[1]
    Write-Host "  ✅ days_to_breach: $days_breach" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  days_to_breach: N/A (no payment metrics yet)" -ForegroundColor Yellow
}

try {
    $autoheal_enabled = (Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:autoheal_enabled").data.result[0].value[1]
    $status = if ($autoheal_enabled -eq "1") { "ENABLED" } else { "disabled" }
    Write-Host "  ✅ autoheal_enabled: $status" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  autoheal_enabled: N/A" -ForegroundColor Red
}

Write-Host ""
Write-Host "Autoheal Metrics:" -ForegroundColor Yellow
try {
    $autoheal_status = Invoke-RestMethod "http://localhost:9009/"
    Write-Host "  ✅ Service: $($autoheal_status.status)" -ForegroundColor Green
    Write-Host "  ✅ Enabled: $($autoheal_status.enabled)" -ForegroundColor Green
    Write-Host "  ✅ Actions: $($autoheal_status.actions.Count)" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  Autoheal service unreachable" -ForegroundColor Red
}

Write-Host ""
Write-Host "Prometheus Rules:" -ForegroundColor Yellow
try {
    $rules = Invoke-RestMethod "http://localhost:9090/api/v1/rules"
    $recording = ($rules.data.groups | Where-Object { $_.name -like '*recording*' } | ForEach-Object { $_.rules }).Count
    $alerting = ($rules.data.groups | Where-Object { $_.name -like '*alerts*' } | ForEach-Object { $_.rules }).Count
    Write-Host "  ✅ Recording rules: $recording" -ForegroundColor Green
    Write-Host "  ✅ Alert rules: $alerting" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  Could not fetch rules" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Verification Complete ===" -ForegroundColor Cyan
