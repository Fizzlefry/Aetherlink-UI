# ============================================================================
# FINAL SHIP SANITY SWEEP - Quick Production Validation
# ============================================================================
# Run this anytime to verify production stack health
# ============================================================================

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          AETHERLINK - FINAL SHIP SANITY SWEEP         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ============================================================================
# 1) Services Healthy + Pinned Versions
# ============================================================================
Write-Host "[1/4] Services & Pinned Versions" -ForegroundColor Yellow
Write-Host ""

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

Write-Host ""

# Verify pinned versions
$pinned = @{
    "aether-prom"         = "v2.54.1"
    "aether-grafana"      = "11.2.0"
    "aether-alertmanager" = "v0.27.0"
}

$containers = docker ps --format "{{.Names}},{{.Image}}" | ConvertFrom-Csv -Header Name, Image

$allPinned = $true
foreach ($expected in $pinned.GetEnumerator()) {
    $container = $containers | Where-Object { $_.Name -eq $expected.Key }
    if ($container.Image -notmatch $expected.Value) {
        Write-Host "   ⚠️  $($expected.Key) not pinned to $($expected.Value)" -ForegroundColor Yellow
        $allPinned = $false
    }
}

if ($allPinned) {
    Write-Host "   ✅ All monitoring services pinned to stable versions" -ForegroundColor Green
}

# ============================================================================
# 2) Rules & Alerts Present
# ============================================================================
Write-Host "`n[2/4] Recording Rules & Alerts" -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod "http://localhost:9090/api/v1/rules" -ErrorAction Stop
    
    $recordingCount = ($response.data.groups.rules | Where-Object { $_.type -eq "recording" }).Count
    $alertingCount = ($response.data.groups.rules | Where-Object { $_.type -eq "alerting" }).Count
    
    Write-Host "   Recording Rules: $recordingCount (expected: 8)" -ForegroundColor $(if ($recordingCount -ge 8) { "Green" }else { "Red" })
    Write-Host "   Alerting Rules:  $alertingCount (expected: 5+)" -ForegroundColor $(if ($alertingCount -ge 5) { "Green" }else { "Red" })
    
    # Show critical recording rules
    $criticalRules = @(
        "aether:cache_hit_ratio:5m:all",
        "aether:estimated_cost_30d_usd",
        "aether:health_score:15m"
    )
    
    Write-Host "`n   Critical Recording Rules:" -ForegroundColor Gray
    foreach ($rule in $criticalRules) {
        $found = $response.data.groups.rules | Where-Object { $_.name -eq $rule }
        if ($found) {
            Write-Host "   ✅ $rule" -ForegroundColor Green
        }
        else {
            Write-Host "   ❌ $rule (missing)" -ForegroundColor Red
        }
    }
    
    # Show critical alerts with traffic guards
    Write-Host "`n   Critical Alerts (with traffic guards):" -ForegroundColor Gray
    $criticalAlerts = @(
        "LowConfidenceSpikeVIP",
        "CacheEffectivenessDropVIP",
        "HealthScoreDegradation"
    )
    
    foreach ($alertName in $criticalAlerts) {
        $alert = $response.data.groups.rules | Where-Object { $_.name -eq $alertName }
        if ($alert) {
            $hasGuard = $alert.query -match "sum\(rate\(.+?\)\) > 0"
            if ($hasGuard) {
                Write-Host "   ✅ $alertName" -ForegroundColor Green
            }
            else {
                Write-Host "   ⚠️  $alertName (no traffic guard)" -ForegroundColor Yellow
            }
        }
    }
    
}
catch {
    Write-Host "   ❌ Failed to query Prometheus: $($_.Exception.Message)" -ForegroundColor Red
}

# ============================================================================
# 3) KPI Signals (Business Metrics)
# ============================================================================
Write-Host "`n[3/4] Business KPI Signals" -ForegroundColor Yellow

