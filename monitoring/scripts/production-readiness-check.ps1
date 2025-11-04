# Production Readiness Validation Script
# Validates all production hardening features before deployment

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$passCount = 0
$failCount = 0

function Test-Component {
    param(
        [string]$Name,
        [scriptblock]$Test,
        [string]$SuccessMessage,
        [string]$FailureMessage
    )

    Write-Host "`n[TEST] $Name" -ForegroundColor Yellow
    try {
        $result = & $Test
        if ($result) {
            Write-Host "  ✅ PASS: $SuccessMessage" -ForegroundColor Green
            $script:passCount++
            return $true
        }
        else {
            Write-Host "  ❌ FAIL: $FailureMessage" -ForegroundColor Red
            $script:failCount++
            return $false
        }
    }
    catch {
        Write-Host "  ❌ ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $script:failCount++
        return $false
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Autoheal Production Readiness Check" -ForegroundColor Cyan
Write-Host "  Aetherlink Platform" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Service Health
Test-Component -Name "Autoheal Service Health" -Test {
    $health = Invoke-RestMethod 'http://localhost:9009/' -ErrorAction Stop
    $health.status -eq "ok"
} -SuccessMessage "Service responding" -FailureMessage "Service not responding"

# 2. Prometheus Integration
Test-Component -Name "Prometheus Scraping Autoheal" -Test {
    $targets = Invoke-RestMethod 'http://localhost:9090/api/v1/targets' -ErrorAction Stop
    $autohealTarget = $targets.data.activeTargets | Where-Object { $_.labels.job -eq "autoheal" }
    $autohealTarget.health -eq "up"
} -SuccessMessage "Autoheal target healthy" -FailureMessage "Autoheal target not found or unhealthy"

# 3. Prometheus Labels
Test-Component -Name "Prometheus Integration Labels" -Test {
    $query = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22autoheal%22%7D' -ErrorAction Stop
    $metric = $query.data.result[0].metric
    ($metric.project -eq "Aetherlink") -and ($metric.module -eq "Autoheal") -and ($metric.app -eq "peakpro-crm")
} -SuccessMessage "Labels: project=Aetherlink, module=Autoheal, app=peakpro-crm" -FailureMessage "Labels not configured correctly"

# 4. Audit Write Latency Metric (SLO-4)
Test-Component -Name "Audit Write Latency Metric (SLO-4)" -Test {
    $metrics = (Invoke-WebRequest 'http://localhost:9009/metrics' -UseBasicParsing).Content
    $metrics -match 'autoheal_audit_write_seconds'
} -SuccessMessage "SLO-4 metric exposed" -FailureMessage "SLO-4 metric not found"

# 5. Alert Rules Loaded
Test-Component -Name "Autoheal Alert Rules" -Test {
    $rules = Invoke-RestMethod 'http://localhost:9090/api/v1/rules' -ErrorAction Stop
    $autohealAlerts = $rules.data.groups | ForEach-Object { $_.rules } | Where-Object { $_.type -eq 'alerting' -and $_.name -like 'Autoheal*' }
    $autohealAlerts.Count -ge 8
} -SuccessMessage "$($autohealAlerts.Count) alert rules loaded" -FailureMessage "Expected >= 8 alert rules"

# 6. SLO Alerts Configured
Test-Component -Name "SLO Alert Coverage" -Test {
    $rules = Invoke-RestMethod 'http://localhost:9090/api/v1/rules' -ErrorAction Stop
    $sloAlerts = $rules.data.groups | ForEach-Object { $_.rules } | Where-Object {
        $_.type -eq 'alerting' -and $_.name -in @(
            'AutohealHeartbeatSLOBreach',
            'AutohealFailureRateSLOBreach',
            'AutohealServiceDown',
            'AutohealAuditWriteLatencySLOBreach'
        )
    }
    $sloAlerts.Count -eq 4
} -SuccessMessage "All 4 SLO alerts configured" -FailureMessage "Not all SLO alerts found"

# 7. Alertmanager Routing
Test-Component -Name "Alertmanager autoheal-notify Route" -Test {
    $config = Invoke-RestMethod 'http://localhost:9093/api/v2/status' -ErrorAction Stop
    $configYaml = $config.config.original
    $configYaml -match 'autoheal-notify'
} -SuccessMessage "autoheal-notify receiver configured" -FailureMessage "autoheal-notify receiver not found"

# 8. Audit Filtering
Test-Component -Name "Filterable Audit API" -Test {
    $audit = Invoke-RestMethod 'http://localhost:9009/audit?n=10&kind=webhook_received' -ErrorAction Stop
    $audit.PSObject.Properties.Name -contains "count" -and $audit.PSObject.Properties.Name -contains "events"
} -SuccessMessage "Audit API returns JSON with count and events" -FailureMessage "Audit API response format invalid"

# 9. SSE Console
Test-Component -Name "SSE Console Accessible" -Test {
    $console = Invoke-WebRequest 'http://localhost:9009/console' -UseBasicParsing -ErrorAction Stop
    $console.StatusCode -eq 200 -and $console.Content -match 'Autoheal Event Stream'
} -SuccessMessage "Console HTML served successfully" -FailureMessage "Console not accessible"

# 10. Production Compose Override
Test-Component -Name "Production Compose File" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\docker-compose.prod.yml'
} -SuccessMessage "docker-compose.prod.yml exists" -FailureMessage "docker-compose.prod.yml not found"

# 11. Logrotate Configuration
Test-Component -Name "Logrotate Configuration" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\logrotate\audit.conf'
} -SuccessMessage "audit.conf exists" -FailureMessage "audit.conf not found"

