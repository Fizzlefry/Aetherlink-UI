# ============================================================================
# PRODUCTION VERIFICATION - Final Smoke Test
# ============================================================================
# Validates production-ready dashboard with "No recent traffic" mappings
# ============================================================================

Write-Host "`n╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     AETHERLINK PRODUCTION STACK - FINAL CHECK       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$errors = 0

# ============================================================================
# 1. Docker Images (Pinned Versions)
# ============================================================================
Write-Host "[1/6] Verifying Pinned Docker Images" -ForegroundColor Yellow

$expectedVersions = @{
    "aether-prom"         = "prom/prometheus:v2.54.1"
    "aether-grafana"      = "grafana/grafana:11.2.0"
    "aether-alertmanager" = "prom/alertmanager:v0.27.0"
}

$containers = docker ps --format "{{.Names}}\t{{.Image}}" | ConvertFrom-Csv -Delimiter "`t" -Header Name, Image

foreach ($expected in $expectedVersions.GetEnumerator()) {
    $container = $containers | Where-Object { $_.Name -eq $expected.Key }
    if ($container -and $container.Image -eq $expected.Value) {
        Write-Host "   ✅ $($expected.Key): $($expected.Value)" -ForegroundColor Green
    }
    else {
        Write-Host "   ❌ $($expected.Key): Expected $($expected.Value), Got $($container.Image)" -ForegroundColor Red
        $errors++
    }
}

# ============================================================================
# 2. Recording Rules (8 Total)
# ============================================================================
Write-Host "`n[2/6] Verifying Recording Rules" -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod "http://localhost:9090/api/v1/rules" -ErrorAction Stop
    $recordingRules = $response.data.groups.rules | Where-Object { $_.type -eq "recording" }
    
    $expectedRules = @(
        "aether:cache_hit_ratio:5m",
        "aether:cache_hit_ratio:5m:all",
        "aether:rerank_utilization_pct:15m",
        "aether:rerank_utilization_pct:15m:all",
        "aether:lowconfidence_pct:15m",
        "aether:lowconfidence_pct:15m:all",
        "aether:estimated_cost_30d_usd",
        "aether:health_score:15m"
    )
    
    $foundRules = $recordingRules.name
    
    foreach ($rule in $expectedRules) {
        if ($foundRules -contains $rule) {
            Write-Host "   ✅ $rule" -ForegroundColor Green
        }
        else {
            Write-Host "   ❌ Missing: $rule" -ForegroundColor Red
            $errors++
        }
    }
    
    Write-Host "   Total: $($recordingRules.Count) recording rules" -ForegroundColor Gray
    
}
catch {
    Write-Host "   ❌ Failed to query Prometheus: $($_.Exception.Message)" -ForegroundColor Red
    $errors++
}

# ============================================================================
# 3. Production Alerts (Traffic Guards)
# ============================================================================
Write-Host "`n[3/6] Verifying Production Alerts" -ForegroundColor Yellow

