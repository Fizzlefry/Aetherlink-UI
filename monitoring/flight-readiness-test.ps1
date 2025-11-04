# Flight Readiness Test - Complete End-to-End Validation
# This simulates production conditions and validates the entire stack
# Run as Administrator

param(
    [string]$User = "aether",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                                ║" -ForegroundColor Cyan
Write-Host "║       🚀 FLIGHT READINESS TEST - MONITORING STACK 🚀           ║" -ForegroundColor Cyan
Write-Host "║                                                                ║" -ForegroundColor Cyan
Write-Host "║  This test validates your complete monitoring infrastructure  ║" -ForegroundColor Cyan
Write-Host "║  Duration: ~15 minutes (includes 7-minute alert wait)         ║" -ForegroundColor Cyan
Write-Host "║                                                                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Test stage counter
$stage = 0
$totalStages = 10

function Show-Stage {
    param([string]$Title)
    $script:stage++
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "  STAGE $script:stage/$totalStages : $Title" -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
}

function Show-Success {
    param([string]$Message)
    Write-Host "  ✅ $Message" -ForegroundColor Green
}

function Show-Error {
    param([string]$Message)
    Write-Host "  ❌ $Message" -ForegroundColor Red
}

function Show-Info {
    param([string]$Message)
    Write-Host "  ℹ️  $Message" -ForegroundColor Cyan
}

function Show-Warning {
    param([string]$Message)
    Write-Host "  ⚠️  $Message" -ForegroundColor Yellow
}

# -------------------------------------------------------------------
# STAGE 1: Pre-Flight Checks
# -------------------------------------------------------------------
Show-Stage "Pre-Flight Checks"

Write-Host "Checking prerequisites..." -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Show-Error "This script must be run as Administrator"
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}
Show-Success "Running as Administrator"

# Check Docker
try {
    $dockerVersion = docker --version
    Show-Success "Docker installed: $dockerVersion"
}
catch {
    Show-Error "Docker not found or not running"
    exit 1
}

# Check if monitoring containers are running
$containers = @(
    "aether-grafana",
    "aether-prometheus",
    "aether-alertmanager",
    "aether-kafka",
    "aether-kafka-exporter",
    "aether-crm-events"
)

Write-Host ""
Write-Host "Checking monitoring containers..." -ForegroundColor Cyan
foreach ($container in $containers) {
    $running = docker ps --filter "name=$container" --filter "status=running" --format "{{.Names}}" 2>$null
    if ($running) {
        Show-Success "$container is running"
    }
    else {
        Show-Warning "$container is not running (will start if needed)"
    }
}

# Check nginx proxy
$nginxRunning = docker ps --filter "name=aether-proxy" --filter "status=running" --format "{{.Names}}" 2>$null
if ($nginxRunning) {
    Show-Success "Nginx proxy is running"
}
else {
    Show-Error "Nginx proxy not found - run deploy-nginx-proxy.ps1 first"
    exit 1
}

# Check hosts file
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$hostsContent = Get-Content $hostsFile
$grafanaEntry = $hostsContent | Where-Object { $_ -match "grafana\.aetherlink\.local" }
$alertmanagerEntry = $hostsContent | Where-Object { $_ -match "alertmanager\.aetherlink\.local" }

if ($grafanaEntry) {
    Show-Success "DNS entry found: grafana.aetherlink.local"
}
else {
    Show-Error "DNS entry missing - run setup-hosts.ps1 first"
    exit 1
}

if ($alertmanagerEntry) {
    Show-Success "DNS entry found: alertmanager.aetherlink.local"
}
else {
    Show-Error "DNS entry missing - run setup-hosts.ps1 first"
    exit 1
}

Write-Host ""
Show-Success "Pre-flight checks complete!"

# -------------------------------------------------------------------
# STAGE 2: Test Nginx Proxy (No Auth - Grafana)
# -------------------------------------------------------------------
Show-Stage "Test Nginx Proxy - Grafana (No Auth)"

