# ============================================================================
# MAINTENANCE MODE - Silence Alerts During Deployments
# ============================================================================
# Silences all alerts for a specified duration to prevent paging during maintenance
# ============================================================================

param(
    [int]$DurationMinutes = 60,
    [string]$Comment = "Maintenance window"
)

Write-Host "`n=== MAINTENANCE MODE ===" -ForegroundColor Yellow
Write-Host "Silencing all alerts for $DurationMinutes minutes...`n" -ForegroundColor Gray

$startTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
$endTime = (Get-Date).ToUniversalTime().AddMinutes($DurationMinutes).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")

$body = @"
{
  "matchers": [
    {
      "name": "alertname",
      "value": ".*",
      "isRegex": true
    }
  ],
  "startsAt": "$startTime",
  "endsAt": "$endTime",
  "createdBy": "maintenance-script",
  "comment": "$Comment"
}
"@

try {
    $response = Invoke-RestMethod -Uri "http://localhost:9093/api/v2/silences" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body

    Write-Host "✅ Maintenance mode activated" -ForegroundColor Green
    Write-Host "   Silence ID: $($response.silenceID)" -ForegroundColor Gray
    Write-Host "   Start: $startTime" -ForegroundColor Gray
    Write-Host "   End: $endTime" -ForegroundColor Gray
    Write-Host "   Duration: $DurationMinutes minutes" -ForegroundColor Gray

    Write-Host "`n📊 View active silences:" -ForegroundColor Cyan
    Write-Host "   http://localhost:9093/#/silences" -ForegroundColor Gray

    Write-Host "`n💡 To delete this silence early:" -ForegroundColor Cyan
    Write-Host "   `$silenceId = '$($response.silenceID)'" -ForegroundColor Gray
    Write-Host "   Invoke-RestMethod -Uri `"http://localhost:9093/api/v2/silence/`$silenceId`" -Method DELETE" -ForegroundColor Gray

}
catch {
    Write-Host "❌ Failed to create silence: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Is Alertmanager running? http://localhost:9093" -ForegroundColor Yellow
}

Write-Host ""
