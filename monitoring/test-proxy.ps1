# Test Nginx Proxy and Slack Buttons
# Usage: .\test-proxy.ps1 -User "aether" -Password "YourPassword"

param(
    [string]$User = "aether",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host "=== TESTING NGINX PROXY ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Grafana (no auth)
Write-Host "🧪 Test 1: Grafana (no auth required)" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://grafana.aetherlink.local" -Method Head -TimeoutSec 5 -UseBasicParsing
    Write-Host "   ✅ Status: $($response.StatusCode) - Grafana accessible" -ForegroundColor Green
}
catch {
    Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Tip: Check if nginx-proxy is running and hosts file is configured" -ForegroundColor Yellow
}
Write-Host ""

# Test 2: Alertmanager (auth required - should fail without creds)
Write-Host "🧪 Test 2: Alertmanager (no auth - should get 401)" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://alertmanager.aetherlink.local" -Method Head -TimeoutSec 5 -UseBasicParsing
    Write-Host "   ⚠️  Status: $($response.StatusCode) - Auth not working!" -ForegroundColor Yellow
}
catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   ✅ Status: 401 - Auth is working (expected)" -ForegroundColor Green
    }
    else {
        Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host ""

# Test 3: Alertmanager (with auth)
Write-Host "🧪 Test 3: Alertmanager (with auth credentials)" -ForegroundColor Yellow
try {
    $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
    $headers = @{
        Authorization = "Basic $base64Auth"
    }
    $response = Invoke-WebRequest -Uri "http://alertmanager.aetherlink.local" -Method Head -Headers $headers -TimeoutSec 5 -UseBasicParsing
    Write-Host "   ✅ Status: $($response.StatusCode) - Auth successful" -ForegroundColor Green
}
catch {
    Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Tip: Check username/password" -ForegroundColor Yellow
}
Write-Host ""

# Test 4: Alertmanager API (silences endpoint)
Write-Host "🧪 Test 4: Alertmanager Silences API" -ForegroundColor Yellow
try {
    $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
    $headers = @{
        Authorization = "Basic $base64Auth"
    }
    $response = Invoke-RestMethod -Uri "http://alertmanager.aetherlink.local/api/v2/silences" -Method Get -Headers $headers -TimeoutSec 5
    Write-Host "   ✅ Silences API accessible - Found $($response.Count) silences" -ForegroundColor Green
}
catch {
    Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 5: Slack Button URLs
Write-Host "=== SLACK BUTTON URL TESTS ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Dashboard Button URL:" -ForegroundColor Yellow
Write-Host "   http://grafana.aetherlink.local/d/crm-events-pipeline" -ForegroundColor White
Write-Host "   Click this in Slack → Should open Grafana dashboard" -ForegroundColor Gray
Write-Host ""

Write-Host "🔍 Prometheus Button URL:" -ForegroundColor Yellow
Write-Host "   http://alertmanager.aetherlink.local/#/alerts" -ForegroundColor White
Write-Host "   Click this in Slack → Should open Alertmanager alerts page" -ForegroundColor Gray
Write-Host ""

Write-Host "🔕 Silence Button URL:" -ForegroundColor Yellow
Write-Host "   http://alertmanager.aetherlink.local/#/silences/new?filter=%7Bteam%3D%22crm%22%2Cservice%3D%22crm-events-sse%22%7D" -ForegroundColor White
Write-Host "   Click this in Slack → Should open pre-filled silence form with auth prompt" -ForegroundColor Gray
Write-Host ""

Write-Host "=== TEST COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 NEXT STEPS:" -ForegroundColor Cyan
Write-Host "   1. Trigger an alert to test Slack buttons:" -ForegroundColor White
Write-Host "      docker stop aether-crm-events" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Wait 7 minutes for alert to fire" -ForegroundColor White
Write-Host ""
Write-Host "   3. Check Slack #crm-events-alerts channel" -ForegroundColor White
Write-Host ""
Write-Host "   4. Click buttons to verify they work from anywhere" -ForegroundColor White
Write-Host ""
Write-Host "   5. Restart service when done:" -ForegroundColor White
Write-Host "      docker start aether-crm-events" -ForegroundColor Gray
Write-Host ""