# 12. Backup Scripts
Test-Component -Name "Backup Scripts" -Test {
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\scripts\backup\backup-autoheal.ps1') -and
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\scripts\backup\prometheus-snapshot.sh')
} -SuccessMessage "Backup scripts present" -FailureMessage "Backup scripts missing"

# 13. CI/CD Pipeline
Test-Component -Name "GitHub Actions CI/CD" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\.github\workflows\autoheal-ci.yml'
} -SuccessMessage "CI/CD workflow configured" -FailureMessage "CI/CD workflow not found"

# 14. Security Middleware
Test-Component -Name "Security Middleware Module" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\autoheal\security.py'
} -SuccessMessage "security.py module exists" -FailureMessage "security.py not found"

# 15. Production Documentation
Test-Component -Name "Production Deployment Guide" -Test {
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\docs\PRODUCTION_DEPLOYMENT_GUIDE.md') -and
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\docs\PRODUCTION_READINESS_SUMMARY.md')
} -SuccessMessage "Deployment guides present" -FailureMessage "Deployment guides missing"

# 16. Audit Trail Persistence
Test-Component -Name "Audit Trail Directory" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\data\autoheal'
} -SuccessMessage "Audit directory exists" -FailureMessage "Audit directory not created"

# 17. Command Center Integration
Test-Component -Name "Ops Dashboard Module" -Test {
    Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\peakpro\app\ops\autoheal_dashboard.py'
} -SuccessMessage "Command Center dashboard ready" -FailureMessage "Dashboard module not found"

# 18. Helper Scripts
Test-Component -Name "Windows Helper Scripts" -Test {
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\scripts\autoheal-provision.ps1') -and
    (Test-Path 'C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\scripts\open-autoheal.ps1')
} -SuccessMessage "Helper scripts present" -FailureMessage "Helper scripts missing"

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Production Readiness Summary" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$total = $passCount + $failCount
$passRate = [math]::Round(($passCount / $total) * 100, 1)

Write-Host "Total Tests: $total" -ForegroundColor White
Write-Host "Passed: $passCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Red" })
Write-Host "Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -ge 95) { "Green" } elseif ($passRate -ge 80) { "Yellow" } else { "Red" })

Write-Host ""

if ($failCount -eq 0) {
    Write-Host "🎉 ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host "✅ Autoheal is READY FOR PRODUCTION" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. Deploy canary with DRY_RUN=true" -ForegroundColor Gray
    Write-Host "  2. Monitor for 24-48 hours" -ForegroundColor Gray
    Write-Host "  3. Flip DRY_RUN=false for production" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d" -ForegroundColor Gray
    exit 0
}
elseif ($passRate -ge 80) {
    Write-Host "⚠️  MOSTLY READY - Some non-critical checks failed" -ForegroundColor Yellow
    Write-Host "Review failed checks and determine if they are blockers" -ForegroundColor Yellow
    exit 1
}
else {
    Write-Host "❌ NOT READY FOR PRODUCTION" -ForegroundColor Red
    Write-Host "Fix critical failures before deploying" -ForegroundColor Red
    exit 1
}
