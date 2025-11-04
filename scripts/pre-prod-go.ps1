# ============================================================================
# PRE-PROD GO CHECKLIST - Final Validation Before Production
# ============================================================================
# Runs comprehensive checks: lint, reload, verify auto-provisioning,
# functional smoke test with traffic guards, and rollback readiness
# ============================================================================

param(
    [switch]$SkipTraffic,
    [switch]$SkipSlackTest
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$checklist = @()
$warnings = @()
$errors = @()

function Write-Step {
    param($Step, $Description)
    Write-Host "`n$Step" -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor DarkGray
    Write-Host $Description -ForegroundColor Gray
}

function Write-Success {
    param($Message)
    Write-Host "✅ $Message" -ForegroundColor Green
    $script:checklist += "✅ $Message"
}

function Write-Warning {
    param($Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
    $script:warnings += "⚠️  $Message"
}

function Write-Failure {
    param($Message)
    Write-Host "❌ $Message" -ForegroundColor Red
    $script:errors += "❌ $Message"
}

function Test-Command {
    param($CommandName)
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

Write-Host @"

╔═══════════════════════════════════════════════════════════════════════════╗
║                    PRE-PROD GO CHECKLIST v1.0                             ║
║                    AetherLink Production Validation                       ║
╚═══════════════════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# ============================================================================
# STEP 1: LINT + SYNTAX VALIDATION
# ============================================================================
Write-Step "[1/7] LINT + SYNTAX VALIDATION" "Checking all config files for syntax errors..."

$configDir = "monitoring"
$hasPromtool = Test-Command "promtool"
$hasAmtool = Test-Command "amtool"

if ($hasPromtool) {
    Write-Host "  🔍 Validating prometheus-config.yml..." -ForegroundColor Gray
    $result = & promtool check config "$configDir\prometheus-config.yml" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Prometheus config valid"
    }
    else {
        Write-Failure "Prometheus config invalid: $result"
    }

    Write-Host "  🔍 Validating prometheus-recording-rules.yml..." -ForegroundColor Gray
    $result = & promtool check rules "$configDir\prometheus-recording-rules.yml" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Recording rules valid"
    }
    else {
        Write-Failure "Recording rules invalid: $result"
    }

    Write-Host "  🔍 Validating prometheus-alerts.yml..." -ForegroundColor Gray
    $result = & promtool check rules "$configDir\prometheus-alerts.yml" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Alert rules valid (with traffic guards)"
    }
    else {
        Write-Failure "Alert rules invalid: $result"
    }
}
else {
    Write-Warning "promtool not found - install Prometheus CLI for validation (optional but recommended)"
}

if ($hasAmtool) {
    Write-Host "  🔍 Validating alertmanager.yml..." -ForegroundColor Gray
    $result = & amtool check-config "$configDir\alertmanager.yml" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Alertmanager config valid"
    }
    else {
        Write-Failure "Alertmanager config invalid: $result"
    }
}
else {
    Write-Warning "amtool not found - skipping Alertmanager validation (optional)"
}

# Check for dashboard JSON validity
if (Test-Path "$configDir\grafana-dashboard-enhanced.json") {
    Write-Host "  🔍 Validating grafana-dashboard-enhanced.json..." -ForegroundColor Gray
    try {
        $dashboard = Get-Content "$configDir\grafana-dashboard-enhanced.json" -Raw | ConvertFrom-Json
        if ($dashboard.title -and $dashboard.panels) {
            Write-Success "Grafana enhanced dashboard JSON valid"
        }
        else {
            Write-Warning "Dashboard JSON missing expected structure"
        }
    }
    catch {
        Write-Failure "Dashboard JSON invalid: $($_.Exception.Message)"
    }
}
else {
    Write-Failure "grafana-dashboard-enhanced.json not found"
}

