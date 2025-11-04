# PeakPro CRM - Monitoring Smoke Test
# Verifies Prometheus rule groups & alert count
# Validates Grafana datasource connection
# Fires a synthetic Slack alert (if webhook set)
# Writes summary + PASS/FAIL exit code

param(
    [switch]$FireSlack
)

$ErrorActionPreference = 'Stop'
Write-Host "=== Monitoring Smoke Test ===" -ForegroundColor Cyan
Write-Host ""

$exitCode = 0

# ---- 1 Prometheus Rule Check ----
Write-Host "1. Checking Prometheus..." -ForegroundColor Yellow
$prom = "http://localhost:9090"
try {
    $rules = (Invoke-RestMethod "$prom/api/v1/rules").data.groups
    $crmRules = $rules | Where-Object { $_.name -match "crm" }
    $alerts = (Invoke-RestMethod "$prom/api/v1/alerts").data.alerts
  
    Write-Host ("   [OK] Rule Groups: {0} total | CRM Groups: {1}" -f $rules.Count, $crmRules.Count) -ForegroundColor Green
    Write-Host ("   [OK] Active Alerts: {0}" -f $alerts.Count) -ForegroundColor Green
  
    # Validate expected CRM rule groups
    $expectedGroups = @("crm_finance.rules", "crm_finance.recording")
    foreach ($group in $expectedGroups) {
        $found = $rules | Where-Object { $_.name -eq $group }
        if ($found) {
            Write-Host ("   [OK] Found '{0}' with {1} rules" -f $group, $found.rules.Count) -ForegroundColor Green
        }
        else {
            Write-Warning ("   [WARN] Missing rule group: {0}" -f $group)
            $exitCode = 1
        }
    }
  
    # Validate recording rules are producing data
    Write-Host ""
    Write-Host "   Testing recording rules..." -ForegroundColor Cyan
    $recordingMetrics = @(
        "crm:invoices_created_24h",
        "crm:invoices_paid_24h", 
        "crm:revenue_usd",
        "crm:payment_rate_30d_pct"
    )
  
    foreach ($metric in $recordingMetrics) {
        $result = (Invoke-RestMethod "$prom/api/v1/query?query=$metric").data.result
        if ($result.Count -gt 0) {
            Write-Host ("   [OK] {0}: {1} series" -f $metric, $result.Count) -ForegroundColor Green
        }
        else {
            Write-Host ("   [WAIT] {0}: Evaluating (no data yet)" -f $metric) -ForegroundColor Yellow
        }
    }
  
}
catch { 
    Write-Warning "   [FAIL] Prometheus unreachable: $_"
    $exitCode = 1
}

Write-Host ""

# ---- 2 Grafana Datasource ----
Write-Host "2. Checking Grafana..." -ForegroundColor Yellow
$graf = "http://localhost:3000/api/health"
try {
    $g = Invoke-RestMethod $graf
    if ($g.database -eq "ok") { 
        Write-Host "   [OK] Grafana connected (database: ok)" -ForegroundColor Green
    
        # Check datasource
        try {
            $ds = Invoke-RestMethod "http://localhost:3000/api/datasources/name/prometheus" -Headers @{"Accept" = "application/json" }
            Write-Host ("   [OK] Prometheus datasource configured (uid: {0})" -f $ds.uid) -ForegroundColor Green
        }
        catch {
            Write-Warning "   [WARN] Could not verify Prometheus datasource"
        }
    }
    else { 
        Write-Warning "   [FAIL] Grafana database not OK"
        $exitCode = 1
    }
}
catch { 
    Write-Warning "   [FAIL] Grafana unreachable: $_"
    $exitCode = 1
}

Write-Host ""

# ---- 3 Alertmanager Check ----
Write-Host "3. Checking Alertmanager..." -ForegroundColor Yellow
try {
    $am = Invoke-RestMethod "http://localhost:9093/api/v2/status"
    Write-Host "   [OK] Alertmanager responsive" -ForegroundColor Green
    Write-Host ("   [OK] Version: {0}" -f $am.versionInfo.version) -ForegroundColor Green
  
    # Check config
    $config = Invoke-RestMethod "http://localhost:9093/api/v1/status"
    $receivers = $config.data.config.receivers
    Write-Host ("   [OK] Configured receivers: {0}" -f $receivers.Count) -ForegroundColor Green
  
    $slackReceivers = $receivers | Where-Object { $_.slack_configs.Count -gt 0 }
    if ($slackReceivers.Count -gt 0) {
        Write-Host ("   [OK] Slack receivers configured: {0}" -f $slackReceivers.Count) -ForegroundColor Green
    }
    else {
        Write-Host "   [WAIT] No Slack receivers configured yet" -ForegroundColor Yellow
    }
  
}
catch {
    Write-Warning "   [FAIL] Alertmanager unreachable: $_"
    $exitCode = 1
}

