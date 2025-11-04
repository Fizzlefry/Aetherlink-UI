#!/usr/bin/env pwsh
# Production deployment verification & hardening script

param(
    [switch]$SkipReload = $false,
    [switch]$GenerateTraffic = $false
)

$ErrorActionPreference = 'Stop'

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Production Verification & Hardening" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Hot reload Prometheus
if (-not $SkipReload) {
    Write-Host "[1/6] Hot-reloading Prometheus rules..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9090/-/reload" -Method Post -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ Prometheus rules reloaded successfully" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "  ✗ Failed to reload Prometheus" -ForegroundColor Red
        Write-Host "    Error: $_" -ForegroundColor Gray
    }
}
else {
    Write-Host "[1/6] Skipping Prometheus reload (use -SkipReload `$false to enable)" -ForegroundColor Gray
}

# Step 2: Verify recording rules loaded
Write-Host "`n[2/6] Checking recording rules..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $recordingGroup = $response.data.groups | Where-Object { $_.name -eq "aetherlink.recording" }

    if ($recordingGroup) {
        $rules = $recordingGroup.rules | Where-Object { $_.record }
        Write-Host "  ✓ Recording rules loaded: $($rules.Count) rules" -ForegroundColor Green
        foreach ($rule in $rules) {
            Write-Host "    • $($rule.record)" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "  ⚠ Recording rules not found" -ForegroundColor Yellow
        Write-Host "    Run: .\scripts\start-monitoring.ps1 -Restart" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ✗ Could not query rules" -ForegroundColor Red
}

# Step 3: Verify new alerts loaded
Write-Host "`n[3/6] Checking new alerts..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $alerts = $response.data.groups.rules | Where-Object { $_.alert } | Select-Object -ExpandProperty alert

    $requiredAlerts = @(
        "CacheEffectivenessDrop",
        "LowConfidenceSpike",
        "LowConfidenceSpikeVIP",
        "CacheEffectivenessDropVIP"
    )

    $found = @()
    $missing = @()

    foreach ($alert in $requiredAlerts) {
        if ($alerts -contains $alert) {
            $found += $alert
            Write-Host "  ✓ $alert" -ForegroundColor Green
        }
        else {
            $missing += $alert
            Write-Host "  ✗ $alert (missing)" -ForegroundColor Red
        }
    }

    if ($missing.Count -eq 0) {
        Write-Host "`n  All 4 production alerts loaded!" -ForegroundColor Green
    }
    else {
        Write-Host "`n  ⚠ $($missing.Count) alerts missing - reload Prometheus" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ✗ Could not query alerts" -ForegroundColor Red
}

# Step 4: Test PromQL queries
Write-Host "`n[4/6] Testing PromQL queries..." -ForegroundColor Yellow

$queries = @(
    @{
        name  = "Cache hit ratio (recording rule)"
        query = "aether:cache_hit_ratio:5m"
    },
    @{
        name  = "Rerank utilization (recording rule)"
        query = "aether:rerank_utilization_pct:15m"
    },
    @{
        name  = "Low-confidence share (recording rule)"
        query = "aether:lowconfidence_pct:15m"
    }
)

foreach ($q in $queries) {
    try {
        $encoded = [uri]::EscapeDataString($q.query)
        $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/query?query=$encoded" -UseBasicParsing

        if ($response.status -eq "success" -and $response.data.result.Count -gt 0) {
            Write-Host "  ✓ $($q.name)" -ForegroundColor Green
        }
        else {
            Write-Host "  ⚠ $($q.name) - no data yet" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  ✗ $($q.name) - query failed" -ForegroundColor Red
    }
}

# Step 5: Check Prometheus targets
Write-Host "`n[5/6] Checking Prometheus targets..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/targets" -UseBasicParsing
    $apiTarget = $response.data.activeTargets | Where-Object { $_.job -eq "aetherlink_api" }

    if ($apiTarget -and $apiTarget.health -eq "up") {
        Write-Host "  ✓ AetherLink API target is UP" -ForegroundColor Green
        Write-Host "    Last scrape: $($apiTarget.lastScrape)" -ForegroundColor Gray
    }
    else {
        Write-Host "  ⚠ API target not healthy" -ForegroundColor Yellow
        Write-Host "    Start API: docker compose -f pods/customer_ops/docker-compose.yml up -d" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ✗ Could not query targets" -ForegroundColor Red
}

# Step 6: Check Alertmanager
Write-Host "`n[6/6] Checking Alertmanager..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9093/-/healthy" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ Alertmanager is healthy" -ForegroundColor Green
        Write-Host "    URL: http://localhost:9093" -ForegroundColor Gray
    }
}
catch {
    Write-Host "  ⚠ Alertmanager not running" -ForegroundColor Yellow
    Write-Host "    To enable: Set SLACK_WEBHOOK_URL and restart stack" -ForegroundColor Gray
}

# Generate traffic if requested
if ($GenerateTraffic) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Generating Test Traffic" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan

    if (-not $env:API_ADMIN_KEY) {
        Write-Host "⚠ API_ADMIN_KEY not set. Set it first:" -ForegroundColor Yellow
        Write-Host '  $env:API_ADMIN_KEY = "admin-secret-123"' -ForegroundColor Gray
    }
    else {
        $smokeTestPath = Join-Path $PSScriptRoot "tenant-smoke-test.ps1"
        if (Test-Path $smokeTestPath) {
            Write-Host "Running smoke test..." -ForegroundColor Yellow
            & $smokeTestPath
        }
        else {
            Write-Host "⚠ Smoke test script not found" -ForegroundColor Yellow
        }
    }
}

# Summary & Next Steps
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "🔍 View dashboards & alerts:" -ForegroundColor White
Write-Host "  • Prometheus rules:  http://localhost:9090/rules" -ForegroundColor Gray
Write-Host "  • Prometheus alerts: http://localhost:9090/alerts" -ForegroundColor Gray
Write-Host "  • Grafana dashboards: http://localhost:3000" -ForegroundColor Gray
Write-Host "  • Alertmanager:      http://localhost:9093" -ForegroundColor Gray

Write-Host "`n📊 PromQL spot checks (run in Prometheus UI):" -ForegroundColor White
Write-Host "  # Cache hit ratio per tenant (5m)" -ForegroundColor Gray
Write-Host "  aether:cache_hit_ratio:5m" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # Rerank utilization per tenant (15m)" -ForegroundColor Gray
Write-Host "  aether:rerank_utilization_pct:15m" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # Low-confidence share per tenant (15m)" -ForegroundColor Gray
Write-Host "  aether:lowconfidence_pct:15m" -ForegroundColor Cyan

Write-Host "`n🚀 Generate test traffic:" -ForegroundColor White
Write-Host '  $env:API_ADMIN_KEY = "admin-secret-123"' -ForegroundColor Gray
Write-Host "  .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray

Write-Host "`n🔔 Enable Slack alerts:" -ForegroundColor White
Write-Host '  $env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"' -ForegroundColor Gray
Write-Host "  .\scripts\start-monitoring.ps1 -Restart" -ForegroundColor Gray

Write-Host "`n✅ Production-ready checklist:" -ForegroundColor White
Write-Host "  ☐ Recording rules loaded (6 rules)" -ForegroundColor Gray
Write-Host "  ☐ New alerts loaded (4 alerts)" -ForegroundColor Gray
Write-Host "  ☐ Enhanced dashboard auto-provisioned" -ForegroundColor Gray
Write-Host "  ☐ VIP tenant regex matches your naming" -ForegroundColor Gray
Write-Host "  ☐ Alertmanager connected (optional)" -ForegroundColor Gray

Write-Host ""
