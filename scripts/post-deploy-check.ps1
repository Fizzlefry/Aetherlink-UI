# ============================================================================
# POST-DEPLOY CHECKLIST - First Data & Polish
# ============================================================================
# Validates monitoring stack, tests API connectivity, and verifies metrics flow
# ============================================================================

param(
    [switch]$SkipAPICheck
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

Write-Host @"

╔═══════════════════════════════════════════════════════════════════════════╗
║                  POST-DEPLOY CHECKLIST - First Data                       ║
║            Verify metrics flow & dashboards light up                      ║
╚═══════════════════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

$checks = @{
    passed   = @()
    warnings = @()
    failed   = @()
}

function Test-Check {
    param($Name, $Test, [switch]$Critical)

    Write-Host "  🔍 $Name..." -NoNewline

    if ($Test) {
        Write-Host " ✅" -ForegroundColor Green
        $script:checks.passed += $Name
        return $true
    }
    else {
        if ($Critical) {
            Write-Host " ❌" -ForegroundColor Red
            $script:checks.failed += $Name
        }
        else {
            Write-Host " ⚠️" -ForegroundColor Yellow
            $script:checks.warnings += $Name
        }
        return $false
    }
}

# ============================================================================
# CHECK 1: CONTAINERS RUNNING
# ============================================================================
Write-Host "`n[1/6] Container Health" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

$containers = docker ps --filter "name=aether-prom" --filter "name=aether-grafana" --filter "name=aether-alertmanager" --format "{{.Names}}"
Test-Check "Prometheus container" ($containers -match "aether-prom") -Critical
Test-Check "Grafana container" ($containers -match "aether-grafana") -Critical
Test-Check "Alertmanager container" ($containers -match "aether-alertmanager")

# ============================================================================
# CHECK 2: RECORDING RULES
# ============================================================================
Write-Host "`n[2/6] Recording Rules (6 expected)" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

try {
    $rules = Invoke-RestMethod "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $recordingGroup = $rules.data.groups | Where-Object { $_.name -eq "aetherlink.recording" } | Select-Object -First 1

    if ($recordingGroup -and $recordingGroup.rules.Count -eq 6) {
        Test-Check "All 6 recording rules loaded" $true

        $expectedRules = @(
            "aether:cache_hit_ratio:5m",
            "aether:rerank_utilization_pct:15m",
            "aether:lowconfidence_pct:15m",
            "aether:cache_hit_ratio:5m:all",
            "aether:rerank_utilization_pct:15m:all",
            "aether:lowconfidence_pct:15m:all"
        )

        foreach ($expected in $expectedRules) {
            $found = $recordingGroup.rules | Where-Object { $_.name -eq $expected }
            if ($found) {
                Write-Host "    ✓ $expected" -ForegroundColor DarkGreen
            }
            else {
                Write-Host "    ✗ $expected (missing)" -ForegroundColor Red
            }
        }
    }
    else {
        Test-Check "Recording rules loaded" $false -Critical
    }
}
catch {
    Test-Check "Recording rules accessible" $false -Critical
}

# ============================================================================
# CHECK 3: PRODUCTION ALERTS WITH TRAFFIC GUARDS
# ============================================================================
Write-Host "`n[3/6] Production Alerts (4 expected with traffic guards)" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

try {
    $alertGroup = $rules.data.groups | Where-Object { $_.name -eq "aetherlink_rag.rules" } | Select-Object -First 1
    $prodAlerts = @("CacheEffectivenessDrop", "LowConfidenceSpike", "LowConfidenceSpikeVIP", "CacheEffectivenessDropVIP")
    $guardedCount = 0

    foreach ($name in $prodAlerts) {
        $alert = $alertGroup.rules | Where-Object { $_.name -eq $name -and $_.type -eq "alerting" }
        if ($alert -and $alert.query -match "and sum\(rate") {
            Write-Host "    ✓ $name (with traffic guard)" -ForegroundColor DarkGreen
            $guardedCount++
        }
        else {
            Write-Host "    ✗ $name (missing or no guard)" -ForegroundColor Red
        }
    }

    Test-Check "All 4 alerts have traffic guards" ($guardedCount -eq 4)
}
catch {
    Test-Check "Alerts accessible" $false -Critical
}

# ============================================================================
# CHECK 4: GRAFANA AUTO-PROVISIONING
# ============================================================================
Write-Host "`n[4/6] Grafana Auto-Provisioning" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

try {
    $grafanaHealth = Invoke-RestMethod "http://localhost:3000/api/health" -UseBasicParsing
    Test-Check "Grafana accessible" ($grafanaHealth.database -eq "ok")

    Start-Sleep -Seconds 2

    try {
        $dashboards = Invoke-RestMethod "http://admin:admin@localhost:3000/api/search?type=dash-db" -UseBasicParsing
        $enhancedDb = $dashboards | Where-Object { $_.title -match "Enhanced" }

        if ($enhancedDb) {
            Test-Check "Enhanced dashboard auto-provisioned" $true
            Write-Host "    📊 Dashboard: $($enhancedDb.title)" -ForegroundColor Gray
            Write-Host "    🔗 URL: http://localhost:3000$($enhancedDb.url)" -ForegroundColor Gray
        }
        else {
            Test-Check "Enhanced dashboard found" $false
            Write-Host "    ℹ️  May take 30-60s to provision. Check again shortly." -ForegroundColor Yellow
        }
    }
    catch {
        Test-Check "Dashboard query" $false
    }
}
catch {
    Test-Check "Grafana accessible" $false -Critical
}

# ============================================================================
# CHECK 5: API METRICS ENDPOINT
# ============================================================================
Write-Host "`n[5/6] API Metrics Endpoint" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

if (-not $SkipAPICheck) {
    try {
        $apiMetrics = Invoke-WebRequest "http://localhost:8000/metrics" -UseBasicParsing -TimeoutSec 3

        if ($apiMetrics.StatusCode -eq 200) {
            Test-Check "API /metrics reachable" $true

            # Check for key metrics
            $content = $apiMetrics.Content
            $hasAnswers = $content -match "aether_rag_answers_total"
            $hasCache = $content -match "aether_cache_requests_total"
            $hasRerank = $content -match "aether_rerank_requests_total"

            Test-Check "aether_rag_answers_total present" $hasAnswers
            Test-Check "aether_cache_requests_total present" $hasCache
            Test-Check "aether_rerank_requests_total present" $hasRerank

            if ($hasAnswers -and $hasCache -and $hasRerank) {
                Write-Host "    ✓ All key metrics present!" -ForegroundColor DarkGreen
            }
        }
        else {
            Test-Check "API /metrics returns 200" $false
        }
    }
    catch {
        Test-Check "API /metrics reachable" $false
        Write-Host "    ℹ️  API may not be running. Start it with: cd pods\customer-ops; docker compose up -d" -ForegroundColor Yellow
    }
}
else {
    Write-Host "  ⏭️  Skipped (use without -SkipAPICheck to test)" -ForegroundColor Gray
}

# ============================================================================
# CHECK 6: RECORDING RULES HAVE DATA
# ============================================================================
Write-Host "`n[6/6] Recording Rules Data (after traffic)" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor DarkGray

try {
    $query = "aether:cache_hit_ratio:5m"
    $result = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" -UseBasicParsing

    if ($result.data.result.Count -gt 0) {
        $hasData = $false
        foreach ($series in $result.data.result) {
            $value = $series.value[1]
            if ($value -ne "NaN" -and $value -ne $null) {
                $hasData = $true
                $tenant = $series.metric.tenant
                Write-Host "    ✓ Tenant '$tenant': $([math]::Round([double]$value, 1))%" -ForegroundColor DarkGreen
            }
        }

        Test-Check "Recording rules returning data" $hasData

        if (-not $hasData) {
            Write-Host "    ℹ️  Rules exist but returning NaN (no traffic yet)" -ForegroundColor Yellow
            Write-Host "    💡 Generate traffic: `$env:API_ADMIN_KEY='admin-secret-123'; .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
        }
    }
    else {
        Test-Check "Recording rules have data" $false
        Write-Host "    ℹ️  No data yet. Generate traffic to populate metrics." -ForegroundColor Yellow
    }
}
catch {
    Test-Check "Query recording rules" $false
}

# ============================================================================
# SUMMARY
# ============================================================================
Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor DarkGray
Write-Host "`n📋 POST-DEPLOY SUMMARY`n" -ForegroundColor Cyan

Write-Host "PASSED: $($checks.passed.Count)" -ForegroundColor Green
if ($checks.passed.Count -gt 0) {
    $checks.passed | ForEach-Object { Write-Host "  ✅ $_" -ForegroundColor Green }
}

if ($checks.warnings.Count -gt 0) {
    Write-Host "`nWARNINGS: $($checks.warnings.Count)" -ForegroundColor Yellow
    $checks.warnings | ForEach-Object { Write-Host "  ⚠️  $_" -ForegroundColor Yellow }
}

if ($checks.failed.Count -gt 0) {
    Write-Host "`nFAILED: $($checks.failed.Count)" -ForegroundColor Red
    $checks.failed | ForEach-Object { Write-Host "  ❌ $_" -ForegroundColor Red }
}

# ============================================================================
# NEXT STEPS
# ============================================================================
Write-Host "`n🎯 NEXT STEPS:" -ForegroundColor Cyan

if ($checks.failed.Count -eq 0) {
    if (-not $SkipAPICheck -and $checks.warnings -contains "API /metrics reachable") {
        Write-Host "`n1️⃣  Start the AetherLink API:" -ForegroundColor Yellow
        Write-Host "   cd ..\pods\customer-ops" -ForegroundColor Gray
        Write-Host "   docker compose up -d" -ForegroundColor Gray
        Write-Host "   # Wait 10s, then re-run this script" -ForegroundColor Gray
    }

    if ($checks.warnings -contains "Recording rules returning data") {
        Write-Host "`n2️⃣  Generate test traffic:" -ForegroundColor Yellow
        Write-Host "   `$env:API_ADMIN_KEY = 'admin-secret-123'" -ForegroundColor Gray
        Write-Host "   .\scripts\tenant-smoke-test.ps1" -ForegroundColor Gray
        Write-Host "   Start-Sleep -Seconds 15" -ForegroundColor Gray
    }

    Write-Host "`n3️⃣  Open monitoring interfaces:" -ForegroundColor Green
    Write-Host "   Prometheus Rules:  http://localhost:9090/rules" -ForegroundColor Gray
    Write-Host "   Prometheus Alerts: http://localhost:9090/alerts" -ForegroundColor Gray
    Write-Host "   Grafana Dashboard: http://localhost:3000 (admin/admin)" -ForegroundColor Gray
    Write-Host "   Alertmanager:      http://localhost:9093/#/status" -ForegroundColor Gray

    Write-Host "`n4️⃣  Optional: Enable Slack notifications:" -ForegroundColor Cyan
    Write-Host "   `$env:SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/XXX/YYY/ZZZ'" -ForegroundColor Gray
    Write-Host "   # Edit monitoring/alertmanager.yml: change 'default' to 'slack' receiver" -ForegroundColor Gray
    Write-Host "   docker compose restart alertmanager" -ForegroundColor Gray

    Write-Host "`n✨ Monitoring stack is healthy! Generate traffic to see gauges light up." -ForegroundColor Green
}
else {
    Write-Host "`n⛔ Critical issues detected. Fix the failed checks above." -ForegroundColor Red
}

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor DarkGray
Write-Host ""