Write-Host ""

# ---- 4 CRM API Metrics ----
Write-Host "4. Checking CRM API metrics..." -ForegroundColor Yellow
try {
    $crmMetrics = Invoke-RestMethod "http://localhost:8089/metrics" -ErrorAction Stop
    if ($crmMetrics -match "crm_invoices_generated_total") {
        Write-Host "   [OK] CRM metrics exposed" -ForegroundColor Green
    
        # Count CRM-specific metrics
        $crmMetricCount = ($crmMetrics -split "`n" | Where-Object { $_ -match "^crm_" -and $_ -notmatch "^#" }).Count
        Write-Host ("   [OK] CRM metric series: {0}" -f $crmMetricCount) -ForegroundColor Green
    }
    else {
        Write-Warning "   [WARN] CRM metrics not found"
        $exitCode = 1
    }
  
    # Check Prometheus is scraping CRM API
    $scrapeHealth = (Invoke-RestMethod "$prom/api/v1/query?query=up{job=~`"crm.*`"}").data.result
    if ($scrapeHealth.Count -gt 0) {
        $status = $scrapeHealth[0].value[1]
        if ($status -eq "1") {
            Write-Host ("   [OK] Prometheus scraping CRM API (job: {0})" -f $scrapeHealth[0].metric.job) -ForegroundColor Green
        }
        else {
            Write-Warning ("   [FAIL] Prometheus scrape failing (job: {0})" -f $scrapeHealth[0].metric.job)
            $exitCode = 1
        }
    }
    else {
        Write-Warning "   [WARN] No CRM scrape target found in Prometheus"
        $exitCode = 1
    }
  
}
catch {
    Write-Warning "   [FAIL] CRM API unreachable: $_"
    $exitCode = 1
}

Write-Host ""

# ---- 5 Synthetic Slack Alert (optional) ----
if ($FireSlack) {
    Write-Host "5. Sending synthetic Slack alert..." -ForegroundColor Yellow
    if (-not $env:SLACK_WEBHOOK_URL) { 
        Write-Warning "   [WARN] SLACK_WEBHOOK_URL not set - skipping Slack test"
    }
    else {
        Write-Host "   Triggering synthetic alert via Alertmanager..." -ForegroundColor Cyan
        $body = @'
[{
 "labels":{"alertname":"SyntheticTest","service":"crm","severity":"info"},
 "annotations":{"summary":"Synthetic validation alert","description":"Triggered manually to verify Slack routing. If you see this, the monitoring to Slack pipeline is working!"}
}]
'@
        try {
            Invoke-RestMethod -Uri "http://localhost:9093/api/v1/alerts" -Method POST -Body $body -ContentType "application/json"
            Write-Host "   [OK] Slack test alert sent to Alertmanager" -ForegroundColor Green
            Write-Host "   -> Check #crm-alerts or #ops-alerts Slack channel" -ForegroundColor Cyan
        }
        catch {
            Write-Warning "   [FAIL] Failed to send test alert: $_"
            $exitCode = 1
        }
    }
    Write-Host ""
}

# ---- 6 Final Evaluation ----
Write-Host "============================================================" -ForegroundColor Cyan

if ($exitCode -eq 0) {
    Write-Host "[PASS] Monitoring stack validated - all core components responsive." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  - View dashboard: http://localhost:3000/d/peakpro_crm_kpis" -ForegroundColor Cyan
    Write-Host "  - Check alerts: http://localhost:9090/alerts" -ForegroundColor Cyan
    Write-Host "  - View metrics: make check-metrics" -ForegroundColor Cyan
    exit 0
}
else {
    Write-Host "[FAIL] Some monitoring components are not healthy." -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  - Check logs: make logs-prom, make logs-alert, make logs-crm" -ForegroundColor Cyan
    Write-Host "  - Restart services: make reload-prom or make restart-all" -ForegroundColor Cyan
    Write-Host "  - Review runbook: docs/runbooks/ALERTS_CRM_FINANCE.md" -ForegroundColor Cyan
    exit 1
}
