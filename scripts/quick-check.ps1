# ============================================================================
# POST-DEPLOY QUICK CHECK - First Data Validation
# ============================================================================

Write-Host "`n=== POST-DEPLOY CHECKLIST ===" -ForegroundColor Cyan

# 1. Check containers
Write-Host "`n[1/6] Container Health" -ForegroundColor Yellow
$containers = docker ps --filter "name=aether" --format "{{.Names}}"
if ($containers -match "aether-prom") { Write-Host "  ✅ Prometheus running" -ForegroundColor Green } else { Write-Host "  ❌ Prometheus not running" -ForegroundColor Red }
if ($containers -match "aether-grafana") { Write-Host "  ✅ Grafana running" -ForegroundColor Green } else { Write-Host "  ❌ Grafana not running" -ForegroundColor Red }
if ($containers -match "aether-alertmanager") { Write-Host "  ✅ Alertmanager running" -ForegroundColor Green } else { Write-Host "  ❌ Alertmanager not running" -ForegroundColor Red }

# 2. Check recording rules
Write-Host "`n[2/6] Recording Rules" -ForegroundColor Yellow
try {
    $rules = Invoke-RestMethod "http://localhost:9090/api/v1/rules"
    $recGroup = $rules.data.groups | Where-Object { $_.name -eq "aetherlink.recording" }
    if ($recGroup -and $recGroup.rules.Count -eq 6) {
        Write-Host "  ✅ All 6 recording rules loaded" -ForegroundColor Green
    }
    else {
        Write-Host "  ❌ Recording rules missing" -ForegroundColor Red
    }
}
catch {
    Write-Host "  ❌ Cannot query Prometheus" -ForegroundColor Red
}

# 3. Check alerts with traffic guards
Write-Host "`n[3/6] Production Alerts" -ForegroundColor Yellow
$alertGroup = $rules.data.groups | Where-Object { $_.name -eq "aetherlink_rag.rules" }
$prodAlerts = @("CacheEffectivenessDrop", "LowConfidenceSpike", "LowConfidenceSpikeVIP", "CacheEffectivenessDropVIP")
$guardCount = 0
foreach ($name in $prodAlerts) {
    $alert = $alertGroup.rules | Where-Object { $_.name -eq $name }
    if ($alert -and $alert.query -match "and sum\(rate") {
        $guardCount++
    }
}
if ($guardCount -eq 4) {
    Write-Host "  ✅ All 4 alerts have traffic guards" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  Only $guardCount/4 alerts have traffic guards" -ForegroundColor Yellow
}

# 4. Check Grafana
Write-Host "`n[4/6] Grafana Auto-Provisioning" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod "http://localhost:3000/api/health"
    if ($health.database -eq "ok") {
        Write-Host "  ✅ Grafana healthy" -ForegroundColor Green
    }

    $dashboards = Invoke-RestMethod "http://admin:admin@localhost:3000/api/search?type=dash-db"
    $enhanced = $dashboards | Where-Object { $_.title -match "Enhanced" }
    if ($enhanced) {
        Write-Host "  ✅ Enhanced dashboard provisioned" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠️  Dashboard not found (may take 30-60s)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ❌ Cannot access Grafana" -ForegroundColor Red
}

# 5. Check API metrics endpoint
Write-Host "`n[5/6] API Metrics Endpoint" -ForegroundColor Yellow
try {
    $metrics = Invoke-WebRequest "http://localhost:8000/metrics" -TimeoutSec 3
    if ($metrics.StatusCode -eq 200) {
        Write-Host "  ✅ API /metrics reachable" -ForegroundColor Green
        if ($metrics.Content -match "aether_rag_answers_total") {
            Write-Host "  ✅ Key metrics present" -ForegroundColor Green
        }
    }
}
catch {
    Write-Host "  ⚠️  API not running (start with: cd pods\customer-ops; docker compose up -d)" -ForegroundColor Yellow
}

# 6. Check if recording rules have data
Write-Host "`n[6/6] Recording Rules Data" -ForegroundColor Yellow
try {
    $result = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aether:cache_hit_ratio:5m"
    $hasData = $false
    foreach ($series in $result.data.result) {
        if ($series.value[1] -ne "NaN") {
            $hasData = $true
            $tenant = $series.metric.tenant
            $value = [math]::Round([double]$series.value[1], 1)
            Write-Host "  ✅ Tenant '$tenant': $value%" -ForegroundColor Green
        }
    }
    if (-not $hasData) {
        Write-Host "  ⚠️  No data yet (generate traffic to populate)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ❌ Cannot query recording rules" -ForegroundColor Red
}

# Summary
Write-Host "`n=== NEXT STEPS ===" -ForegroundColor Cyan
Write-Host "1. Start API: cd pods\customer-ops; docker compose up -d" -ForegroundColor Gray
Write-Host "2. Generate traffic: `$env:API_ADMIN_KEY='admin-secret-123'; .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
Write-Host "3. Open Grafana: http://localhost:3000 (admin/admin)" -ForegroundColor Gray
Write-Host "4. View rules: http://localhost:9090/rules" -ForegroundColor Gray
Write-Host ""