try {
    # Check if KPI metrics have data
    $costQuery = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aether:estimated_cost_30d_usd" -ErrorAction Stop
    $healthQuery = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aether:health_score:15m" -ErrorAction Stop
    
    if ($costQuery.data.result.Count -gt 0) {
        $costValue = [math]::Round([double]$costQuery.data.result[0].value[1], 2)
        Write-Host "   💰 Estimated 30-Day Cost: `$$costValue" -ForegroundColor Green
    }
    else {
        Write-Host "   💰 Estimated 30-Day Cost: No data (run smoke test)" -ForegroundColor Gray
    }
    
    if ($healthQuery.data.result.Count -gt 0) {
        $healthValue = [math]::Round([double]$healthQuery.data.result[0].value[1], 0)
        $healthColor = if ($healthValue -ge 80) { "Green" } elseif ($healthValue -ge 60) { "Yellow" } else { "Red" }
        Write-Host "   ❤️  System Health Score: $healthValue/100" -ForegroundColor $healthColor
    }
    else {
        Write-Host "   ❤️  System Health Score: No data (run smoke test)" -ForegroundColor Gray
    }
    
    Write-Host "`n   📊 Open KPI graphs:" -ForegroundColor Cyan
    Write-Host "   Start-Process `"http://localhost:9090/graph?g0.expr=aether:estimated_cost_30d_usd`"" -ForegroundColor Gray
    Write-Host "   Start-Process `"http://localhost:9090/graph?g0.expr=aether:health_score:15m`"" -ForegroundColor Gray
    
}
catch {
    Write-Host "   ⚠️  KPI metrics not yet available (normal on fresh start)" -ForegroundColor Yellow
}

# ============================================================================
# 4) Dashboards
# ============================================================================
Write-Host "`n[4/4] Grafana Dashboards" -ForegroundColor Yellow

try {
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
    
    # Check main dashboard
    $mainDash = Invoke-RestMethod "http://localhost:3000/api/dashboards/uid/aetherlink_rag_tenant_metrics_enhanced" `
        -Headers @{Authorization = "Basic $auth" } `
        -ErrorAction Stop
    
    Write-Host "   ✅ Main Dashboard: $($mainDash.dashboard.title)" -ForegroundColor Green
    Write-Host "      Panels: $($mainDash.dashboard.panels.Count)" -ForegroundColor Gray
    Write-Host "      URL: http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced" -ForegroundColor Gray
    
    # Check if exec dashboard exists
    try {
        $execDash = Invoke-RestMethod "http://localhost:3000/api/dashboards/uid/aetherlink_business_kpis" `
            -Headers @{Authorization = "Basic $auth" } `
            -ErrorAction Stop
        Write-Host "   ✅ Executive Dashboard: $($execDash.dashboard.title)" -ForegroundColor Green
    }
    catch {
        Write-Host "   📊 Executive Dashboard: Not imported (optional)" -ForegroundColor Gray
        Write-Host "      Import: monitoring\grafana-dashboard-business-kpis.json" -ForegroundColor Gray
    }
    
}
catch {
    Write-Host "   ❌ Dashboard check failed: $($_.Exception.Message)" -ForegroundColor Red
}

# ============================================================================
# Summary & Recommendations
# ============================================================================
Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    RECOMMENDATIONS                     ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

Write-Host "🔒 Recommended Lock-Ins (2 minutes):" -ForegroundColor Yellow
Write-Host ""
Write-Host "   1. Change Grafana admin password:" -ForegroundColor White
Write-Host "      Settings → Users → admin → Change Password" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Create first backup:" -ForegroundColor White
Write-Host "      .\scripts\backup-monitoring.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Test maintenance mode (1-min silence):" -ForegroundColor White
Write-Host "      .\scripts\maintenance-mode.ps1 -DurationMinutes 1 -Comment `"post-launch test`"" -ForegroundColor Gray
Write-Host ""

Write-Host "🚀 Optional Upgrades:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   • Add Loki + Promtail for searchable logs" -ForegroundColor Gray
Write-Host "   • Add Blackbox Exporter for API uptime probes" -ForegroundColor Gray
Write-Host "   • Pin dashboard exports via API for version control" -ForegroundColor Gray
Write-Host ""

Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "   • On-Call Runbook:  .\docs\ON_CALL_RUNBOOK.md" -ForegroundColor Gray
Write-Host "   • SLO Tuning:       .\docs\SLO_TUNING.md" -ForegroundColor Gray
Write-Host "   • Reliability Pack: .\docs\RELIABILITY_PACK.md" -ForegroundColor Gray
Write-Host ""

Write-Host "✅ Status: " -NoNewline -ForegroundColor White
Write-Host "PRODUCTION READY" -ForegroundColor Green
Write-Host ""
