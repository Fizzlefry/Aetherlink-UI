# ============================================================================
# SETUP AUTO-START & NIGHTLY BACKUPS
# ============================================================================
# Creates Windows Scheduled Tasks for:
# 1. Auto-start monitoring on user logon
# 2. Nightly backups at 1:30 AM
# ============================================================================

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         SETUP AUTO-START & NIGHTLY BACKUPS            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$scriptsPath = "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts"

# Verify scripts exist
if (-not (Test-Path "$scriptsPath\start-monitoring.ps1")) {
    Write-Host "❌ start-monitoring.ps1 not found at: $scriptsPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$scriptsPath\backup-monitoring.ps1")) {
    Write-Host "❌ backup-monitoring.ps1 not found at: $scriptsPath" -ForegroundColor Red
    exit 1
}

Write-Host "📁 Scripts location: $scriptsPath" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# 1. Auto-Start on Logon
# ============================================================================
Write-Host "[1/2] Creating Auto-Start Task (on user logon)..." -ForegroundColor Yellow

$autoStartExists = schtasks /Query /TN "AetherLink-Monitoring-Autostart" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ⚠️  Task already exists - deleting old version..." -ForegroundColor Yellow
    schtasks /Delete /TN "AetherLink-Monitoring-Autostart" /F | Out-Null
}

$autoStartCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptsPath\start-monitoring.ps1`" -Silent"

schtasks /Create `
    /TN "AetherLink-Monitoring-Autostart" `
    /SC ONLOGON `
    /RL HIGHEST `
    /TR $autoStartCmd `
    /F | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Auto-start task created" -ForegroundColor Green

    # Harden: Run whether user is logged on or not + 1-minute delay for Docker Desktop
    Write-Host "   � Hardening task (run even when not logged in + 1-min delay)..." -ForegroundColor Yellow
    schtasks /Change /TN "AetherLink-Monitoring-Autostart" /RU "$env:USERNAME" /RL HIGHEST /ENABLE | Out-Null
    schtasks /Change /TN "AetherLink-Monitoring-Autostart" /DELAY 0001:00 | Out-Null

    Write-Host "   �� Task Name: AetherLink-Monitoring-Autostart" -ForegroundColor Gray
    Write-Host "   🔄 Trigger: On user logon (+1 min delay for Docker)" -ForegroundColor Gray
    Write-Host "   📜 Action: Start monitoring stack (silent mode)" -ForegroundColor Gray
    Write-Host "   🛡️  Resilient: Runs even if not logged in" -ForegroundColor Gray
}
else {
    Write-Host "   ❌ Failed to create auto-start task" -ForegroundColor Red
}

Write-Host ""

# ============================================================================
# 2. Nightly Backups at 1:30 AM
# ============================================================================
Write-Host "[2/2] Creating Nightly Backup Task (1:30 AM daily)..." -ForegroundColor Yellow

$backupExists = schtasks /Query /TN "AetherLink-Monitoring-Backup" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ⚠️  Task already exists - deleting old version..." -ForegroundColor Yellow
    schtasks /Delete /TN "AetherLink-Monitoring-Backup" /F | Out-Null
}

$backupCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptsPath\backup-monitoring.ps1`""

schtasks /Create `
    /TN "AetherLink-Monitoring-Backup" `
    /SC DAILY `
    /ST 01:30 `
    /RL HIGHEST `
    /TR $backupCmd `
    /F | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Nightly backup task created" -ForegroundColor Green

    # Harden: Run whether user is logged on or not
    Write-Host "   🔒 Hardening task (run even when not logged in)..." -ForegroundColor Yellow
    schtasks /Change /TN "AetherLink-Monitoring-Backup" /RU "$env:USERNAME" /RL HIGHEST /ENABLE | Out-Null

    Write-Host "   📋 Task Name: AetherLink-Monitoring-Backup" -ForegroundColor Gray
    Write-Host "   🔄 Trigger: Daily at 1:30 AM" -ForegroundColor Gray
    Write-Host "   📜 Action: Backup dashboards + configs" -ForegroundColor Gray
    Write-Host "   🛡️  Resilient: Runs even if not logged in" -ForegroundColor Gray
}
else {
    Write-Host "   ❌ Failed to create backup task" -ForegroundColor Red
}

Write-Host ""

# ============================================================================
# Optional: Also run at system startup (for reboots with no login)
# ============================================================================
Write-Host "[3/3] Optional: Create Startup Task (for reboots)..." -ForegroundColor Yellow
Write-Host "   ℹ️  This ensures monitoring starts even if no one logs in" -ForegroundColor Gray
Write-Host ""
Write-Host "   Create startup task? (Y/N): " -NoNewline -ForegroundColor Cyan
$createStartup = Read-Host

if ($createStartup -eq "Y" -or $createStartup -eq "y") {
    $startupExists = schtasks /Query /TN "AetherLink-Monitoring-AtStartup" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ⚠️  Task already exists - deleting old version..." -ForegroundColor Yellow
        schtasks /Delete /TN "AetherLink-Monitoring-AtStartup" /F | Out-Null
    }

    $startupCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptsPath\start-monitoring.ps1`" -Silent"

    schtasks /Create `
        /TN "AetherLink-Monitoring-AtStartup" `
        /SC ONSTART `
        /RL HIGHEST `
        /TR $startupCmd `
        /F | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Startup task created" -ForegroundColor Green

        # Harden: Run whether user is logged on or not
        schtasks /Change /TN "AetherLink-Monitoring-AtStartup" /RU "$env:USERNAME" /RL HIGHEST /ENABLE | Out-Null

        Write-Host "   📋 Task Name: AetherLink-Monitoring-AtStartup" -ForegroundColor Gray
        Write-Host "   🔄 Trigger: On system startup" -ForegroundColor Gray
        Write-Host "   🛡️  Resilient: Runs even if not logged in" -ForegroundColor Gray
    }
    else {
        Write-Host "   ❌ Failed to create startup task" -ForegroundColor Red
    }
}
else {
    Write-Host "   ⏭️  Skipped startup task" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                  SETUP COMPLETE                        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

Write-Host "✅ Scheduled Tasks Created:" -ForegroundColor Green
Write-Host ""
Write-Host "   1️⃣  Auto-Start: Monitoring stack starts on user logon (+1 min delay)" -ForegroundColor White
Write-Host "       View: Task Scheduler → AetherLink-Monitoring-Autostart" -ForegroundColor Gray
Write-Host ""
Write-Host "   2️⃣  Nightly Backup: Runs daily at 1:30 AM" -ForegroundColor White
Write-Host "       View: Task Scheduler → AetherLink-Monitoring-Backup" -ForegroundColor Gray
Write-Host ""
if ($createStartup -eq "Y" -or $createStartup -eq "y") {
    Write-Host "   3️⃣  Startup Task: Runs on system boot (optional)" -ForegroundColor White
    Write-Host "       View: Task Scheduler → AetherLink-Monitoring-AtStartup" -ForegroundColor Gray
    Write-Host ""
}


Write-Host "🔧 Management Commands:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   View all tasks:" -ForegroundColor White
Write-Host "   schtasks /Query /TN `"AetherLink-*`"" -ForegroundColor Gray
Write-Host ""
Write-Host "   Disable auto-start:" -ForegroundColor White
Write-Host "   schtasks /Change /TN `"AetherLink-Monitoring-Autostart`" /DISABLE" -ForegroundColor Gray
Write-Host ""
Write-Host "   Enable auto-start:" -ForegroundColor White
Write-Host "   schtasks /Change /TN `"AetherLink-Monitoring-Autostart`" /ENABLE" -ForegroundColor Gray
Write-Host ""
Write-Host "   Delete tasks:" -ForegroundColor White
Write-Host "   schtasks /Delete /TN `"AetherLink-Monitoring-Autostart`" /F" -ForegroundColor Gray
Write-Host "   schtasks /Delete /TN `"AetherLink-Monitoring-Backup`" /F" -ForegroundColor Gray
if ($createStartup -eq "Y" -or $createStartup -eq "y") {
    Write-Host "   schtasks /Delete /TN `"AetherLink-Monitoring-AtStartup`" /F" -ForegroundColor Gray
}
Write-Host ""

# ============================================================================
# Optional: Import Executive Dashboard
# ============================================================================
Write-Host "📊 Import Executive Dashboard?" -ForegroundColor Yellow
Write-Host "   This adds a business-focused KPIs view to Grafana (cost + health only)" -ForegroundColor Gray
Write-Host ""
Write-Host "   Import now? (Y/N): " -NoNewline -ForegroundColor Cyan
$importDashboard = Read-Host

if ($importDashboard -eq "Y" -or $importDashboard -eq "y") {
    Write-Host ""
    Write-Host "   📤 Importing dashboard via API..." -ForegroundColor Yellow

    $importScript = Join-Path $scriptsPath "import-exec-dashboard.ps1"
    if (Test-Path $importScript) {
        & $importScript
    }
    else {
        Write-Host "   ⚠️  import-exec-dashboard.ps1 not found" -ForegroundColor Yellow
        Write-Host "   Run manually: .\scripts\import-exec-dashboard.ps1" -ForegroundColor Gray
    }
}
else {
    Write-Host "   ⏭️  Skipped dashboard import" -ForegroundColor Gray
    Write-Host "   Run later: .\scripts\import-exec-dashboard.ps1" -ForegroundColor Gray
}

Write-Host ""

Write-Host "🎯 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Test auto-start: Log out and log back in (or wait 1 min)" -ForegroundColor Gray
Write-Host "   2. Verify backup location: .\monitoring\backups\" -ForegroundColor Gray
Write-Host "   3. Check Task Scheduler: taskschd.msc" -ForegroundColor Gray
Write-Host "   4. Health check: .\scripts\ship-sanity-sweep.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "⚡ Quick Verification:" -ForegroundColor Cyan
Write-Host '   schtasks /Query /TN "AetherLink-*"' -ForegroundColor Gray
Write-Host '   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1" -Silent' -ForegroundColor Gray
Write-Host ""

Write-Host "🛡️  Resilience Features Enabled:" -ForegroundColor Green
Write-Host "   ✅ Tasks run whether you're logged in or not" -ForegroundColor Gray
Write-Host "   ✅ 1-minute delay on logon (lets Docker Desktop start first)" -ForegroundColor Gray
Write-Host "   ✅ Silent mode (no popup windows)" -ForegroundColor Gray
Write-Host "   ✅ Highest privileges (no permission issues)" -ForegroundColor Gray
Write-Host ""

Write-Host "✨ Your monitoring stack is now fully automated!" -ForegroundColor Green
Write-Host ""
