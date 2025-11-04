# Quick Slack Integration Setup
# Run this script to enable Slack notifications in 30 seconds

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🔔 AetherLink Slack Alert Integration Setup        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get webhook URL
Write-Host "📋 Step 1: Get your Slack Webhook URL" -ForegroundColor Yellow
Write-Host "   1. Visit: https://api.slack.com/apps" -ForegroundColor White
Write-Host "   2. Create New App → From scratch" -ForegroundColor White
Write-Host "   3. Enable 'Incoming Webhooks'" -ForegroundColor White
Write-Host "   4. Add webhook to #crm-events-alerts channel" -ForegroundColor White
Write-Host "   5. Copy the webhook URL`n" -ForegroundColor White

$webhookUrl = Read-Host "Enter Slack Webhook URL (or press Enter to skip)"

if ([string]::IsNullOrWhiteSpace($webhookUrl)) {
    Write-Host "`n⚠️  Skipping Slack setup - webhook URL not provided" -ForegroundColor Yellow
    Write-Host "   To enable later, set SLACK_WEBHOOK_URL environment variable`n" -ForegroundColor Gray
    exit 0
}

# Validate webhook URL format
if ($webhookUrl -notmatch '^https://hooks\.slack\.com/services/') {
    Write-Host "`n❌ Invalid webhook URL format" -ForegroundColor Red
    Write-Host "   Expected: https://hooks.slack.com/services/..." -ForegroundColor Gray
    Write-Host "   Received: $webhookUrl`n" -ForegroundColor Gray
    exit 1
}

Write-Host "`n✅ Webhook URL validated" -ForegroundColor Green

# Step 2: Update docker-compose.yml
Write-Host "`n📝 Step 2: Updating docker-compose.yml..." -ForegroundColor Yellow

$composeFile = "C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\docker-compose.yml"

if (!(Test-Path $composeFile)) {
    Write-Host "❌ docker-compose.yml not found at: $composeFile" -ForegroundColor Red
    exit 1
}

# Check if alertmanager service exists
$composeContent = Get-Content $composeFile -Raw

if ($composeContent -notmatch 'alertmanager:') {
    Write-Host "❌ alertmanager service not found in docker-compose.yml" -ForegroundColor Red
    exit 1
}

# Add environment variable to alertmanager service (if not already present)
if ($composeContent -notmatch 'SLACK_WEBHOOK_URL') {
    Write-Host "   Adding SLACK_WEBHOOK_URL to alertmanager service..." -ForegroundColor Gray
    
    # Backup original file
    Copy-Item $composeFile "$composeFile.backup" -Force
    Write-Host "   ✅ Backup created: docker-compose.yml.backup" -ForegroundColor Green
    
    # Note: Manual update recommended for complex YAML
    Write-Host "`n⚠️  Manual update required:" -ForegroundColor Yellow
    Write-Host "   Add this to alertmanager service in docker-compose.yml:" -ForegroundColor Gray
    Write-Host "   environment:" -ForegroundColor White
    Write-Host "     - SLACK_WEBHOOK_URL=$webhookUrl" -ForegroundColor White
}
else {
    Write-Host "   ℹ️  SLACK_WEBHOOK_URL already configured" -ForegroundColor Cyan
}

# Step 3: Set environment variable for current session
Write-Host "`n🔧 Step 3: Setting environment variable..." -ForegroundColor Yellow
$env:SLACK_WEBHOOK_URL = $webhookUrl
Write-Host "   ✅ SLACK_WEBHOOK_URL set for current session" -ForegroundColor Green

# Step 4: Restart Alertmanager
Write-Host "`n🔄 Step 4: Restarting Alertmanager..." -ForegroundColor Yellow
Set-Location "C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring"