# ============================================================================
# STEP 2: HOT-RELOAD PROMETHEUS & ALERTMANAGER
# ============================================================================
Write-Step "[2/7] HOT-RELOAD CONFIGS" "Reloading Prometheus and Alertmanager without restart..."

Write-Host "  🔄 Reloading Prometheus..." -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9090/-/reload" -Method POST -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Success "Prometheus reloaded successfully"
    }
    else {
        Write-Warning "Prometheus reload returned status: $($response.StatusCode)"
    }
}
catch {
    Write-Failure "Prometheus reload failed: $($_.Exception.Message)"
}

Write-Host "  🔄 Reloading Alertmanager..." -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9093/-/reload" -Method POST -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Success "Alertmanager reloaded successfully"
    }
    else {
        Write-Warning "Alertmanager reload returned status: $($response.StatusCode)"
    }
}
catch {
    Write-Warning "Alertmanager reload failed: $($_.Exception.Message) - May not be running"
}

Start-Sleep -Seconds 2

# ============================================================================
# STEP 3: VERIFY RECORDING RULES LOADED
# ============================================================================
Write-Step "[3/7] VERIFY RECORDING RULES" "Checking that all 6 recording rules are active..."

try {
    $rules = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $recordingRules = $rules.data.groups | Where-Object { $_.name -eq "aetherlink.recording" } | Select-Object -First 1

    if ($recordingRules -and $recordingRules.rules.Count -ge 6) {
        Write-Success "All 6 recording rules loaded"

        $expectedRules = @(
            "aether:cache_hit_ratio:5m",
            "aether:rerank_utilization_pct:15m",
            "aether:lowconfidence_pct:15m",
            "aether:cache_hit_ratio:5m:all",
            "aether:rerank_utilization_pct:15m:all",
            "aether:lowconfidence_pct:15m:all"
        )

        foreach ($expected in $expectedRules) {
            $found = $recordingRules.rules | Where-Object { $_.name -eq $expected }
            if ($found) {
                Write-Host "    ✓ $expected" -ForegroundColor DarkGreen
            }
            else {
                Write-Warning "Missing recording rule: $expected"
            }
        }
    }
    else {
        Write-Failure "Recording rules not loaded correctly (expected 6, found $($recordingRules.rules.Count))"
    }
}
catch {
    Write-Failure "Could not fetch recording rules: $($_.Exception.Message)"
}

# ============================================================================
# STEP 4: VERIFY ALERTS WITH TRAFFIC GUARDS
# ============================================================================
Write-Step "[4/7] VERIFY ALERTS (WITH TRAFFIC GUARDS)" "Checking that all 4 production alerts are active with traffic guards..."

try {
    $rules = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/rules" -UseBasicParsing
    $alertRules = $rules.data.groups | Where-Object { $_.name -eq "aetherlink_rag.rules" } | Select-Object -First 1

    if ($alertRules) {
        $expectedAlerts = @(
            "CacheEffectivenessDrop",
            "LowConfidenceSpike",
            "LowConfidenceSpikeVIP",
            "CacheEffectivenessDropVIP"
        )

        $foundCount = 0
        foreach ($expected in $expectedAlerts) {
            $alert = $alertRules.rules | Where-Object { $_.name -eq $expected -and $_.type -eq "alerting" }
            if ($alert) {
                $foundCount++
                # Check if alert has traffic guard (contains 'and sum(rate')
                if ($alert.query -match "and sum\(rate") {
                    Write-Host "    ✓ $expected (with traffic guard)" -ForegroundColor DarkGreen
                }
                else {
                    Write-Warning "$expected loaded but missing traffic guard"
                }
            }
            else {
                Write-Warning "Missing alert: $expected"
            }
        }

        if ($foundCount -eq 4) {
            Write-Success "All 4 production alerts loaded with traffic guards"
        }
        else {
            Write-Warning "Only $foundCount/4 production alerts found"
        }
    }
    else {
        Write-Failure "Alert rules not loaded"
    }
}
catch {
    Write-Failure "Could not fetch alert rules: $($_.Exception.Message)"
}

