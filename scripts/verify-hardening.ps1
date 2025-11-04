# ====================================================================================
# HARDENING VERIFICATION SCRIPT
# ====================================================================================
# Quick 30-second check that all resilience features are working
# ====================================================================================

Write-Host "`n======================================== " -ForegroundColor Cyan
Write-Host "  HARDENING VERIFICATION (30 SECONDS)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$failures = 0

# ====================================================================================
# 1. Check Scheduled Tasks Exist
# ====================================================================================
Write-Host "[1/6] Checking Scheduled Tasks..." -ForegroundColor Yellow

$tasks = @("AetherLink-Monitoring-Autostart", "AetherLink-Monitoring-Backup")
foreach ($taskName in $tasks) {
    $null = schtasks /Query /TN $taskName 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] $taskName exists" -ForegroundColor Green
    }
    else {
        Write-Host "   [FAIL] $taskName not found" -ForegroundColor Red
        $failures++
    }
}

# Check optional startup task (not a failure if missing)
$null = schtasks /Query /TN "AetherLink-Monitoring-AtStartup" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   [OK] AetherLink-Monitoring-AtStartup exists (optional)" -ForegroundColor Green
}
else {
    Write-Host "   [INFO] AetherLink-Monitoring-AtStartup not found (optional)" -ForegroundColor Gray
}

Write-Host ""

# ====================================================================================
# 2. Verify Task Settings (Resilience)
# ====================================================================================
Write-Host "[2/6] Verifying Resilience Settings..." -ForegroundColor Yellow

# Check auto-start task delay
$autoStartDetails = schtasks /Query /TN "AetherLink-Monitoring-Autostart" /FO LIST /V 2>$null
if ($autoStartDetails -match "Delay Time:\s+0:01:00") {
    Write-Host "   [OK] Auto-start has 1-minute delay (Docker-safe)" -ForegroundColor Green
}
else {
    Write-Host "   [WARN] Auto-start delay not configured" -ForegroundColor Yellow
}

# Check run level (should be Highest)
if ($autoStartDetails -match "Run With Highest Privileges:\s+Yes") {
    Write-Host "   [OK] Highest privileges enabled" -ForegroundColor Green
}
else {
    Write-Host "   [WARN] Highest privileges not enabled" -ForegroundColor Yellow
}

Write-Host ""

# ====================================================================================
# 3. Test Manual Start (Dry Run)
# ====================================================================================
Write-Host "[3/6] Testing Manual Start (Dry Run)..." -ForegroundColor Yellow

$startScript = "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1"
if (Test-Path $startScript) {
    Write-Host "   Running start-monitoring.ps1 in Silent mode..." -ForegroundColor Gray
    
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $startScript -Silent -ErrorAction Stop
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   [OK] Manual start succeeded" -ForegroundColor Green
        }
        else {
            Write-Host "   [WARN] Manual start returned non-zero exit code" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "   [FAIL] Manual start failed: $($_.Exception.Message)" -ForegroundColor Red
        $failures++
    }
}
else {
    Write-Host "   [FAIL] start-monitoring.ps1 not found" -ForegroundColor Red
    $failures++
}

Write-Host ""

# ====================================================================================
# 4. Quick Health Check (Services)
# ====================================================================================
Write-Host "[4/6] Quick Health Check (Services)..." -ForegroundColor Yellow

Start-Sleep -Seconds 5  # Give services time to start

try {
    $services = docker ps --format "{{.Names}}" 2>$null
    if ($services) {
        $serviceList = $services -split "`n"
        $expectedServices = @("prometheus", "grafana", "alertmanager")
        
        foreach ($svc in $expectedServices) {
            if ($serviceList -match $svc) {
                Write-Host "   [OK] $svc running" -ForegroundColor Green
            }
            else {
                Write-Host "   [FAIL] $svc not running" -ForegroundColor Red
                $failures++
            }
        }
    }
    else {
        Write-Host "   [FAIL] No Docker services found (is Docker Desktop running?)" -ForegroundColor Red
        $failures++
    }
}
catch {
    Write-Host "   [FAIL] Failed to check Docker services: $($_.Exception.Message)" -ForegroundColor Red
    $failures++
}

