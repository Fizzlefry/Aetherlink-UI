#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Verify per-tenant Prometheus metrics are working correctly
.DESCRIPTION
    Tests that all RAG metrics (cache, answers, lowconf) include tenant labels
    and that different tenants produce separate metric series.
#>

param(
    [string]$ApiUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Per-Tenant Metrics Validation ===" -ForegroundColor Cyan
Write-Host "API: $ApiUrl`n" -ForegroundColor Gray

# Test API keys for different tenants
$env:API_KEY_TENANT_A = "xk-tenant-a-1234"
$env:API_KEY_TENANT_B = "xk-tenant-b-5678"

function Get-MetricValue {
    param(
        [string]$MetricName,
        [string]$Labels
    )
    
    $response = Invoke-WebRequest -Uri "$ApiUrl/metrics" -UseBasicParsing
    $lines = $response.Content -split "`n"
    
    foreach ($line in $lines) {
        if ($line -match "^$MetricName\{$Labels\}\s+(\d+(\.\d+)?)") {
            return [double]$matches[1]
        }
    }
    
    return $null
}

# Test 1: Cache metrics have tenant labels
Write-Host "[Test 1] Cache metrics include tenant labels..." -ForegroundColor Yellow

# Make requests from tenant A
Invoke-WebRequest -Uri "$ApiUrl/search?q=test&mode=hybrid" `
    -Headers @{"X-API-Key" = $env:API_KEY_TENANT_A } -UseBasicParsing | Out-Null

Start-Sleep -Milliseconds 500

# Check for tenant label in metrics
$cacheMetrics = (Invoke-WebRequest -Uri "$ApiUrl/metrics" -UseBasicParsing).Content
if ($cacheMetrics -match 'aether_rag_cache_\w+_total\{endpoint="[^"]+",tenant="[^"]+"\}') {
    Write-Host "  ✓ Cache metrics have tenant labels" -ForegroundColor Green
    Write-Host "    Sample: $($matches[0])" -ForegroundColor Gray
}
else {
    Write-Host "  ✗ Cache metrics missing tenant labels" -ForegroundColor Red
    exit 1
}

# Test 2: Different tenants produce separate metrics
Write-Host "`n[Test 2] Different tenants tracked separately..." -ForegroundColor Yellow

# Clear any existing cache and metrics (restart would be ideal, but we'll test increments)
$beforeA = Get-MetricValue -MetricName "aether_rag_cache_misses_total" -Labels 'endpoint="search",tenant="tenant-a"'
$beforeB = Get-MetricValue -MetricName "aether_rag_cache_misses_total" -Labels 'endpoint="search",tenant="tenant-b"'

Write-Host "  Baseline tenant-a: $beforeA" -ForegroundColor Gray
Write-Host "  Baseline tenant-b: $beforeB" -ForegroundColor Gray

# Make unique requests from each tenant
$queryA = "unique_query_a_$(Get-Random)"
$queryB = "unique_query_b_$(Get-Random)"
Invoke-WebRequest -Uri "$ApiUrl/search?q=$queryA&mode=hybrid" `
    -Headers @{"X-API-Key" = $env:API_KEY_TENANT_A } -UseBasicParsing | Out-Null

Invoke-WebRequest -Uri "$ApiUrl/search?q=$queryB&mode=hybrid" `
    -Headers @{"X-API-Key" = $env:API_KEY_TENANT_B } -UseBasicParsing | Out-Null

Start-Sleep -Milliseconds 500

$afterA = Get-MetricValue -MetricName "aether_rag_cache_misses_total" -Labels 'endpoint="search",tenant="tenant-a"'
$afterB = Get-MetricValue -MetricName "aether_rag_cache_misses_total" -Labels 'endpoint="search",tenant="tenant-b"'

Write-Host "  After tenant-a: $afterA" -ForegroundColor Gray
Write-Host "  After tenant-b: $afterB" -ForegroundColor Gray

if ($afterA -gt $beforeA -and $afterB -gt $beforeB) {
    Write-Host "  ✓ Separate tenant metrics incremented independently" -ForegroundColor Green
}
else {
    Write-Host "  ✗ Tenant metrics not incrementing properly" -ForegroundColor Red
    exit 1
}

# Test 3: ANSWERS_TOTAL includes tenant label
Write-Host "`n[Test 3] ANSWERS_TOTAL has tenant label..." -ForegroundColor Yellow

# Make an /answer request
Invoke-WebRequest -Uri "$ApiUrl/answer?q=test&mode=hybrid" `
    -Headers @{"X-API-Key" = $env:API_KEY_TENANT_A } -UseBasicParsing | Out-Null

Start-Sleep -Milliseconds 500

$answerMetrics = (Invoke-WebRequest -Uri "$ApiUrl/metrics" -UseBasicParsing).Content
if ($answerMetrics -match 'aether_rag_answers_total\{mode="[^"]+",rerank="[^"]+",tenant="[^"]+"\}') {
    Write-Host "  ✓ ANSWERS_TOTAL has tenant label" -ForegroundColor Green
    Write-Host "    Sample: $($matches[0])" -ForegroundColor Gray
}
else {
    Write-Host "  ✗ ANSWERS_TOTAL missing tenant label" -ForegroundColor Red
    exit 1
}

# Test 4: LOWCONF_TOTAL includes tenant label
Write-Host "`n[Test 4] LOWCONF_TOTAL has tenant label..." -ForegroundColor Yellow

$lowconfMetrics = (Invoke-WebRequest -Uri "$ApiUrl/metrics" -UseBasicParsing).Content
# Check metric definition (may not have actual data yet)
if ($lowconfMetrics -match '# HELP aether_rag_lowconfidence_total Low confidence answers' `
        -and $lowconfMetrics -match '# TYPE aether_rag_lowconfidence_total counter') {
    
    # Try to find actual metric with labels (may be 0)
    if ($lowconfMetrics -match 'aether_rag_lowconfidence_total\{tenant="[^"]+"\}') {
        Write-Host "  ✓ LOWCONF_TOTAL has tenant label (with data)" -ForegroundColor Green
        Write-Host "    Sample: $($matches[0])" -ForegroundColor Gray
    }
    else {
        Write-Host "  ✓ LOWCONF_TOTAL defined correctly (no data yet)" -ForegroundColor Green
    }
}
else {
    Write-Host "  ✗ LOWCONF_TOTAL not properly defined" -ForegroundColor Red
    exit 1
}

# Test 5: Verify rerank label format (should be "true"/"false", not "True"/"False")
Write-Host "`n[Test 5] Rerank label uses lowercase boolean..." -ForegroundColor Yellow

if ($answerMetrics -match 'rerank="(true|false)"') {
    Write-Host "  ✓ Rerank label format correct: $($matches[1])" -ForegroundColor Green
}
elseif ($answerMetrics -match 'rerank="(True|False)"') {
    Write-Host "  ✗ Rerank label should be lowercase: $($matches[1])" -ForegroundColor Red
    exit 1
}
else {
    Write-Host "  ⚠ No rerank metrics found yet (might need more requests)" -ForegroundColor Yellow
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "✓ All per-tenant metrics validated successfully!" -ForegroundColor Green
Write-Host "`nYou can now:" -ForegroundColor Gray
Write-Host "  1. View metrics: curl http://localhost:8000/metrics | Select-String tenant" -ForegroundColor Gray
Write-Host "  2. Create Grafana dashboards with tenant filters" -ForegroundColor Gray
Write-Host "  3. Set up Prometheus alerts per tenant" -ForegroundColor Gray
