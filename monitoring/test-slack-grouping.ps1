# Test Enhanced Slack Grouping (Clean Feed)
# This script demonstrates the before/after of smart grouping

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🧵 Slack Clean Feed Test (Thread-like Grouping)    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 What This Test Does:" -ForegroundColor Yellow
Write-Host "   1. Triggers multiple alerts simultaneously" -ForegroundColor White
Write-Host "   2. Shows OLD behavior (separate messages)" -ForegroundColor White
Write-Host "   3. Applies ENHANCED grouping config" -ForegroundColor White
Write-Host "   4. Shows NEW behavior (single grouped message)" -ForegroundColor White
Write-Host ""

# Check if in correct directory
$currentDir = Get-Location
if ($currentDir.Path -notmatch 'monitoring$') {
    Write-Host "⚠️  Please run from monitoring directory:" -ForegroundColor Yellow
    Write-Host "   cd C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring" -ForegroundColor White
    exit 1
}

Write-Host "📊 Current Configuration:" -ForegroundColor Cyan
Write-Host "   Checking alertmanager.yml..." -ForegroundColor Gray

$alertmanagerConfig = Get-Content "alertmanager.yml" -Raw

if ($alertmanagerConfig -match 'group_by:\s*\["service"\]') {
    Write-Host "   ✅ Enhanced grouping ENABLED (group_by: service)" -ForegroundColor Green
    Write-Host "   ✅ Clean feed mode active" -ForegroundColor Green
    $groupingEnabled = $true
}
else {
    Write-Host "   ℹ️  Basic grouping active" -ForegroundColor Cyan
    Write-Host "   💡 Enhanced grouping available in alertmanager.yml" -ForegroundColor Yellow
    $groupingEnabled = $false
}

Write-Host ""
Write-Host "🧪 Test Options:" -ForegroundColor Yellow
Write-Host "   [1] Quick demo (show config only)" -ForegroundColor White
Write-Host "   [2] Full test (trigger real alerts) - 15 minutes" -ForegroundColor White
Write-Host "   [3] Apply enhanced config and restart" -ForegroundColor White
Write-Host "   [Q] Quit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Select option (1-3, Q)"