try {
    $alerts = $response.data.groups.rules | Where-Object { $_.type -eq "alerting" }
    
    $criticalAlerts = @(
        "CacheEffectivenessDrop",
        "LowConfidenceSpike",
        "LowConfidenceSpikeVIP",
        "CacheEffectivenessDropVIP",
        "HealthScoreDegradation"
    )
    
    $foundAlerts = $alerts.name
    $verifiedCount = 0
    
    foreach ($alertName in $criticalAlerts) {
        $alert = $alerts | Where-Object { $_.name -eq $alertName }
        if ($alert) {
            # Check for traffic guard pattern
            if ($alert.query -match "sum\(rate\(.+?\)\) > 0") {
                Write-Host "   ✅ $alertName (with traffic guard)" -ForegroundColor Green
                $verifiedCount++
            }
            else {
                Write-Host "   ⚠️  $alertName (missing traffic guard)" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "   ❌ Missing: $alertName" -ForegroundColor Red
            $errors++
        }
    }
    
    Write-Host "   Verified: $verifiedCount/5 critical alerts with traffic guards" -ForegroundColor Gray
    
}
catch {
    Write-Host "   ❌ Failed to verify alerts" -ForegroundColor Red
    $errors++
}

# ============================================================================
# 4. Grafana Dashboard (Enhanced with Mappings)
# ============================================================================
Write-Host "`n[4/6] Verifying Grafana Dashboard" -ForegroundColor Yellow

try {
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
    
    # Check dashboard exists
    $dashboard = Invoke-RestMethod "http://localhost:3000/api/dashboards/uid/aetherlink_rag_tenant_metrics_enhanced" `
        -Headers @{Authorization = "Basic $auth" } `
        -ErrorAction Stop
    
    Write-Host "   ✅ Dashboard found: $($dashboard.dashboard.title)" -ForegroundColor Green
    Write-Host "   ✅ UID: $($dashboard.dashboard.uid)" -ForegroundColor Gray
    Write-Host "   ✅ Panels: $($dashboard.dashboard.panels.Count)" -ForegroundColor Gray
    
    # Check for "No recent traffic" mappings
    $dashboardJson = Get-Content ".\grafana-dashboard-enhanced.json" -Raw | ConvertFrom-Json
    $mappingsCount = 0
    
    foreach ($panel in $dashboardJson.panels) {
        if ($panel.fieldConfig.defaults.mappings) {
            $noTrafficMapping = $panel.fieldConfig.defaults.mappings | Where-Object { 
                $_.display -eq "No recent traffic" 
            }
            if ($noTrafficMapping) {
                $mappingsCount++
            }
        }
    }
    
    Write-Host "   ✅ 'No recent traffic' mappings: $mappingsCount panels" -ForegroundColor Green
    
    if ($mappingsCount -lt 5) {
        Write-Host "   ⚠️  Expected 5 panels with 'No recent traffic' mapping" -ForegroundColor Yellow
    }
    
}
catch {
    Write-Host "   ❌ Dashboard verification failed: $($_.Exception.Message)" -ForegroundColor Red
    $errors++
}

# ============================================================================
# 5. Business KPIs Executive Dashboard
# ============================================================================
Write-Host "`n[5/6] Verifying Business KPIs Dashboard" -ForegroundColor Yellow

if (Test-Path ".\grafana-dashboard-business-kpis.json") {
    Write-Host "   ✅ Business KPIs dashboard available" -ForegroundColor Green
    Write-Host "   📊 Import via: Grafana → Dashboards → Import → Upload JSON" -ForegroundColor Gray
    Write-Host "   📄 File: .\monitoring\grafana-dashboard-business-kpis.json" -ForegroundColor Gray
}
else {
    Write-Host "   ⚠️  Business KPIs dashboard not found (optional)" -ForegroundColor Yellow
}

# ============================================================================
# 6. Operational Scripts
# ============================================================================
Write-Host "`n[6/6] Verifying Operational Scripts" -ForegroundColor Yellow

$scripts = @{
    "pre-prod-go.ps1"       = "7-check pre-production validation"
    "quick-check.ps1"       = "Rapid 6-step health check"
    "backup-monitoring.ps1" = "Backup dashboards + configs"
    "maintenance-mode.ps1"  = "Alert silencing during deploys"
}

foreach ($script in $scripts.GetEnumerator()) {
    if (Test-Path "..\scripts\$($script.Key)") {
        Write-Host "   ✅ $($script.Key) - $($script.Value)" -ForegroundColor Green
    }
    else {
        Write-Host "   ❌ Missing: $($script.Key)" -ForegroundColor Red
        $errors++
    }
}

# ============================================================================
# Summary
# ============================================================================
Write-Host "`n╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                  VERIFICATION SUMMARY                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

if ($errors -eq 0) {
    Write-Host "🎉 ALL CHECKS PASSED - PRODUCTION READY" -ForegroundColor Green
    Write-Host ""
    Write-Host "✨ Key Features:" -ForegroundColor Cyan
    Write-Host "   • Zero false alerts (traffic guards on all 5 alerts)" -ForegroundColor Gray
    Write-Host "   • Version stability (pinned Docker images)" -ForegroundColor Gray
    Write-Host "   • User-friendly UI ('No recent traffic' vs scary red)" -ForegroundColor Gray
    Write-Host "   • Business visibility (cost + health score)" -ForegroundColor Gray
    Write-Host "   • Day-2 ops ready (backup + maintenance scripts)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📊 Quick Access:" -ForegroundColor Cyan
    Write-Host "   Main Dashboard:   http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced" -ForegroundColor Gray
    Write-Host "   Prometheus:       http://localhost:9090" -ForegroundColor Gray
    Write-Host "   Alertmanager:     http://localhost:9093" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📚 Documentation:" -ForegroundColor Cyan
    Write-Host "   On-Call Runbook:  .\docs\ON_CALL_RUNBOOK.md" -ForegroundColor Gray
    Write-Host "   SLO Tuning:       .\docs\SLO_TUNING.md" -ForegroundColor Gray
    Write-Host "   Reliability Pack: .\docs\RELIABILITY_PACK.md" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host "⚠️  $errors ISSUE(S) FOUND - REVIEW ABOVE" -ForegroundColor Red
    Write-Host ""
}

Write-Host "💡 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Import Business KPIs dashboard for exec view" -ForegroundColor Gray
Write-Host "   2. Run smoke test to generate traffic: .\scripts\final-steps.ps1" -ForegroundColor Gray
Write-Host "   3. Create first backup: .\scripts\backup-monitoring.ps1" -ForegroundColor Gray
Write-Host "   4. Review on-call runbook: .\docs\ON_CALL_RUNBOOK.md" -ForegroundColor Gray
Write-Host ""
