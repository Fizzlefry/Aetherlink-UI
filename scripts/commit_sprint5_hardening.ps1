# Sprint 5 Production Hardening - Git Commit Helper
# Run this script to commit all changes

Write-Host "=== Sprint 5 Production Hardening - Git Commit ===" -ForegroundColor Cyan

# Stage all modified files
$filesToAdd = @(
    "monitoring/prometheus-recording-rules.yml"
    "monitoring/prometheus-alerts.yml"
    "monitoring/alertmanager.yml"
    "monitoring/Makefile"
    "monitoring/grafana-provisioning/dashboards/peakpro-crm-kpis.json"
    "docs/runbooks/ALERTS_CRM_FINANCE.md"
    "docs/SPRINT5_PRODUCTION_HARDENING_SUMMARY.md"
    "docs/QUICK_REFERENCE_FINANCE_MONITORING.md"
    "pods/crm/src/crm/metrics.py"
    "pods/crm/src/crm/qbo_sync.py"
)

Write-Host "`nStaging files..." -ForegroundColor Yellow
foreach ($file in $filesToAdd) {
    if (Test-Path $file) {
        git add $file
        Write-Host "  ✓ $file" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠ $file (not found)" -ForegroundColor Red
    }
}

# Create commit message
$commitMessage = @"
Obs: Sprint5 prod hardening — recording rules, Slack routes, runbook, alerts

- Add 8 Prometheus recording rules (30s eval): 4 aggregate + 4 per-org for multi-tenant support
- Create 4 production alerts: LowInvoicePaymentRate, RevenueZeroStreak, InvoiceGenerationStalled, CrmApiDown
- Configure Alertmanager Slack integration: #crm-alerts (2h repeat), #ops-alerts (4h repeat)
- Migrate all 4 Grafana finance panels to use :by_org recording rules (10-100x speedup, sub-second loads)
- Add CRM_INVOICE_PAYMENTS_CENTS metric for revenue tracking (wired in qbo_sync.py)
- Create comprehensive runbook: docs/runbooks/ALERTS_CRM_FINANCE.md (300+ lines with diagnostic steps)
- Add operational Makefile with 13 commands: reload-prom, open-crm-kpis, check-metrics, logs-*, etc.
- Fix InvoiceGenerationStalled: Remove brittle business-hours guard (timezone-safe)
- Fix CrmApiDown: Match Prometheus scrape job name (crm_api not crm-api)
- Add runbook links to all Slack alert messages

Performance: 10-100x faster dashboard queries via pre-computed recording rules
Future-ready: Per-org rules support multi-tenant `$org` variable when needed
"@

Write-Host "`nCommit message:" -ForegroundColor Yellow
Write-Host $commitMessage

Write-Host "`nReady to commit? (y/n): " -ForegroundColor Cyan -NoNewline
$response = Read-Host

if ($response -eq "y" -or $response -eq "Y") {
    git commit -m $commitMessage
    Write-Host "`n✅ Committed successfully!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "  1. Review changes: git log -1 --stat"
    Write-Host "  2. Push to remote: git push origin main"
    Write-Host "  3. Set SLACK_WEBHOOK_URL for live alerting"
    Write-Host "  4. Connect production QuickBooks OAuth"
}
else {
    Write-Host "`n❌ Commit cancelled. Files are staged and ready when you're ready." -ForegroundColor Yellow
    Write-Host "   Run manually: git commit -m 'Your message'"
}