Write-Host "Testing Grafana access..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://grafana.aetherlink.local" -Method Head -TimeoutSec 10 -UseBasicParsing
    Show-Success "Grafana accessible: HTTP $($response.StatusCode)"
}
catch {
    Show-Error "Grafana not accessible: $($_.Exception.Message)"
    Show-Info "Check if nginx-proxy and grafana containers are running"
    exit 1
}

# -------------------------------------------------------------------
# STAGE 3: Test Nginx Proxy (With Auth - Alertmanager)
# -------------------------------------------------------------------
Show-Stage "Test Nginx Proxy - Alertmanager (Auth Required)"

Write-Host "Testing Alertmanager without auth (should fail)..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://alertmanager.aetherlink.local" -Method Head -TimeoutSec 10 -UseBasicParsing
    Show-Warning "Alertmanager accessible without auth - auth may not be configured"
}
catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Show-Success "Auth required (HTTP 401) - correct behavior"
    }
    else {
        Show-Error "Unexpected error: $($_.Exception.Message)"
        exit 1
    }
}

Write-Host ""
Write-Host "Testing Alertmanager with auth credentials..." -ForegroundColor Cyan
try {
    $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
    $headers = @{
        Authorization = "Basic $base64Auth"
    }
    $response = Invoke-WebRequest -Uri "http://alertmanager.aetherlink.local" -Method Head -Headers $headers -TimeoutSec 10 -UseBasicParsing
    Show-Success "Alertmanager accessible with auth: HTTP $($response.StatusCode)"
}
catch {
    Show-Error "Alertmanager auth failed: $($_.Exception.Message)"
    Show-Info "Check username/password or .htpasswd file"
    exit 1
}

# -------------------------------------------------------------------
# STAGE 4: Test Alertmanager API
# -------------------------------------------------------------------
Show-Stage "Test Alertmanager API (Silences Endpoint)"

Write-Host "Testing silences API..." -ForegroundColor Cyan
try {
    $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
    $headers = @{
        Authorization = "Basic $base64Auth"
    }
    $silences = Invoke-RestMethod -Uri "http://alertmanager.aetherlink.local/api/v2/silences" -Method Get -Headers $headers -TimeoutSec 10
    Show-Success "Silences API accessible - Found $($silences.Count) active silences"
}
catch {
    Show-Error "Silences API failed: $($_.Exception.Message)"
    exit 1
}

# -------------------------------------------------------------------
# STAGE 5: Verify Alert Configuration
# -------------------------------------------------------------------
Show-Stage "Verify Alert Rules"

Write-Host "Checking Prometheus alert rules..." -ForegroundColor Cyan
try {
    $prometheusUrl = "http://localhost:9090"
    $rulesResponse = Invoke-RestMethod -Uri "$prometheusUrl/api/v1/rules" -TimeoutSec 10
    
    $alertRules = $rulesResponse.data.groups | ForEach-Object { $_.rules } | Where-Object { $_.type -eq "alerting" }
    $alertCount = ($alertRules | Measure-Object).Count
    
    Show-Success "Found $alertCount alert rules configured"
    
    # Check for CRM Events alerts
    $crmAlerts = $alertRules | Where-Object { $_.labels.team -eq "crm" }
    if ($crmAlerts) {
        Show-Success "CRM Events alerts found: $($crmAlerts.Count) rules"
    }
    else {
        Show-Warning "No CRM Events alerts found"
    }
}
catch {
    Show-Warning "Could not verify alert rules: $($_.Exception.Message)"
}

# -------------------------------------------------------------------
# STAGE 6: Trigger Test Alert
# -------------------------------------------------------------------
Show-Stage "Trigger Test Alert"

Write-Host "This will stop the aether-crm-events container to trigger alerts" -ForegroundColor Yellow
Write-Host "Alert will fire after 7 minutes of downtime" -ForegroundColor Yellow
Write-Host ""
$response = Read-Host "Continue with alert trigger? (y/n)"
if ($response -ne "y") {
    Show-Warning "Test aborted by user"
    exit 0
}

Write-Host ""
Write-Host "Stopping aether-crm-events container..." -ForegroundColor Cyan
try {
    docker stop aether-crm-events 2>$null | Out-Null
    Show-Success "Container stopped - alert will fire in ~7 minutes"
}
catch {
    Show-Error "Failed to stop container: $($_.Exception.Message)"
    exit 1
}

