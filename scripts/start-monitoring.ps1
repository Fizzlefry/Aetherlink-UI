#!/usr/bin/env pwsh
# Quick start script for AetherLink monitoring stack

param(
    [switch]$Stop = $false,
    [switch]$Restart = $false,
    [switch]$Logs = $false
)

$ErrorActionPreference = 'Stop'

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  AetherLink Monitoring Stack" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$monitoringDir = Join-Path $PSScriptRoot ".." "monitoring"

if (-not (Test-Path $monitoringDir)) {
    Write-Host "Error: monitoring directory not found at $monitoringDir" -ForegroundColor Red
    exit 1
}

Set-Location $monitoringDir

if ($Stop) {
    Write-Host "Stopping monitoring stack..." -ForegroundColor Yellow
    docker compose down
    Write-Host "`n✓ Monitoring stack stopped" -ForegroundColor Green
    exit 0
}

if ($Restart) {
    Write-Host "Restarting monitoring stack..." -ForegroundColor Yellow
    docker compose restart
    Write-Host "`n✓ Monitoring stack restarted" -ForegroundColor Green
    Start-Sleep -Seconds 3
}

if ($Logs) {
    Write-Host "Showing logs (Ctrl+C to exit)..." -ForegroundColor Yellow
    docker compose logs -f
    exit 0
}

# Start the stack
Write-Host "[1/4] Starting Prometheus + Grafana..." -ForegroundColor Yellow
docker compose up -d

Write-Host "`n[2/4] Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if services are running
$promStatus = docker ps --filter "name=aether-prom" --format "{{.Status}}"
$grafanaStatus = docker ps --filter "name=aether-grafana" --format "{{.Status}}"

if ($promStatus -match "Up") {
    Write-Host "  ✓ Prometheus is running" -ForegroundColor Green
}
else {
    Write-Host "  ✗ Prometheus failed to start" -ForegroundColor Red
    docker compose logs prometheus
    exit 1
}

if ($grafanaStatus -match "Up") {
    Write-Host "  ✓ Grafana is running" -ForegroundColor Green
}
else {
    Write-Host "  ✗ Grafana failed to start" -ForegroundColor Red
    docker compose logs grafana
    exit 1
}

Write-Host "`n[3/4] Verifying connections..." -ForegroundColor Yellow

# Check Prometheus targets
try {
    $targets = curl.exe -s "http://localhost:9090/api/v1/targets" | ConvertFrom-Json
    $apiTarget = $targets.data.activeTargets | Where-Object { $_.labels.job -eq "aetherlink_api" }

    if ($apiTarget) {
        if ($apiTarget.health -eq "up") {
            Write-Host "  ✓ Prometheus scraping AetherLink API" -ForegroundColor Green
        }
        else {
            Write-Host "  ⚠ AetherLink API target is down" -ForegroundColor Yellow
            Write-Host "    Make sure API is running at http://localhost:8000" -ForegroundColor Gray
            Write-Host "    Last scrape error: $($apiTarget.lastError)" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "  ⚠ AetherLink API target not configured" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ⚠ Could not verify Prometheus targets" -ForegroundColor Yellow
}

# Check Grafana
try {
    $health = curl.exe -s "http://localhost:3000/api/health" | ConvertFrom-Json
    if ($health.database -eq "ok") {
        Write-Host "  ✓ Grafana is healthy" -ForegroundColor Green
    }
}
catch {
    Write-Host "  ⚠ Grafana may still be starting up" -ForegroundColor Yellow
}

Write-Host "`n[4/4] Generating test metrics..." -ForegroundColor Yellow
Write-Host "  Running smoke test to populate dashboard..." -ForegroundColor Gray

# Check if API is available
try {
    $apiHealth = curl.exe -s "http://localhost:8000/health" | ConvertFrom-Json
    if ($apiHealth.status -eq "healthy") {
        # Run smoke test if admin key is set
        if ($env:API_ADMIN_KEY) {
            $smokeScript = Join-Path $PSScriptRoot "tenant-smoke-test.ps1"
            if (Test-Path $smokeScript) {
                & $smokeScript
            }
        }
        else {
            Write-Host "  ⚠ API_ADMIN_KEY not set - skipping smoke test" -ForegroundColor Yellow
            Write-Host "    Set it: `$env:API_ADMIN_KEY = 'admin-secret-123'" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "  ⚠ AetherLink API not available" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ⚠ AetherLink API not running at http://localhost:8000" -ForegroundColor Yellow
    Write-Host "    Start it: docker compose -f pods\customer_ops\docker-compose.yml up -d" -ForegroundColor Gray
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✓ MONITORING STACK READY" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Access points:" -ForegroundColor White
Write-Host "  Prometheus: http://localhost:9090" -ForegroundColor Cyan
Write-Host "  Grafana:    http://localhost:3000 (admin/admin)" -ForegroundColor Cyan
Write-Host ""

Write-Host "Quick commands:" -ForegroundColor White
Write-Host "  View logs:    .\scripts\start-monitoring.ps1 -Logs" -ForegroundColor Gray
Write-Host "  Restart:      .\scripts\start-monitoring.ps1 -Restart" -ForegroundColor Gray
Write-Host "  Stop:         .\scripts\start-monitoring.ps1 -Stop" -ForegroundColor Gray
Write-Host "  Smoke test:   .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Open Grafana at http://localhost:3000" -ForegroundColor Gray
Write-Host "  2. Navigate to 'AetherLink' folder → 'AetherLink RAG - Tenant Metrics'" -ForegroundColor Gray
Write-Host "     OR import enhanced dashboard: monitoring/grafana-dashboard-enhanced.json" -ForegroundColor Magenta
Write-Host "  3. Select a tenant from the dropdown" -ForegroundColor Gray
Write-Host "  4. Generate traffic: .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "🎨 New! Enhanced dashboard with 3 gauges:" -ForegroundColor Cyan
Write-Host "   • Answer Cache Hit Ratio (health proxy)" -ForegroundColor Gray
Write-Host "   • Rerank Utilization % (cost signal)" -ForegroundColor Gray
Write-Host "   • Low-Confidence Share (quality signal)" -ForegroundColor Gray
Write-Host "   See: monitoring/ENHANCED_FEATURES.md`n" -ForegroundColor Gray
