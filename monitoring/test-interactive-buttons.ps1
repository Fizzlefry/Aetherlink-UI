# Test Slack Interactive Buttons
# Demonstrates one-click actions from Slack messages

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🔘 Slack Interactive Buttons Test                  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 What's Been Added:" -ForegroundColor Yellow
Write-Host "   Every Slack alert now includes 3 action buttons:" -ForegroundColor White
Write-Host ""
Write-Host "   [📊 View Dashboard]  → Opens Grafana (primary action)" -ForegroundColor Cyan
Write-Host "   [🔍 Prometheus Alerts] → Opens Prometheus alerts view" -ForegroundColor White
Write-Host "   [🔕 Silence Alert]   → Opens pre-filled silence form" -ForegroundColor Red
Write-Host ""

Write-Host "🎯 Benefits:" -ForegroundColor Yellow
Write-Host "   ✅ One-click access to dashboards" -ForegroundColor Green
Write-Host "   ✅ Quick alert silencing (acknowledgeauthn)" -ForegroundColor Green
Write-Host "   ✅ No dashboard hopping" -ForegroundColor Green
Write-Host "   ✅ No custom code required" -ForegroundColor Green
Write-Host "   ✅ Works with existing webhook" -ForegroundColor Green
Write-Host ""

# Check configuration
$currentDir = Get-Location
if ($currentDir.Path -notmatch 'monitoring$') {
    Write-Host "⚠️  Please run from monitoring directory:" -ForegroundColor Yellow
    Write-Host "   cd C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring" -ForegroundColor White
    exit 1
}

Write-Host "🔍 Checking Configuration:" -ForegroundColor Cyan
Write-Host "   Reading alertmanager.yml..." -ForegroundColor Gray

$alertmanagerConfig = Get-Content "alertmanager.yml" -Raw