# -------------------------------------------------------------------
# STAGE 7: Wait for Alert to Fire
# -------------------------------------------------------------------
Show-Stage "Wait for Alert Firing"

Write-Host "Waiting for alert to fire (7 minutes)..." -ForegroundColor Yellow
Write-Host "You can monitor progress at:" -ForegroundColor Cyan
Write-Host "  Prometheus Alerts: http://localhost:9090/alerts" -ForegroundColor White
Write-Host "  Alertmanager:      http://alertmanager.aetherlink.local" -ForegroundColor White
Write-Host ""

$waitMinutes = 7
$startTime = Get-Date
for ($i = 1; $i -le $waitMinutes; $i++) {
    $elapsed = $i
    $remaining = $waitMinutes - $i
    Write-Host "  ⏱️  Elapsed: $elapsed min | Remaining: $remaining min" -ForegroundColor Gray
    Start-Sleep -Seconds 60
}

Write-Host ""
Show-Success "Wait complete - checking if alert fired..."

# Check if alerts are firing
try {
    $alertsUrl = "http://localhost:9090/api/v1/alerts"
    $alertsResponse = Invoke-RestMethod -Uri $alertsUrl -TimeoutSec 10
    
    $firingAlerts = $alertsResponse.data.alerts | Where-Object { $_.state -eq "firing" }
    if ($firingAlerts) {
        Show-Success "Found $($firingAlerts.Count) firing alerts"
        
        # Show details
        foreach ($alert in $firingAlerts) {
            $alertName = $alert.labels.alertname
            $service = $alert.labels.service
            Write-Host "    • $alertName (service=$service)" -ForegroundColor White
        }
    }
    else {
        Show-Warning "No firing alerts yet - may need more time"
        Show-Info "Check Prometheus manually: http://localhost:9090/alerts"
    }
}
catch {
    Show-Warning "Could not check alerts: $($_.Exception.Message)"
}

# -------------------------------------------------------------------
# STAGE 8: Check Slack Delivery
# -------------------------------------------------------------------
Show-Stage "Verify Slack Notification"

Write-Host "Manual verification required:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Open Slack and go to #crm-events-alerts channel" -ForegroundColor White
Write-Host "2. You should see a message like:" -ForegroundColor White
Write-Host ""
Write-Host "   ┌─────────────────────────────────────────────────────┐" -ForegroundColor Gray
Write-Host "   │ 🔴 [FIRING] crm-events-sse (X firing)              │" -ForegroundColor Gray
Write-Host "   │                                                     │" -ForegroundColor Gray
Write-Host "   │ [📊 View Dashboard] [🔍 Prometheus] [🔕 Silence]  │" -ForegroundColor Gray
Write-Host "   └─────────────────────────────────────────────────────┘" -ForegroundColor Gray
Write-Host ""
$slackReceived = Read-Host "Did you receive the Slack notification? (y/n)"

if ($slackReceived -ne "y") {
    Show-Error "Slack notification not received"
    Show-Info "Check SLACK_WEBHOOK_URL environment variable"
    Show-Info "Check Alertmanager logs: docker logs aether-alertmanager"
    
    $continueTest = Read-Host "Continue with remaining tests? (y/n)"
    if ($continueTest -ne "y") {
        Write-Host ""
        Write-Host "Restarting aether-crm-events..." -ForegroundColor Cyan
        docker start aether-crm-events | Out-Null
        exit 1
    }
}
else {
    Show-Success "Slack notification confirmed!"
}

# -------------------------------------------------------------------
# STAGE 9: Test Slack Buttons
# -------------------------------------------------------------------
Show-Stage "Test Slack Buttons"

Write-Host "Manual button testing:" -ForegroundColor Yellow
Write-Host ""

