# Autoheal Provision - Aetherlink Platform Setup
# Ensures directories, starts services, reloads configs

Write-Host ""
Write-Host "Autoheal Provision - Aetherlink Platform" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Gray

# Ensure data directory exists
$dataPath = "C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\data\autoheal"
if (!(Test-Path $dataPath)) {
    Write-Host ""
    Write-Host "Creating data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $dataPath | Out-Null
    Write-Host "   Created: $dataPath" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "Data directory exists: $dataPath" -ForegroundColor Green
}

# Check if audit trail exists
$auditFile = Join-Path $dataPath "audit.jsonl"
if (Test-Path $auditFile) {
    $lineCount = (Get-Content $auditFile | Measure-Object -Line).Lines
    Write-Host "   Audit trail: $lineCount events" -ForegroundColor Gray
}
else {
    Write-Host "   Audit trail: empty (will be created on first event)" -ForegroundColor Gray
}

# Start services
Write-Host ""
Write-Host "Starting monitoring services..." -ForegroundColor Yellow
docker compose --profile dev up -d autoheal prometheus grafana alertmanager

# Wait for services to be ready
Write-Host ""
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Reload Prometheus configuration
Write-Host ""
Write-Host "Reloading Prometheus configuration..." -ForegroundColor Yellow
try {
    Invoke-RestMethod -Method POST 'http://localhost:9090/-/reload' -ErrorAction Stop
    Write-Host "   Prometheus reloaded" -ForegroundColor Green
}
catch {
    Write-Host "   Failed to reload Prometheus: $($_.Exception.Message)" -ForegroundColor Red
}

# Test autoheal health
Write-Host ""
Write-Host "Testing autoheal health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod 'http://localhost:9009/' -ErrorAction Stop
    Write-Host "   Autoheal running" -ForegroundColor Green
    Write-Host "      - Enabled: $($health.enabled)" -ForegroundColor Gray
    Write-Host "      - Dry-run: $($health.dry_run)" -ForegroundColor Gray
    Write-Host "      - Actions: $($health.actions.Count)" -ForegroundColor Gray
}
catch {
    Write-Host "   Autoheal not responding: $($_.Exception.Message)" -ForegroundColor Red
}

# Test audit endpoint
Write-Host ""
Write-Host "Testing audit endpoint..." -ForegroundColor Yellow
try {
    $audit = Invoke-RestMethod 'http://localhost:9009/audit?n=1' -ErrorAction Stop
    Write-Host "   Audit endpoint working ($($audit.count) events)" -ForegroundColor Green
}
catch {
    Write-Host "   Audit endpoint not responding: $($_.Exception.Message)" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "==================================================" -ForegroundColor Gray
Write-Host "Autoheal provisioned successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick Access:" -ForegroundColor Cyan
Write-Host "   - Audit trail: $auditFile" -ForegroundColor Gray
Write-Host "   - Console: http://localhost:9009/console" -ForegroundColor Gray
Write-Host "   - API: http://localhost:9009/" -ForegroundColor Gray
Write-Host "   - Metrics: http://localhost:9009/metrics" -ForegroundColor Gray
Write-Host "   - Dashboard: http://localhost:3000/d/autoheal" -ForegroundColor Gray
Write-Host ""
Write-Host "Run '.\monitoring\scripts\open-autoheal.ps1' to open all interfaces" -ForegroundColor Gray
Write-Host ""
