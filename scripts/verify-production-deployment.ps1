#!/usr/bin/env pwsh
# Quick verification script for production deployment

$ErrorActionPreference = 'Stop'

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Production Deployment Verification" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$checks = @()

# Check 1: Prometheus is up
Write-Host "[1/8] Checking Prometheus health..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ Prometheus is healthy" -ForegroundColor Green
        $checks += $true
    }
}
catch {
    Write-Host "  ✗ Prometheus not responding" -ForegroundColor Red
    $checks += $false
}

# Check 2: Grafana is up
Write-Host "[2/8] Checking Grafana health..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ Grafana is healthy" -ForegroundColor Green
        $checks += $true
    }
}
catch {
    Write-Host "  ✗ Grafana not responding" -ForegroundColor Red
    $checks += $false
}

# Check 3: New alerts loaded
Write-Host "[3/8] Checking new alerts loaded..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $alerts = $response.data.groups.rules | Where-Object { $_.alert } | Select-Object -ExpandProperty alert
    
    $newAlerts = @("CacheEffectivenessDrop", "LowConfidenceSpike", "LowConfidenceSpikeVIP", "CacheEffectivenessDropVIP")
    $found = 0
    foreach ($alert in $newAlerts) {
        if ($alerts -contains $alert) {
            $found++
        }
    }
    
    if ($found -eq 4) {
        Write-Host "  ✓ All 4 new alerts loaded" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ Only $found/4 new alerts found" -ForegroundColor Yellow
        Write-Host "    Missing alerts - run: curl.exe -X POST http://localhost:9090/-/reload" -ForegroundColor Gray
        $checks += $false
    }
}
catch {
    Write-Host "  ✗ Could not check alerts" -ForegroundColor Red
    $checks += $false
}

# Check 4: Recording rules loaded (optional)
Write-Host "[4/8] Checking recording rules..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $recordingGroup = $response.data.groups | Where-Object { $_.name -eq "aetherlink.recording" }
    
    if ($recordingGroup) {
        $ruleCount = $recordingGroup.rules.Count
        Write-Host "  ✓ Recording rules loaded ($ruleCount rules)" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ Recording rules not loaded (optional)" -ForegroundColor Yellow
        Write-Host "    To enable: Restart stack with .\scripts\start-monitoring.ps1 -Restart" -ForegroundColor Gray
        $checks += $true  # Don't fail on optional feature
    }
}
catch {
    Write-Host "  ⚠ Could not check recording rules" -ForegroundColor Yellow
    $checks += $true  # Don't fail on optional feature
}

# Check 5: AetherLink API metrics
Write-Host "[5/8] Checking API metrics endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -UseBasicParsing -TimeoutSec 5
    if ($response.Content -match "aether_rag_answers_total") {
        Write-Host "  ✓ API metrics available" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ Metrics endpoint up but no RAG metrics" -ForegroundColor Yellow
        $checks += $false
    }
}
catch {
    Write-Host "  ✗ API not responding at http://localhost:8000" -ForegroundColor Red
    Write-Host "    Start API with: docker compose -f pods/customer_ops/docker-compose.yml up -d" -ForegroundColor Gray
    $checks += $false
}

# Check 6: Prometheus scraping API
Write-Host "[6/8] Checking Prometheus targets..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/targets" -UseBasicParsing
    $apiTarget = $response.data.activeTargets | Where-Object { $_.job -eq "aetherlink_api" }
    
    if ($apiTarget -and $apiTarget.health -eq "up") {
        Write-Host "  ✓ Prometheus scraping API successfully" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ API target not healthy" -ForegroundColor Yellow
        $checks += $false
    }
}
catch {
    Write-Host "  ✗ Could not check targets" -ForegroundColor Red
    $checks += $false
}

# Check 7: Test PromQL queries
Write-Host "[7/8] Testing PromQL queries..." -ForegroundColor Yellow
try {
    $query = "(sum(rate(aether_cache_hits_total[5m]))/sum(rate(aether_cache_requests_total[5m])))*100"
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/query?query=$([uri]::EscapeDataString($query))" -UseBasicParsing
    
    if ($response.status -eq "success") {
        Write-Host "  ✓ Cache hit ratio query works" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ Query returned no data (generate traffic first)" -ForegroundColor Yellow
        $checks += $true  # Don't fail if no data yet
    }
}
catch {
    Write-Host "  ✗ Query failed" -ForegroundColor Red
    $checks += $false
}

# Check 8: Enhanced dashboard file exists
Write-Host "[8/8] Checking dashboard file..." -ForegroundColor Yellow
$dashboardPath = Join-Path $PSScriptRoot ".." "monitoring" "grafana-dashboard-enhanced.json"
if (Test-Path $dashboardPath) {
    $content = Get-Content $dashboardPath -Raw | ConvertFrom-Json
    if ($content.uid -eq "aetherlink_rag_tenant_metrics_enhanced") {
        Write-Host "  ✓ Enhanced dashboard file ready for import" -ForegroundColor Green
        $checks += $true
    }
    else {
        Write-Host "  ⚠ Dashboard file exists but UID mismatch" -ForegroundColor Yellow
        $checks += $false
    }
}
else {
    Write-Host "  ✗ Dashboard file not found" -ForegroundColor Red
    $checks += $false
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
$passed = ($checks | Where-Object { $_ -eq $true }).Count
$total = $checks.Count
$percentage = [math]::Round(($passed / $total) * 100, 0)

if ($passed -eq $total) {
    Write-Host "  ✓ ALL CHECKS PASSED ($passed/$total)" -ForegroundColor Green
}
elseif ($passed -ge ($total * 0.75)) {
    Write-Host "  ⚠ MOSTLY READY ($passed/$total - $percentage%)" -ForegroundColor Yellow
}
else {
    Write-Host "  ✗ NEEDS ATTENTION ($passed/$total - $percentage%)" -ForegroundColor Red
}
Write-Host "========================================`n" -ForegroundColor Cyan

# Next steps
if ($passed -eq $total) {
    Write-Host "🎉 Production deployment verified!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Import dashboard: http://localhost:3000" -ForegroundColor Gray
    Write-Host "     → Dashboards → Import → monitoring/grafana-dashboard-enhanced.json" -ForegroundColor Gray
    Write-Host "  2. Generate test data: .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
    Write-Host "  3. View dashboard: http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced`n" -ForegroundColor Gray
}
else {
    Write-Host "⚠ Fix issues above, then re-run verification:" -ForegroundColor Yellow
    Write-Host "  .\scripts\verify-production-deployment.ps1`n" -ForegroundColor Gray
}