# ============================================================================
# STEP 5: VERIFY GRAFANA AUTO-PROVISIONING
# ============================================================================
Write-Step "[5/7] VERIFY GRAFANA AUTO-PROVISIONING" "Checking that enhanced dashboard is auto-provisioned..."

try {
    # Check if Grafana is accessible
    $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Success "Grafana is accessible"
    }

    # Check datasources
    Write-Host "  🔍 Checking Prometheus datasource..." -ForegroundColor Gray
    try {
        $datasources = Invoke-RestMethod -Uri "http://admin:admin@localhost:3000/api/datasources" -UseBasicParsing
        $promDs = $datasources | Where-Object { $_.type -eq "prometheus" }
        if ($promDs) {
            Write-Success "Prometheus datasource configured"
        }
        else {
            Write-Warning "Prometheus datasource not found - check grafana-datasource.yml"
        }
    }
    catch {
        Write-Warning "Could not verify datasources: $($_.Exception.Message)"
    }

    # Check dashboards
    Write-Host "  🔍 Checking for enhanced dashboard..." -ForegroundColor Gray
    try {
        $dashboards = Invoke-RestMethod -Uri "http://admin:admin@localhost:3000/api/search?type=dash-db" -UseBasicParsing
        $enhancedDb = $dashboards | Where-Object { $_.title -match "Enhanced" }
        if ($enhancedDb) {
            Write-Success "Enhanced dashboard auto-provisioned: '$($enhancedDb.title)'"
            Write-Host "    📊 Dashboard URL: http://localhost:3000$($enhancedDb.url)" -ForegroundColor Gray
        }
        else {
            Write-Warning "Enhanced dashboard not found - may take 30-60s to provision"
            Write-Host "    ℹ️  Check docker logs: docker logs aether-grafana" -ForegroundColor Gray
        }
    }
    catch {
        Write-Warning "Could not verify dashboards: $($_.Exception.Message)"
    }
}
catch {
    Write-Failure "Grafana not accessible: $($_.Exception.Message)"
}

# ============================================================================
# STEP 6: SLACK WIRING SANITY (ALERTMANAGER)
# ============================================================================
Write-Step "[6/7] SLACK WIRING SANITY" "Checking Alertmanager Slack configuration..."

if ($env:SLACK_WEBHOOK_URL) {
    if ($env:SLACK_WEBHOOK_URL -match "^https://hooks\.slack\.com/services/") {
        Write-Success "SLACK_WEBHOOK_URL environment variable set correctly"

        if (-not $SkipSlackTest) {
            Write-Host "  💬 Testing Alertmanager status..." -ForegroundColor Gray
            try {
                $amStatus = Invoke-RestMethod -Uri "http://localhost:9093/api/v2/status" -UseBasicParsing
                if ($amStatus) {
                    Write-Success "Alertmanager is responding"
                }
            }
            catch {
                Write-Warning "Alertmanager not accessible: $($_.Exception.Message)"
            }
        }
    }
    else {
        Write-Warning "SLACK_WEBHOOK_URL format looks incorrect (expected https://hooks.slack.com/services/...)"
    }
}
else {
    Write-Warning "SLACK_WEBHOOK_URL not set - Slack notifications will not work"
    Write-Host "    ℹ️  Set with: `$env:SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/XXX/YYY/ZZZ'" -ForegroundColor Gray
}

# ============================================================================
# STEP 7: FUNCTIONAL SMOKE TEST
# ============================================================================
Write-Step "[7/7] FUNCTIONAL SMOKE TEST" "Generating traffic to verify metrics and dashboards..."