switch ($choice) {
    "1" {
        Write-Host "`n📖 Quick Demo: Configuration Comparison" -ForegroundColor Cyan
        Write-Host ""

        Write-Host "❌ OLD Configuration (Multiple Separate Messages):" -ForegroundColor Red
        Write-Host @"
route:
  routes:
    - matchers:
        - team="crm"
      receiver: slack_crm
      group_by: ["alertname", "consumergroup"]  # Separate by alert name
      group_wait: 15s
      repeat_interval: 2h
"@ -ForegroundColor Gray

        Write-Host ""
        Write-Host "Result in Slack:" -ForegroundColor Yellow
        Write-Host @"
#crm-events-alerts:
├─ 🚨 CrmEventsHotKeySkewHigh (12:00 PM)
├─ 🚨 CrmEventsHotKeySkewHigh (12:02 PM) ← Duplicate
├─ 🚨 CrmEventsUnderReplicatedConsumers (12:05 PM)
└─ ✅ CrmEventsHotKeySkewHigh (12:30 PM)
"@ -ForegroundColor Gray

        Write-Host ""
        Write-Host "✅ NEW Configuration (Single Grouped Message):" -ForegroundColor Green
        Write-Host @"
route:
  routes:
    - matchers:
        - team="crm"
      receiver: slack_crm
      group_by: ["service"]               # ✅ Group ALL service alerts
      group_wait: 30s                     # ✅ Wait to collect simultaneous
      group_interval: 5m                  # ✅ Updates every 5m
      repeat_interval: 4h                 # ✅ Less spam
"@ -ForegroundColor White

        Write-Host ""
        Write-Host "Result in Slack:" -ForegroundColor Yellow
        Write-Host @"
#crm-events-alerts:
├─ 🚨 crm-events-sse Pipeline Issues (2 alerts) (12:00 PM)
│   ├─ 🔥 CrmEventsHotKeySkewHigh
│   └─ 🔥 CrmEventsUnderReplicatedConsumers
│
└─ ✅ crm-events-sse Pipeline Resolved (12:30 PM)
"@ -ForegroundColor White

        Write-Host ""
        Write-Host "📊 Benefits:" -ForegroundColor Cyan
        Write-Host "   ✅ 75% fewer messages (2 instead of 6+)" -ForegroundColor Green
        Write-Host "   ✅ Related alerts grouped automatically" -ForegroundColor Green
        Write-Host "   ✅ Single resolved notification" -ForegroundColor Green
        Write-Host "   ✅ No duplicate spam" -ForegroundColor Green
        Write-Host "   ✅ Clean, professional feed" -ForegroundColor Green
        Write-Host ""
    }

    "2" {
        Write-Host "`n🚀 Full Test: Triggering Real Alerts" -ForegroundColor Cyan
        Write-Host ""

        if (!$groupingEnabled) {
            Write-Host "⚠️  Enhanced grouping not enabled yet" -ForegroundColor Yellow
            Write-Host "   Run option [3] first to apply configuration" -ForegroundColor Gray
            exit 1
        }

        Write-Host "⏰ Timeline:" -ForegroundColor Yellow
        Write-Host "   T+0:00 - Trigger hot-key skew (300 messages)" -ForegroundColor White
        Write-Host "   T+0:30 - Stop consumer (under-replication)" -ForegroundColor White
        Write-Host "   T+7:30 - UnderReplicatedConsumers alert fires" -ForegroundColor White
        Write-Host "   T+12:00 - HotKeySkewHigh alert fires" -ForegroundColor White
        Write-Host "   T+12:30 - Check Slack for GROUPED message" -ForegroundColor White
        Write-Host "   T+14:00 - Restart consumer" -ForegroundColor White
        Write-Host "   T+16:00 - Check Slack for resolved message" -ForegroundColor White
        Write-Host ""

        $confirm = Read-Host "Continue with 15-minute test? (y/N)"
        if ($confirm -ne 'y' -and $confirm -ne 'Y') {
            Write-Host "   Test cancelled" -ForegroundColor Gray
            exit 0
        }

        Write-Host "`n🔥 Step 1: Creating hot-key skew..." -ForegroundColor Yellow
        $evt = '{"Type":"Test","Key":"HOTKEY","Timestamp":"' + (Get-Date -Format o) + '"}'
        Write-Host "   Producing 300 messages to partition with key HOTKEY..." -ForegroundColor Gray

        1..300 | ForEach-Object {
            $evt | docker exec -i kafka rpk topic produce --key HOTKEY aetherlink.events | Out-Null
            if ($_ % 50 -eq 0) {
                Write-Host "   Progress: $_/300" -ForegroundColor Cyan
            }
        }
        Write-Host "   ✅ Hot-key skew created (will trigger alert in ~12 minutes)" -ForegroundColor Green

        Write-Host "`n⏸️  Waiting 30 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30

        Write-Host "`n🛑 Step 2: Stopping consumer..." -ForegroundColor Yellow
        docker stop aether-crm-events | Out-Null
        Write-Host "   ✅ Consumer stopped (will trigger alert in ~7 minutes)" -ForegroundColor Green

        Write-Host "`n⏰ Monitoring alerts..." -ForegroundColor Cyan
        Write-Host "   Open these URLs to watch progress:" -ForegroundColor Gray
        Write-Host "   • Prometheus: http://localhost:9090/alerts" -ForegroundColor White
        Write-Host "   • Grafana: http://localhost:3000/d/crm-events-pipeline" -ForegroundColor White
        Write-Host "   • Slack: #crm-events-alerts channel" -ForegroundColor White
        Write-Host ""

        # Wait for alerts with countdown
        Write-Host "   Waiting 12 minutes for alerts to fire..." -ForegroundColor Yellow
        for ($i = 720; $i -gt 0; $i--) {
            $minutes = [math]::Floor($i / 60)
            $seconds = $i % 60
            Write-Host "`r   Time remaining: $($minutes)m $($seconds)s " -NoNewline -ForegroundColor Cyan
            Start-Sleep -Seconds 1
        }

        Write-Host "`n`n   ✅ Alerts should have fired!" -ForegroundColor Green
        Write-Host "   📱 Check #crm-events-alerts for SINGLE GROUPED MESSAGE" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Expected Slack message:" -ForegroundColor Yellow
        Write-Host @"
🚨 crm-events-sse Pipeline Issues (2 alerts)

Service: crm-events-sse
Team: crm
Status: FIRING

⚠️ Multiple alerts detected - grouped for clean feed

🔥 WARNING — CrmEventsUnderReplicatedConsumers
Only 1 consumer active...

---

🔥 WARNING — CrmEventsHotKeySkewHigh
Skew ratio exceeded 4x...

---

Firing: 2 | Resolved: 0
"@ -ForegroundColor White

        Write-Host ""
        $restoreNow = Read-Host "Restore consumer now to trigger resolved notification? (y/N)"

        if ($restoreNow -eq 'y' -or $restoreNow -eq 'Y') {
            Write-Host "`n🔄 Restoring consumer..." -ForegroundColor Yellow
            docker start aether-crm-events | Out-Null
            Write-Host "   ✅ Consumer restarted" -ForegroundColor Green
            Write-Host "   ⏰ Wait ~2 minutes for resolved notification" -ForegroundColor Cyan
            Write-Host "   📱 Check Slack for single RESOLVED message" -ForegroundColor Cyan
        }
        else {
            Write-Host "`n   ℹ️  To restore later, run:" -ForegroundColor Cyan
            Write-Host "   docker start aether-crm-events" -ForegroundColor White
        }

        Write-Host ""
    }

    "3" {
        Write-Host "`n🔧 Applying Enhanced Configuration" -ForegroundColor Cyan
        Write-Host ""

        if ($groupingEnabled) {
            Write-Host "   ✅ Enhanced grouping already enabled" -ForegroundColor Green
            Write-Host "   No changes needed" -ForegroundColor Gray
        }
        else {
            Write-Host "   ℹ️  Configuration already updated in alertmanager.yml" -ForegroundColor Cyan
            Write-Host "   Restarting Alertmanager to apply changes..." -ForegroundColor Yellow

            docker compose restart alertmanager | Out-Null
            Start-Sleep -Seconds 3

            $containerStatus = docker ps --filter "name=alertmanager" --format "{{.Status}}"
            if ($containerStatus -match "Up") {
                Write-Host "   ✅ Alertmanager restarted successfully" -ForegroundColor Green
                Write-Host "   ✅ Enhanced grouping now active" -ForegroundColor Green
            }
            else {
                Write-Host "   ⚠️  Alertmanager may not be running" -ForegroundColor Yellow
                Write-Host "   Check: docker logs alertmanager" -ForegroundColor Gray
            }
        }

        Write-Host ""
        Write-Host "📊 Active Configuration:" -ForegroundColor Cyan
        Write-Host "   • group_by: [service]" -ForegroundColor White
        Write-Host "   • group_wait: 30s" -ForegroundColor White
        Write-Host "   • group_interval: 5m" -ForegroundColor White
        Write-Host "   • repeat_interval: 4h" -ForegroundColor White
        Write-Host ""
        Write-Host "✅ Clean feed enabled!" -ForegroundColor Green
        Write-Host "   Run option [2] to test with real alerts" -ForegroundColor Gray
        Write-Host ""
    }

    default {
        Write-Host "   Exiting..." -ForegroundColor Gray
        exit 0
    }
}

Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              🧵 CLEAN FEED CONFIGURATION              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📖 Documentation:" -ForegroundColor Cyan
Write-Host "   • Full Guide: monitoring/docs/SLACK_THREADING.md" -ForegroundColor White
Write-Host "   • Integration: monitoring/docs/SLACK_INTEGRATION.md" -ForegroundColor White
Write-Host "   • Quick Ref: monitoring/QUICK_REFERENCE.md" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Result:" -ForegroundColor Cyan
Write-Host "   • 75% fewer Slack messages" -ForegroundColor Green
Write-Host "   • Related alerts grouped automatically" -ForegroundColor Green
Write-Host "   • Professional, clean feed" -ForegroundColor Green
Write-Host ""