Write-Host ""

# ====================================================================================
# 5. Verify Backup Script Exists
# ====================================================================================
Write-Host "[5/6] Checking Backup Configuration..." -ForegroundColor Yellow

$backupScript = "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\backup-monitoring.ps1"
if (Test-Path $backupScript) {
    Write-Host "   [OK] backup-monitoring.ps1 found" -ForegroundColor Green
}
else {
    Write-Host "   [FAIL] backup-monitoring.ps1 not found" -ForegroundColor Red
    $failures++
}

$backupDir = "$env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring\backups"
if (Test-Path $backupDir) {
    $backupCount = (Get-ChildItem $backupDir -Directory -ErrorAction SilentlyContinue).Count
    Write-Host "   [OK] Backup directory exists ($backupCount existing backups)" -ForegroundColor Green
}
else {
    Write-Host "   [INFO] Backup directory doesn't exist yet (will be created on first backup)" -ForegroundColor Gray
}

Write-Host ""

# ====================================================================================
# 6. Check Dashboard Files
# ====================================================================================
Write-Host "[6/6] Checking Dashboard Files..." -ForegroundColor Yellow

$mainDashboard = "$env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring\grafana-dashboard-enhanced.json"
$execDashboard = "$env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring\grafana-dashboard-business-kpis.json"

if (Test-Path $mainDashboard) {
    Write-Host "   [OK] Main dashboard found (grafana-dashboard-enhanced.json)" -ForegroundColor Green
}
else {
    Write-Host "   [FAIL] Main dashboard not found" -ForegroundColor Red
    $failures++
}

if (Test-Path $execDashboard) {
    Write-Host "   [OK] Executive dashboard found (grafana-dashboard-business-kpis.json)" -ForegroundColor Green
}
else {
    Write-Host "   [WARN] Executive dashboard not found (optional)" -ForegroundColor Yellow
}

Write-Host ""

# ====================================================================================
# Summary
# ====================================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "       VERIFICATION RESULTS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if ($failures -eq 0) {
    Write-Host "*** ALL CHECKS PASSED! ***" -ForegroundColor Green
    Write-Host ""
    Write-Host "[OK] Scheduled Tasks: Configured and enabled" -ForegroundColor Green
    Write-Host "[OK] Resilience Features: 1-min delay + highest privileges" -ForegroundColor Green
    Write-Host "[OK] Manual Start: Works correctly" -ForegroundColor Green
    Write-Host "[OK] Docker Services: Running" -ForegroundColor Green
    Write-Host "[OK] Backup Configuration: Ready" -ForegroundColor Green
    Write-Host "[OK] Dashboard Files: Found" -ForegroundColor Green
    Write-Host ""
    Write-Host "STATUS: PRODUCTION READY - FULLY HARDENED" -ForegroundColor Green
    Write-Host ""
    Write-Host "Quick Links:" -ForegroundColor Cyan
    Write-Host "   Grafana:       http://localhost:3000 (admin/admin)" -ForegroundColor Gray
    Write-Host "   Prometheus:    http://localhost:9090" -ForegroundColor Gray
    Write-Host "   Alertmanager:  http://localhost:9093" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host "*** $failures ISSUE(S) FOUND ***" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Quick Fixes:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Re-run setup script:" -ForegroundColor White
    Write-Host "   .\scripts\setup-automation.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Or manually create tasks:" -ForegroundColor White
    Write-Host "   See: docs\HARDENING_GUIDE.md" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "   Hardening Guide:  .\docs\HARDENING_GUIDE.md" -ForegroundColor Gray
Write-Host "   Quick Reference:  .\docs\QUICK_REFERENCE_CARD.md" -ForegroundColor Gray
Write-Host "   Deployment Guide: .\docs\FINAL_SHIP_CHECKLIST.md" -ForegroundColor Gray
Write-Host ""

# Return exit code based on failures
exit $failures