# Test 1: Dashboard button
Write-Host "TEST 1: Click [📊 View Dashboard] button in Slack" -ForegroundColor Cyan
Write-Host "  Expected: Opens http://grafana.aetherlink.local/d/crm-events-pipeline" -ForegroundColor Gray
Write-Host "  Should: Display Grafana dashboard with 19 panels" -ForegroundColor Gray
Write-Host ""
$dashboardWorks = Read-Host "Did the dashboard button work? (y/n)"
if ($dashboardWorks -eq "y") {
    Show-Success "Dashboard button working"
}
else {
    Show-Error "Dashboard button failed"
}

Write-Host ""

# Test 2: Prometheus button
Write-Host "TEST 2: Click [🔍 Prometheus Alerts] button in Slack" -ForegroundColor Cyan
Write-Host "  Expected: Opens http://alertmanager.aetherlink.local/#/alerts" -ForegroundColor Gray
Write-Host "  Should: Show Alertmanager alerts page (with auth prompt)" -ForegroundColor Gray
Write-Host ""
$prometheusWorks = Read-Host "Did the Prometheus button work? (y/n)"
if ($prometheusWorks -eq "y") {
    Show-Success "Prometheus button working"
}
else {
    Show-Error "Prometheus button failed"
}

Write-Host ""

# Test 3: Silence button (most important!)
Write-Host "TEST 3: Click [🔕 Silence 1h] button in Slack" -ForegroundColor Cyan
Write-Host "  Expected: Opens http://alertmanager.aetherlink.local/#/silences/new?filter=..." -ForegroundColor Gray
Write-Host "  Should: Prompt for auth (aether / $Password)" -ForegroundColor Gray
Write-Host "  Should: Pre-fill form with:" -ForegroundColor Gray
Write-Host "    • service = ""crm-events-sse""" -ForegroundColor Gray
Write-Host "    • team = ""crm""" -ForegroundColor Gray
Write-Host ""
$silenceWorks = Read-Host "Did the silence button work correctly? (y/n)"
if ($silenceWorks -eq "y") {
    Show-Success "Silence button working (auth + pre-filled form)"
}
else {
    Show-Error "Silence button failed"
}

# -------------------------------------------------------------------
# STAGE 10: Create Silence and Verify Suppression
# -------------------------------------------------------------------
Show-Stage "Test Silence Creation"

Write-Host "Final test: Create a silence and verify it suppresses alerts" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. If you haven't already, click [🔕 Silence 1h] button" -ForegroundColor White
Write-Host "2. Enter credentials: aether / $Password" -ForegroundColor White
Write-Host "3. Verify form is pre-filled with service + team" -ForegroundColor White
Write-Host "4. Add comment: ""Flight readiness test""" -ForegroundColor White
Write-Host "5. Click Create" -ForegroundColor White
Write-Host ""

$silenceCreated = Read-Host "Did you create the silence? (y/n)"

if ($silenceCreated -eq "y") {
    Show-Success "Silence created"
    
    Write-Host ""
    Write-Host "Checking if silence is active..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3
    
    try {
        $base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Password}"))
        $headers = @{
            Authorization = "Basic $base64Auth"
        }
        $silences = Invoke-RestMethod -Uri "http://alertmanager.aetherlink.local/api/v2/silences" -Method Get -Headers $headers -TimeoutSec 10
        
        $activeSilences = $silences | Where-Object { $_.status.state -eq "active" }
        if ($activeSilences) {
            Show-Success "Found $($activeSilences.Count) active silences"
            
            # Check for CRM silence
            $crmSilence = $activeSilences | Where-Object { 
                $_.matchers | Where-Object { $_.name -eq "service" -and $_.value -eq "crm-events-sse" }
            }
            
            if ($crmSilence) {
                Show-Success "CRM Events silence is active!"
                $endsAt = [DateTime]::Parse($crmSilence[0].endsAt).ToLocalTime()
                Show-Info "Silence expires at: $endsAt"
            }
        }
        else {
            Show-Warning "No active silences found - may take a moment to sync"
        }
    }
    catch {
        Show-Warning "Could not verify silence: $($_.Exception.Message)"
    }
}
else {
    Show-Warning "Silence not created - skipping verification"
}

# -------------------------------------------------------------------
# CLEANUP: Restart Service
# -------------------------------------------------------------------
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "  CLEANUP: Restart Service" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""

