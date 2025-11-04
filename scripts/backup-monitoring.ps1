# ============================================================================
# BACKUP SCRIPT - Export Grafana Dashboards + Prometheus Snapshots
# ============================================================================
# Creates backups of all monitoring configs and dashboards
# ============================================================================

param(
    [string]$BackupDir = ".\monitoring\backups\$(Get-Date -Format 'yyyy-MM-dd_HH-mm')"
)

Write-Host "`n=== MONITORING BACKUP ===" -ForegroundColor Cyan
Write-Host "Backup destination: $BackupDir`n" -ForegroundColor Gray

# Create backup directory
New-Item -ItemType Directory -Force -Path "$BackupDir\grafana" | Out-Null
New-Item -ItemType Directory -Force -Path "$BackupDir\prometheus" | Out-Null
New-Item -ItemType Directory -Force -Path "$BackupDir\configs" | Out-Null

$errors = 0

# ============================================================================
# 1. Export Grafana Dashboard
# ============================================================================
Write-Host "[1/4] Exporting Grafana dashboard..." -ForegroundColor Yellow

try {
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
    
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
        
        $exportPath = "$BackupDir\grafana\$title.json"
        $dashboard.dashboard | ConvertTo-Json -Depth 100 | Set-Content $exportPath
        
        Write-Host "   ✅ Exported: $title" -ForegroundColor Green
    }
    
}
catch {
    Write-Host "   ❌ Grafana export failed: $($_.Exception.Message)" -ForegroundColor Red
    $errors++
}

# ============================================================================
# 2. Backup Prometheus Data (TSDB Snapshot)
# ============================================================================
Write-Host "`n[2/4] Creating Prometheus snapshot..." -ForegroundColor Yellow

try {
    # Create TSDB snapshot
    $snapshot = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/admin/tsdb/snapshot" `
        -Method POST `
        -ErrorAction Stop
    
    if ($snapshot.status -eq "success") {
        $snapshotName = $snapshot.data.name
        Write-Host "   ✅ Snapshot created: $snapshotName" -ForegroundColor Green
        
        # Copy snapshot from container
        Write-Host "   📦 Copying snapshot data..." -ForegroundColor Gray
        docker cp "aether-prom:/prometheus/snapshots/$snapshotName" "$BackupDir\prometheus\" 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Snapshot exported" -ForegroundColor Green
        }
        else {
            Write-Host "   ⚠️  Snapshot created but copy failed (may need --enable-feature=admin-api)" -ForegroundColor Yellow
            Write-Host "   Manual export: docker exec aether-prom tar czf /tmp/snapshot.tar.gz /prometheus/snapshots/$snapshotName" -ForegroundColor Gray
            $errors++
        }
    }
    
}
catch {
    Write-Host "   ⚠️  Snapshot failed: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "   Add --enable-feature=admin-api to Prometheus command to enable snapshots" -ForegroundColor Gray
    $errors++
}

# ============================================================================
# 3. Backup Configuration Files
# ============================================================================
Write-Host "`n[3/4] Backing up config files..." -ForegroundColor Yellow

$configFiles = @(
    ".\monitoring\docker-compose.yml",
    ".\monitoring\prometheus-config.yml",
    ".\monitoring\prometheus-recording-rules.yml",
    ".\monitoring\prometheus-alerts.yml",
    ".\monitoring\alertmanager.yml",
    ".\monitoring\grafana-dashboard-enhanced.json"
)

foreach ($file in $configFiles) {
    if (Test-Path $file) {
        $filename = Split-Path $file -Leaf
        Copy-Item $file "$BackupDir\configs\$filename"
        Write-Host "   ✅ $filename" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  Not found: $filename" -ForegroundColor Yellow
    }
}

# ============================================================================
# 4. Create Backup Manifest
# ============================================================================
Write-Host "`n[4/4] Creating backup manifest..." -ForegroundColor Yellow

$manifest = @"
AETHER MONITORING BACKUP
========================
Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Location: $BackupDir

Components:
- Grafana Dashboards: $(($dashboards | Measure-Object).Count) dashboards
- Prometheus Data: TSDB snapshot (if admin-api enabled)
- Config Files: $(($configFiles | Where-Object {Test-Path $_} | Measure-Object).Count) files

Pinned Versions:
- Prometheus: v2.54.1
- Grafana: 11.2.0
- Alertmanager: v0.27.0

Recording Rules: 8 total
- aether:cache_hit_ratio:5m (per-tenant + :all)
- aether:rerank_utilization_pct:15m (per-tenant + :all)
- aether:lowconfidence_pct:15m (per-tenant + :all)
- aether:estimated_cost_30d_usd
- aether:health_score:15m

Alerts: 5 total (all with traffic guards)
- CacheEffectivenessDrop
- LowConfidenceSpike
- LowConfidenceSpikeVIP
- CacheEffectivenessDropVIP
- HealthScoreDegradation

Restore Instructions:
1. Copy config files from backups/configs/ to monitoring/
2. docker compose up -d
3. Import Grafana dashboards from backups/grafana/
4. (Optional) Restore TSDB data from backups/prometheus/

Errors: $errors
"@

$manifest | Set-Content "$BackupDir\MANIFEST.txt"
Write-Host "   ✅ Manifest created" -ForegroundColor Green

# ============================================================================
# Summary
# ============================================================================
Write-Host "`n=== BACKUP COMPLETE ===" -ForegroundColor Cyan
Write-Host "📁 Location: $BackupDir" -ForegroundColor Green
Write-Host "📊 Dashboards: $(($dashboards | Measure-Object).Count)" -ForegroundColor Gray
Write-Host "⚙️  Configs: $(($configFiles | Where-Object {Test-Path $_} | Measure-Object).Count)" -ForegroundColor Gray

if ($errors -gt 0) {
    Write-Host "⚠️  $errors warnings/errors (see above)" -ForegroundColor Yellow
}

Write-Host "`n💡 Commit to git:" -ForegroundColor Cyan
Write-Host "   git add .\monitoring\backups\" -ForegroundColor Gray
Write-Host "   git commit -m `"backup: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`"" -ForegroundColor Gray
Write-Host ""