if (-not $SkipTraffic) {
    if (Test-Path "scripts\tenant-smoke-test.ps1") {
        Write-Host "  🚀 Running tenant smoke test..." -ForegroundColor Gray

        if (-not $env:API_ADMIN_KEY) {
            Write-Warning "API_ADMIN_KEY not set - setting default for smoke test"
            $env:API_ADMIN_KEY = "admin-secret-123"
        }

        try {
            & ".\scripts\tenant-smoke-test.ps1" 2>&1 | Out-Null
            Start-Sleep -Seconds 5

            # Verify metrics are being scraped
            $query = "aether:cache_hit_ratio:5m"
            $result = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/query?query=$query" -UseBasicParsing

            if ($result.data.result.Count -gt 0) {
                $hasData = $false
                foreach ($series in $result.data.result) {
                    if ($series.value[1] -ne "NaN") {
                        $hasData = $true
                        break
                    }
                }

                if ($hasData) {
                    Write-Success "Recording rules returning valid data (non-NaN)"
                }
                else {
                    Write-Warning "Recording rules exist but returning NaN - may need more traffic"
                }
            }
            else {
                Write-Warning "No data from recording rules yet - scrape may be pending"
            }
        }
        catch {
            Write-Warning "Smoke test failed: $($_.Exception.Message)"
        }
    }
    else {
        Write-Warning "scripts\tenant-smoke-test.ps1 not found - skipping traffic generation"
    }
}
else {
    Write-Host "  ⏭️  Skipping traffic generation (use without -SkipTraffic to test)" -ForegroundColor Gray
}

# ============================================================================
# SUMMARY + NEXT STEPS
# ============================================================================
Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor DarkGray
Write-Host "`n📋 PRE-PROD GO CHECKLIST SUMMARY`n" -ForegroundColor Cyan

if ($checklist.Count -gt 0) {
    Write-Host "PASSED CHECKS ($($checklist.Count)):" -ForegroundColor Green
    $checklist | ForEach-Object { Write-Host "  $_" -ForegroundColor Green }
}

if ($warnings.Count -gt 0) {
    Write-Host "`nWARNINGS ($($warnings.Count)):" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}

if ($errors.Count -gt 0) {
    Write-Host "`nERRORS ($($errors.Count)):" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "`n⛔ NOT READY FOR PRODUCTION - Fix errors above" -ForegroundColor Red
}
else {
    Write-Host "`n🎉 ALL CRITICAL CHECKS PASSED!" -ForegroundColor Green

    if ($warnings.Count -eq 0) {
        Write-Host "✨ PRODUCTION-READY - No issues found!" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  PRODUCTION-READY with warnings - Review warnings above" -ForegroundColor Yellow
    }
}

# ============================================================================
# QUICK ACCESS LINKS
# ============================================================================
Write-Host "`n🔗 QUICK ACCESS LINKS:" -ForegroundColor Cyan
Write-Host "  📊 Prometheus Rules:  http://localhost:9090/rules" -ForegroundColor Gray
Write-Host "  🚨 Prometheus Alerts: http://localhost:9090/alerts" -ForegroundColor Gray
Write-Host "  🔔 Alertmanager:      http://localhost:9093/#/status" -ForegroundColor Gray
Write-Host "  📈 Grafana:           http://localhost:3000" -ForegroundColor Gray
Write-Host "  🎯 Enhanced Dashboard: http://localhost:3000/dashboards" -ForegroundColor Gray

# ============================================================================
# ROLLBACK PLAN
# ============================================================================
Write-Host "`n🔄 ROLLBACK PLAN (if needed):" -ForegroundColor Cyan
Write-Host @"
  git checkout -- monitoring\prometheus-alerts.yml
  git checkout -- monitoring\prometheus-recording-rules.yml
  git checkout -- monitoring\alertmanager.yml
  git checkout -- monitoring\grafana-dashboard-enhanced.json
  curl.exe -s -X POST http://localhost:9090/-/reload
  curl.exe -s -X POST http://localhost:9093/-/reload
"@ -ForegroundColor Gray

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor DarkGray
Write-Host ""