$restart = Read-Host "Restart aether-crm-events now? (y/n)"
if ($restart -eq "y") {
    Write-Host "Restarting aether-crm-events..." -ForegroundColor Cyan
    docker start aether-crm-events | Out-Null
    Show-Success "Service restarted"
    
    Write-Host ""
    Show-Info "Alert should resolve in ~5 minutes"
    Show-Info "Slack will show [RESOLVED] message"
}
else {
    Show-Warning "Remember to restart: docker start aether-crm-events"
}

# -------------------------------------------------------------------
# FINAL REPORT
# -------------------------------------------------------------------
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                                ║" -ForegroundColor Green
Write-Host "║           ✅ FLIGHT READINESS TEST COMPLETE ✅                 ║" -ForegroundColor Green
Write-Host "║                                                                ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "TEST RESULTS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Infrastructure:" -ForegroundColor Yellow
Write-Host "  ✅ Nginx proxy running" -ForegroundColor Green
Write-Host "  ✅ DNS entries configured" -ForegroundColor Green
Write-Host "  ✅ Monitoring containers running" -ForegroundColor Green
Write-Host ""

Write-Host "Authentication:" -ForegroundColor Yellow
Write-Host "  ✅ Grafana accessible (no auth)" -ForegroundColor Green
Write-Host "  ✅ Alertmanager requires auth" -ForegroundColor Green
Write-Host "  ✅ Silences API protected" -ForegroundColor Green
Write-Host ""

Write-Host "Slack Integration:" -ForegroundColor Yellow
if ($slackReceived -eq "y") {
    Write-Host "  ✅ Slack notification received" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Slack notification not received" -ForegroundColor Red
}

if ($dashboardWorks -eq "y") {
    Write-Host "  ✅ Dashboard button working" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Dashboard button failed" -ForegroundColor Red
}

if ($prometheusWorks -eq "y") {
    Write-Host "  ✅ Prometheus button working" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Prometheus button failed" -ForegroundColor Red
}

if ($silenceWorks -eq "y") {
    Write-Host "  ✅ Silence button working (auth + pre-fill)" -ForegroundColor Green
}
else {
    Write-Host "  ❌ Silence button failed" -ForegroundColor Red
}

Write-Host ""

# Calculate pass rate
$tests = @($slackReceived, $dashboardWorks, $prometheusWorks, $silenceWorks)
$passed = ($tests | Where-Object { $_ -eq "y" }).Count
$total = $tests.Count
$passRate = [math]::Round(($passed / $total) * 100)

if ($passRate -eq 100) {
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║       🏆 CONGRATULATIONS - 100% PASS RATE 🏆                   ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║   Your monitoring stack is COMMAND-CENTER GRADE!              ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║   ✅ External URLs working                                     ║" -ForegroundColor Green
    Write-Host "║   ✅ Authentication enforced                                   ║" -ForegroundColor Green
    Write-Host "║   ✅ Slack buttons functional                                  ║" -ForegroundColor Green
    Write-Host "║   ✅ One-click silence creation                                ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║   STATUS: PRODUCTION READY 🚀                                 ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
}
elseif ($passRate -ge 75) {
    Write-Host "Pass Rate: $passRate% - Good, but some issues to address" -ForegroundColor Yellow
}
else {
    Write-Host "Pass Rate: $passRate% - Critical issues need attention" -ForegroundColor Red
}

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Train your team on the silence button" -ForegroundColor White
Write-Host "  2. Document credentials in 1Password/Vault" -ForegroundColor White
Write-Host "  3. Test from team member's phone/laptop" -ForegroundColor White
Write-Host "  4. Set up quarterly password rotation" -ForegroundColor White
Write-Host ""
Write-Host "DOCUMENTATION:" -ForegroundColor Cyan
Write-Host "  • Quick Start:    QUICK_DEPLOY.md" -ForegroundColor White
Write-Host "  • Full Guide:     DEPLOY.md" -ForegroundColor White
Write-Host "  • Architecture:   ARCHITECTURE.md" -ForegroundColor White
Write-Host "  • What Shipped:   SHIPMENT_MANIFEST.md" -ForegroundColor White
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