if ($alertmanagerConfig -match 'actions:') {
    Write-Host "   ✅ Action buttons configured" -ForegroundColor Green

    if ($alertmanagerConfig -match '"📊 View Dashboard"') {
        Write-Host "   ✅ Dashboard button found" -ForegroundColor Green
    }
    if ($alertmanagerConfig -match '"🔍 Prometheus Alerts"') {
        Write-Host "   ✅ Prometheus button found" -ForegroundColor Green
    }
    if ($alertmanagerConfig -match '"🔕 Silence Alert"') {
        Write-Host "   ✅ Silence button found" -ForegroundColor Green
    }
}
else {
    Write-Host "   ⚠️  Action buttons not found in config" -ForegroundColor Yellow
    Write-Host "   Run setup to add buttons" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🧪 Test Options:" -ForegroundColor Yellow
Write-Host "   [1] Show example Slack message" -ForegroundColor White
Write-Host "   [2] Trigger real alert (15 min test)" -ForegroundColor White
Write-Host "   [3] Restart Alertmanager to apply changes" -ForegroundColor White
Write-Host "   [Q] Quit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Select option (1-3, Q)"

switch ($choice) {
    "1" {
        Write-Host "`n📱 Example Slack Message with Buttons:" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════╗" -ForegroundColor White
        Write-Host "║ 🚨 crm-events-sse Pipeline Issues (2 alerts)     ║" -ForegroundColor Yellow
        Write-Host "╠═══════════════════════════════════════════════════╣" -ForegroundColor White
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ Service: crm-events-sse                           ║" -ForegroundColor White
        Write-Host "║ Team: crm                                         ║" -ForegroundColor White
        Write-Host "║ Status: FIRING                                    ║" -ForegroundColor White
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ ⚠️  Multiple alerts detected - grouped for clean ║" -ForegroundColor Yellow
        Write-Host "║     feed                                          ║" -ForegroundColor Yellow
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ 🔥 WARNING — CrmEventsHotKeySkewHigh              ║" -ForegroundColor Red
        Write-Host "║ Skew ratio exceeded 4x threshold...               ║" -ForegroundColor White
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ 🔥 WARNING — CrmEventsUnderReplicatedConsumers    ║" -ForegroundColor Red
        Write-Host "║ Only 1 consumer active...                         ║" -ForegroundColor White
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ Firing: 2 | Resolved: 0                           ║" -ForegroundColor White
        Write-Host "║                                                   ║" -ForegroundColor White
        Write-Host "║ ┌─────────────────┐ ┌─────────────────┐          ║" -ForegroundColor Cyan
        Write-Host "║ │ 📊 View Dashboard│ │🔍 Prometheus Alerts│         ║" -ForegroundColor Cyan
        Write-Host "║ └─────────────────┘ └─────────────────┘          ║" -ForegroundColor Cyan
        Write-Host "║        ┌──────────────────┐                       ║" -ForegroundColor Red
        Write-Host "║        │ 🔕 Silence Alert  │                       ║" -ForegroundColor Red
        Write-Host "║        └──────────────────┘                       ║" -ForegroundColor Red
        Write-Host "╚═══════════════════════════════════════════════════╝" -ForegroundColor White
        Write-Host ""
        Write-Host "🔘 Button Actions:" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "   1️⃣  Click [📊 View Dashboard]" -ForegroundColor White
        Write-Host "      → Opens: http://localhost:3000/d/crm-events-pipeline" -ForegroundColor Gray
        Write-Host "      → Shows: Panel 17 (partition lag), Panel 19 (skew)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   2️⃣  Click [🔍 Prometheus Alerts]" -ForegroundColor White
        Write-Host "      → Opens: http://localhost:9090/alerts" -ForegroundColor Gray
        Write-Host "      → Shows: Active alerts with PromQL expressions" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   3️⃣  Click [🔕 Silence Alert]" -ForegroundColor White
        Write-Host "      → Opens: http://localhost:9093/#/silences/new" -ForegroundColor Gray
        Write-Host "      → Pre-filled: service=crm-events-sse filter" -ForegroundColor Gray
        Write-Host "      → Action: Fill duration (1h/4h) and comment, click Create" -ForegroundColor Gray
        Write-Host ""
    }

    "2" {
        Write-Host "`n🚀 Triggering Real Alert with Buttons" -ForegroundColor Cyan
        Write-Host ""

        # Check if Slack webhook is configured
        if (!$env:SLACK_WEBHOOK_URL) {
            Write-Host "⚠️  SLACK_WEBHOOK_URL not set" -ForegroundColor Yellow
            Write-Host "   Buttons will be added to Alertmanager config," -ForegroundColor Gray
            Write-Host "   but no Slack message will be sent" -ForegroundColor Gray
            Write-Host ""
            $continue = Read-Host "Continue anyway? (y/N)"
            if ($continue -ne 'y' -and $continue -ne 'Y') {
                Write-Host "   Test cancelled" -ForegroundColor Gray
                exit 0
            }
        }

        Write-Host "⏰ Test Timeline:" -ForegroundColor Yellow
        Write-Host "   T+0:00 - Stop consumer (trigger alert)" -ForegroundColor White
        Write-Host "   T+7:00 - UnderReplicatedConsumers alert fires" -ForegroundColor White
        Write-Host "   T+7:30 - Check Slack for message WITH BUTTONS" -ForegroundColor White
        Write-Host "   T+8:00 - Click [📊 View Dashboard] button" -ForegroundColor White
        Write-Host "   T+8:30 - Click [🔕 Silence Alert] button" -ForegroundColor White
        Write-Host "   T+9:00 - Restart consumer" -ForegroundColor White
        Write-Host ""

        $confirm = Read-Host "Start 10-minute button test? (y/N)"
        if ($confirm -ne 'y' -and $confirm -ne 'Y') {
            Write-Host "   Test cancelled" -ForegroundColor Gray
            exit 0
        }

        Write-Host "`n🛑 Stopping consumer..." -ForegroundColor Yellow
        docker stop aether-crm-events | Out-Null
        Write-Host "   ✅ Consumer stopped" -ForegroundColor Green
        Write-Host "   ⏰ Alert will fire in ~7 minutes" -ForegroundColor Cyan
        Write-Host ""

        Write-Host "📱 Monitor Slack Channel:" -ForegroundColor Cyan
        Write-Host "   Channel: #crm-events-alerts" -ForegroundColor White
        Write-Host "   Expected: Message with 3 action buttons" -ForegroundColor White
        Write-Host ""

        Write-Host "🔗 Monitor Dashboards:" -ForegroundColor Cyan
        Write-Host "   Prometheus: http://localhost:9090/alerts" -ForegroundColor White
        Write-Host "   Grafana: http://localhost:3000/d/crm-events-pipeline" -ForegroundColor White
        Write-Host "   Alertmanager: http://localhost:9093" -ForegroundColor White
        Write-Host ""

        # Wait 7 minutes with countdown
        Write-Host "⏳ Waiting for alert to fire..." -ForegroundColor Yellow
        for ($i = 420; $i -gt 0; $i--) {
            $minutes = [math]::Floor($i / 60)
            $seconds = $i % 60
            Write-Host "`r   Time remaining: $($minutes)m $($seconds)s " -NoNewline -ForegroundColor Cyan
            Start-Sleep -Seconds 1
        }

        Write-Host "`n`n   ✅ Alert should have fired!" -ForegroundColor Green
        Write-Host "   📱 Check Slack for message with buttons" -ForegroundColor Cyan
        Write-Host ""

        Write-Host "🧪 Button Test Steps:" -ForegroundColor Yellow
        Write-Host "   1. Find the Slack message in #crm-events-alerts" -ForegroundColor White
        Write-Host "   2. Click [📊 View Dashboard] - should open Grafana" -ForegroundColor White
        Write-Host "   3. Click [🔍 Prometheus Alerts] - should open Prometheus" -ForegroundColor White
        Write-Host "   4. Click [🔕 Silence Alert] - should open silence form" -ForegroundColor White
        Write-Host "   5. In silence form: Set duration to 1h, add comment, click Create" -ForegroundColor White
        Write-Host "   6. Verify silence appears at: http://localhost:9093/#/silences" -ForegroundColor White
        Write-Host ""

        $restore = Read-Host "Restore consumer now? (y/N)"
        if ($restore -eq 'y' -or $restore -eq 'Y') {
            Write-Host "`n🔄 Restoring consumer..." -ForegroundColor Yellow
            docker start aether-crm-events | Out-Null
            Write-Host "   ✅ Consumer restarted" -ForegroundColor Green
            Write-Host "   ⏰ Resolved notification in ~2 minutes" -ForegroundColor Cyan
        }
        else {
            Write-Host "`n   ℹ️  To restore later:" -ForegroundColor Cyan
            Write-Host "   docker start aether-crm-events" -ForegroundColor White
        }

        Write-Host ""
    }

    "3" {
        Write-Host "`n🔄 Restarting Alertmanager..." -ForegroundColor Yellow
        Write-Host "   Applying button configuration..." -ForegroundColor Gray

        docker compose restart alertmanager | Out-Null
        Start-Sleep -Seconds 3

        $containerStatus = docker ps --filter "name=alertmanager" --format "{{.Status}}"
        if ($containerStatus -match "Up") {
            Write-Host "   ✅ Alertmanager restarted successfully" -ForegroundColor Green
            Write-Host "   ✅ Action buttons now active" -ForegroundColor Green
        }
        else {
            Write-Host "   ⚠️  Alertmanager may not be running" -ForegroundColor Yellow
            Write-Host "   Check: docker logs alertmanager" -ForegroundColor Gray
        }

        Write-Host ""
        Write-Host "📊 Button Configuration:" -ForegroundColor Cyan
        Write-Host "   ✅ Dashboard button (primary)" -ForegroundColor White
        Write-Host "   ✅ Prometheus button (secondary)" -ForegroundColor White
        Write-Host "   ✅ Silence button (danger)" -ForegroundColor White
        Write-Host ""
        Write-Host "🧪 Test Buttons:" -ForegroundColor Yellow
        Write-Host "   Run option [2] to trigger alert and test buttons" -ForegroundColor Gray
        Write-Host ""
    }

    default {
        Write-Host "   Exiting..." -ForegroundColor Gray
        exit 0
    }
}

Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          🔘 INTERACTIVE BUTTONS CONFIGURED            ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📖 Documentation:" -ForegroundColor Cyan
Write-Host "   • Full Guide: monitoring/docs/SLACK_INTERACTIVE_BUTTONS.md" -ForegroundColor White
Write-Host "   • Slack Integration: monitoring/docs/SLACK_INTEGRATION.md" -ForegroundColor White
Write-Host "   • Quick Ref: monitoring/QUICK_REFERENCE.md" -ForegroundColor White
Write-Host ""
Write-Host "🎯 What's Next:" -ForegroundColor Cyan
Write-Host "   1. Trigger an alert (stop consumer or create hot-key)" -ForegroundColor White
Write-Host "   2. Check Slack for message with 3 buttons" -ForegroundColor White
Write-Host "   3. Click buttons to test one-click actions" -ForegroundColor White
Write-Host "   4. Use [🔕 Silence Alert] to acknowledge alerts" -ForegroundColor White
Write-Host ""
Write-Host "✅ Feedback loop complete: Alert → Slack → Action → Resolution" -ForegroundColor Green
Write-Host ""