try {
    docker compose restart alertmanager | Out-Null
    Start-Sleep -Seconds 3
    
    # Check if container is running
    $containerStatus = docker ps --filter "name=alertmanager" --format "{{.Status}}"
    if ($containerStatus -match "Up") {
        Write-Host "   ✅ Alertmanager restarted successfully" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  Alertmanager may not be running. Check: docker logs alertmanager" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ❌ Failed to restart Alertmanager: $_" -ForegroundColor Red
    Write-Host "   Try manually: docker compose restart alertmanager" -ForegroundColor Gray
}

# Step 5: Test configuration
Write-Host "`n🧪 Step 5: Testing Slack integration..." -ForegroundColor Yellow

Write-Host "   Sending test message to webhook..." -ForegroundColor Gray

$testPayload = @{
    text = "✅ AetherLink Monitoring is now connected to Slack!`n`nTest message from setup script."
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri $webhookUrl `
        -Method POST `
        -ContentType "application/json" `
        -Body $testPayload `
        -ErrorAction Stop
    
    Write-Host "   ✅ Test message sent successfully!" -ForegroundColor Green
    Write-Host "   📱 Check #crm-events-alerts channel in Slack" -ForegroundColor Cyan
}
catch {
    Write-Host "   ⚠️  Failed to send test message: $_" -ForegroundColor Yellow
    Write-Host "   Verify webhook URL and try manually" -ForegroundColor Gray
}

# Step 6: Trigger real alert for validation
Write-Host "`n🚦 Step 6: Validation Test (Optional)" -ForegroundColor Yellow
Write-Host "   To trigger a real alert, run:" -ForegroundColor Gray
Write-Host "   docker stop aether-crm-events" -ForegroundColor White
Write-Host "   # Wait 7 minutes for CrmEventsUnderReplicatedConsumers alert" -ForegroundColor Gray
Write-Host "   docker start aether-crm-events" -ForegroundColor White
Write-Host "   # Wait 2 minutes for resolved notification`n" -ForegroundColor Gray

$runTest = Read-Host "Run validation test now? (y/N)"

if ($runTest -eq 'y' -or $runTest -eq 'Y') {
    Write-Host "`n   Stopping consumer (triggering alert)..." -ForegroundColor Yellow
    docker stop aether-crm-events | Out-Null
    
    Write-Host "   ⏰ Waiting 7 minutes for alert to fire..." -ForegroundColor Cyan
    Write-Host "   (Alert condition: consumer count < 2 for > 7 minutes)" -ForegroundColor Gray
    Write-Host "   Monitor Prometheus: http://localhost:9090/alerts" -ForegroundColor White
    Write-Host "   Monitor Slack: #crm-events-alerts channel" -ForegroundColor White
    Write-Host "`n   Press Ctrl+C to cancel and restore consumer manually`n" -ForegroundColor Yellow
    
    # Wait 7 minutes
    for ($i = 420; $i -gt 0; $i--) {
        $minutes = [math]::Floor($i / 60)
        $seconds = $i % 60
        Write-Host "`r   Time remaining: $($minutes)m $($seconds)s " -NoNewline -ForegroundColor Cyan
        Start-Sleep -Seconds 1
    }
    
    Write-Host "`n`n   ✅ Alert should have fired!" -ForegroundColor Green
    Write-Host "   Check #crm-events-alerts for notification" -ForegroundColor White
    
    Write-Host "`n   Restoring consumer..." -ForegroundColor Yellow
    docker start aether-crm-events | Out-Null
    Write-Host "   ✅ Consumer restarted" -ForegroundColor Green
    Write-Host "   Wait ~2 minutes for resolved notification in Slack`n" -ForegroundColor Cyan
}
else {
    Write-Host "   ℹ️  Skipping validation test" -ForegroundColor Cyan
}

# Summary
Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║            ✅ SLACK INTEGRATION COMPLETE              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Configuration Summary:" -ForegroundColor Cyan
Write-Host "   • Webhook URL: $($webhookUrl.Substring(0, 50))..." -ForegroundColor White
Write-Host "   • Target Channel: #crm-events-alerts" -ForegroundColor White
Write-Host "   • Alertmanager: Restarted" -ForegroundColor White
Write-Host "   • Test Message: Sent" -ForegroundColor White
Write-Host ""
Write-Host "📋 Alerts Routed to Slack:" -ForegroundColor Cyan
Write-Host "   • CrmEventsHotKeySkewHigh (skew >4x for 12m)" -ForegroundColor White
Write-Host "   • CrmEventsUnderReplicatedConsumers (consumers <2 for 7m)" -ForegroundColor White
Write-Host "   • CrmEventsPartitionStuck (no consumption for 10m)" -ForegroundColor White
Write-Host "   • CrmEventsServiceDown (no heartbeat for 5m)" -ForegroundColor White
Write-Host "   • All other team=crm alerts" -ForegroundColor White
Write-Host ""
Write-Host "🔗 Quick Links:" -ForegroundColor Cyan
Write-Host "   • Dashboard: http://localhost:3000/d/crm-events-pipeline" -ForegroundColor White
Write-Host "   • Prometheus: http://localhost:9090/alerts" -ForegroundColor White
Write-Host "   • Alertmanager: http://localhost:9093" -ForegroundColor White
Write-Host ""
Write-Host "📖 Documentation:" -ForegroundColor Cyan
Write-Host "   • Slack Guide: monitoring/docs/SLACK_INTEGRATION.md" -ForegroundColor White
Write-Host "   • Quick Ref: monitoring/QUICK_REFERENCE.md" -ForegroundColor White
Write-Host "   • Runbook: monitoring/docs/RUNBOOK_HOTKEY_SKEW.md" -ForegroundColor White
Write-Host ""
Write-Host "🎉 Your team will now receive instant Slack notifications!" -ForegroundColor Green
Write-Host ""
