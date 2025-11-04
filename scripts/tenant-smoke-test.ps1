#!/usr/bin/env pwsh
# Tenant metrics smoke test - fully automated, no env setup required

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$AdminKey = $env:API_ADMIN_KEY
)

$ErrorActionPreference = 'Stop'

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TENANT METRICS SMOKE TEST" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 0: Check API health
Write-Host "[1/6] Checking API health..." -ForegroundColor Yellow
try {
    $health = curl.exe -s "$BaseUrl/health" | ConvertFrom-Json
    if ($health.status -eq "healthy") {
        Write-Host "  ✓ API is healthy" -ForegroundColor Green
    }
    else {
        Write-Host "  ✗ API returned: $($health.status)" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "  ✗ API not responding at $BaseUrl" -ForegroundColor Red
    Write-Host "  Run: docker compose -f pods\customer_ops\docker-compose.yml ps" -ForegroundColor Gray
    exit 1
}

# Step 1: Fetch editor API key
Write-Host "`n[2/6] Fetching editor API key..." -ForegroundColor Yellow
if (-not $AdminKey) {
    Write-Host "  ✗ API_ADMIN_KEY not set" -ForegroundColor Red
    Write-Host "  Set it: `$env:API_ADMIN_KEY = 'admin-secret-123'" -ForegroundColor Gray
    exit 1
}

try {
    $keys = curl.exe -s -H "x-admin-key: $AdminKey" "$BaseUrl/admin/apikeys" | ConvertFrom-Json
    $editorKey = ($keys.items | Where-Object { $_.role -eq 'editor' } | Select-Object -First 1)

    if ($editorKey) {
        Write-Host "  ✓ Found editor key for tenant: $($editorKey.tenant_id)" -ForegroundColor Green
        Write-Host "    Key: $($editorKey.key.Substring(0, 12))..." -ForegroundColor Gray
    }
    else {
        Write-Host "  ✗ No editor API keys found" -ForegroundColor Red
        Write-Host "  Create one via: POST /admin/apikeys" -ForegroundColor Gray
        exit 1
    }
}
catch {
    Write-Host "  ✗ Failed to fetch API keys" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Gray
    exit 1
}

# Step 2: Make search request to bump counters
Write-Host "`n[3/6] Making search request..." -ForegroundColor Yellow
try {
    $null = curl.exe -s -H "X-API-Key: $($editorKey.key)" "$BaseUrl/search?q=test&mode=hybrid"
    Write-Host "  ✓ Search request completed" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ Search request failed" -ForegroundColor Red
    exit 1
}

# Step 3: Make answer request with rerank
Write-Host "`n[4/6] Making answer request..." -ForegroundColor Yellow
try {
    $null = curl.exe -s -H "X-API-Key: $($editorKey.key)" "$BaseUrl/answer?q=storm%20collar&mode=hybrid&rerank=true"
    Write-Host "  ✓ Answer request completed" -ForegroundColor Green
}
catch {
    Write-Host "  ✗ Answer request failed" -ForegroundColor Red
    exit 1
}

Start-Sleep -Seconds 1

# Step 4: Fetch and parse metrics
Write-Host "`n[5/6] Fetching metrics..." -ForegroundColor Yellow
$metrics = curl.exe -s "$BaseUrl/metrics"
$tenantMetrics = $metrics | Select-String 'aether_rag_.*tenant='

if ($tenantMetrics) {
    Write-Host "  ✓ Found tenant-labeled metrics" -ForegroundColor Green
}
else {
    Write-Host "  ✗ No tenant-labeled metrics found" -ForegroundColor Red
    Write-Host "`n  Troubleshooting:" -ForegroundColor Yellow
    Write-Host "    1. Restart API: docker compose -f pods\customer_ops\docker-compose.yml restart api" -ForegroundColor Gray
    Write-Host "    2. Check code: pods/customer_ops/api/main.py (search for '.labels(.*tenant=')" -ForegroundColor Gray
    Write-Host "    3. Verify auth sets tenant_id in request.state" -ForegroundColor Gray
    exit 1
}

# Step 5: Display results
Write-Host "`n[6/6] Tenant Metrics Summary:" -ForegroundColor Yellow
Write-Host "  Tenant: $($editorKey.tenant_id)" -ForegroundColor Cyan
Write-Host "  ----------------------------------------" -ForegroundColor Gray

$cacheHits = $tenantMetrics | Select-String "cache_hits_total"
$cacheMisses = $tenantMetrics | Select-String "cache_misses_total"
$answers = $tenantMetrics | Select-String "answers_total"
$lowconf = $tenantMetrics | Select-String "lowconfidence_total"

if ($cacheHits) {
    Write-Host "`n  Cache Hits:" -ForegroundColor Green
    $cacheHits | Select-Object -First 3 | ForEach-Object { Write-Host "    $($_.Line)" -ForegroundColor White }
}

if ($cacheMisses) {
    Write-Host "`n  Cache Misses:" -ForegroundColor Yellow
    $cacheMisses | Select-Object -First 3 | ForEach-Object { Write-Host "    $($_.Line)" -ForegroundColor White }
}

if ($answers) {
    Write-Host "`n  Answers:" -ForegroundColor Cyan
    $answers | Select-Object -First 3 | ForEach-Object { Write-Host "    $($_.Line)" -ForegroundColor White }
}

if ($lowconf) {
    Write-Host "`n  Low Confidence:" -ForegroundColor Magenta
    $lowconf | Select-Object -First 2 | ForEach-Object { Write-Host "    $($_.Line)" -ForegroundColor White }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✓ SMOKE TEST PASSED" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next steps:" -ForegroundColor Gray
Write-Host "  - View all metrics: curl $BaseUrl/metrics | Select-String tenant" -ForegroundColor Gray
Write-Host "  - Run full validation: .\scripts\validate-quick-wins.ps1" -ForegroundColor Gray
Write-Host "  - Test red team mode: .\scripts\validate-quick-wins.ps1 -Strict`n" -ForegroundColor Gray
