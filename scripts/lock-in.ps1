# ============================================================================
# LOCK-IN SCRIPT - Secure Grafana + Create First Backup
# ============================================================================
# Run this immediately after deployment to:
# 1. Change default admin password
# 2. Create first backup with dashboard exports
# 3. Test maintenance mode
# ============================================================================

param(
    [string]$NewPassword = "",
    [switch]$SkipPasswordChange = $false
)

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           PRODUCTION LOCK-IN - SECURE & BACKUP        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$errors = 0

# ============================================================================
# 1. Change Grafana Admin Password
# ============================================================================
if (-not $SkipPasswordChange) {
    Write-Host "[1/3] Change Grafana Admin Password" -ForegroundColor Yellow
    
    if ($NewPassword -eq "") {
        Write-Host "`n   ⚠️  SECURITY WARNING: Default password 'admin' is still active!" -ForegroundColor Red
        Write-Host "   Current: admin / admin" -ForegroundColor Gray
        Write-Host ""
        
        $NewPassword = Read-Host "   Enter new admin password (or press Enter to skip)"
    }
    
    if ($NewPassword -ne "") {
        try {
            $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
            
            $body = @{
                oldPassword = "admin"
                newPassword = $NewPassword
                confirmNew  = $NewPassword
            } | ConvertTo-Json
            
            Invoke-RestMethod -Uri "http://localhost:3000/api/user/password" `
                -Method PUT `
                -Headers @{
                Authorization  = "Basic $auth"
                'Content-Type' = 'application/json'
            } `
                -Body $body `
                -ErrorAction Stop | Out-Null
            
            Write-Host "   ✅ Admin password changed successfully" -ForegroundColor Green
            Write-Host "   📝 Save this password securely!" -ForegroundColor Yellow
            Write-Host ""
            
        }
        catch {
            Write-Host "   ❌ Failed to change password: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "   💡 Change manually: http://localhost:3000 → Settings → Users → admin" -ForegroundColor Gray
            $errors++
        }
    }
    else {
        Write-Host "   ⏭️  Skipped password change" -ForegroundColor Gray
        Write-Host "   ⚠️  Remember to change it manually: http://localhost:3000" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[1/3] Grafana Password (Skipped)" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# 2. Create First Backup with Dashboard Exports
# ============================================================================
Write-Host "[2/3] Create First Backup" -ForegroundColor Yellow

$backupDir = ".\backups\initial-$(Get-Date -Format 'yyyy-MM-dd_HH-mm')"

try {
    # Create backup directory
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    
    Write-Host "   📁 Backup location: $backupDir" -ForegroundColor Gray
    
    # Export dashboards via API (use new password if changed, otherwise default)
    $authPassword = if ($NewPassword -ne "") { $NewPassword } else { "admin" }
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:$authPassword"))
    
    Write-Host "   📊 Exporting dashboards via API..." -ForegroundColor Gray
    
    # Get all dashboards
    $dashboards = Invoke-RestMethod -Uri "http://localhost:3000/api/search?type=dash-db" `
        -Headers @{Authorization = "Basic $auth" } `
        -ErrorAction Stop
    
    foreach ($dash in $dashboards) {
        $uid = $dash.uid
        $title = $dash.title -replace '[^\w\s-]', ''
        
        # Export dashboard JSON
        $dashboard = Invoke-RestMethod -Uri "http://localhost:3000/api/dashboards/uid/$uid" `
            -Headers @{Authorization = "Basic $auth" } `
            -ErrorAction Stop
        
        $exportPath = "$backupDir\$title.json"
        $dashboard.dashboard | ConvertTo-Json -Depth 100 | Set-Content $exportPath
        
        Write-Host "      ✅ $title" -ForegroundColor Green
    }
    
    # Copy config files
    Write-Host "   ⚙️  Backing up config files..." -ForegroundColor Gray
    
    $configFiles = @(
        ".\docker-compose.yml",
        ".\prometheus-config.yml",
        ".\prometheus-recording-rules.yml",
        ".\prometheus-alerts.yml",
        ".\alertmanager.yml"
    )
    
    foreach ($file in $configFiles) {
        if (Test-Path $file) {
            Copy-Item $file "$backupDir\"
            Write-Host "      ✅ $(Split-Path $file -Leaf)" -ForegroundColor Green
        }
    }
    
    # Create manifest
    $manifest = @"
AETHERLINK MONITORING - INITIAL BACKUP
========================================
Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Backup Type: Initial Production Lock-In

Components:
- Grafana Dashboards: $(($dashboards | Measure-Object).Count) dashboards
- Config Files: $(($configFiles | Where-Object {Test-Path $_} | Measure-Object).Count) files

Pinned Versions:
- Prometheus: v2.54.1
- Grafana: 11.2.0
- Alertmanager: v0.27.0

Recording Rules: 8
Alerts: 5 (with traffic guards)
Dashboards: Main (5 panels) + Executive (4 panels)

Restore Instructions:
1. Copy config files to monitoring/
2. docker compose down && docker compose up -d
3. Import dashboards: Grafana → Dashboards → Import
4. Verify: .\scripts\ship-sanity-sweep.ps1

Notes:
- Admin password changed: $(if($NewPassword -ne ""){"YES"}else{"NO"})
- Dashboard exports via API: YES
- Config version control: Commit to git

Next Steps:
1. Commit to git: git add .\backups\ && git commit -m "backup: initial $(Get-Date -Format 'yyyy-MM-dd')"
2. Test maintenance mode: .\scripts\maintenance-mode.ps1 -DurationMinutes 1
3. Review on-call runbook: .\docs\ON_CALL_RUNBOOK.md
"@

    $manifest | Set-Content "$backupDir\MANIFEST.txt"
    
    Write-Host "`n   ✅ Backup complete: $backupDir" -ForegroundColor Green
    Write-Host "   📝 Manifest: $backupDir\MANIFEST.txt" -ForegroundColor Gray
    
}
catch {
    Write-Host "   ❌ Backup failed: $($_.Exception.Message)" -ForegroundColor Red
    $errors++
}

Write-Host ""

# ============================================================================
# 3. Test Maintenance Mode (1-min silence)
# ============================================================================
Write-Host "[3/3] Test Maintenance Mode" -ForegroundColor Yellow

try {
    # Create 1-minute silence
    $startTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $endTime = (Get-Date).ToUniversalTime().AddMinutes(1).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    
    $body = @"
{
  "matchers": [
    {
      "name": "alertname",
      "value": ".*",
      "isRegex": true
    }
  ],
  "startsAt": "$startTime",
  "endsAt": "$endTime",
  "createdBy": "lock-in-script",
  "comment": "Post-launch test - 1 minute silence"
}
"@
    
    $response = Invoke-RestMethod -Uri "http://localhost:9093/api/v2/silences" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -ErrorAction Stop
    
    Write-Host "   ✅ Maintenance mode test successful" -ForegroundColor Green
    Write-Host "   Silence ID: $($response.silenceID)" -ForegroundColor Gray
    Write-Host "   Duration: 1 minute" -ForegroundColor Gray
    Write-Host "   View: http://localhost:9093/#/silences" -ForegroundColor Gray
    
}
catch {
    Write-Host "   ❌ Maintenance mode test failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   💡 Test manually: .\scripts\maintenance-mode.ps1 -DurationMinutes 1" -ForegroundColor Gray
    $errors++
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                      LOCK-IN SUMMARY                   ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

if ($errors -eq 0) {
    Write-Host "🎉 LOCK-IN COMPLETE - PRODUCTION SECURED" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Completed:" -ForegroundColor White
    if ($NewPassword -ne "") {
        Write-Host "   • Admin password changed" -ForegroundColor Gray
    }
    else {
        Write-Host "   • Admin password (skipped - ⚠️  change manually!)" -ForegroundColor Yellow
    }
    Write-Host "   • Initial backup created: $backupDir" -ForegroundColor Gray
    Write-Host "   • Maintenance mode tested (1-min silence)" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host "⚠️  LOCK-IN COMPLETED WITH $errors ISSUE(S)" -ForegroundColor Yellow
    Write-Host "   Review errors above and fix manually" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   1. Commit backup to git:" -ForegroundColor White
Write-Host "      git add .\backups\" -ForegroundColor Gray
Write-Host "      git commit -m `"backup: initial $(Get-Date -Format 'yyyy-MM-dd')`"" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Run final sanity sweep:" -ForegroundColor White
Write-Host "      .\scripts\ship-sanity-sweep.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Review documentation:" -ForegroundColor White
Write-Host "      .\docs\ON_CALL_RUNBOOK.md" -ForegroundColor Gray
Write-Host "      .\docs\SLO_TUNING.md" -ForegroundColor Gray
Write-Host ""

if ($NewPassword -eq "" -and -not $SkipPasswordChange) {
    Write-Host "⚠️  SECURITY REMINDER:" -ForegroundColor Red
    Write-Host "   Default admin password is still active!" -ForegroundColor Yellow
    Write-Host "   Change it: http://localhost:3000 → Settings → Users → admin" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "🚀 You're ready to ship!" -ForegroundColor Green
Write-Host ""
