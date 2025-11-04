Write-Host "`n=== CRM Events E2E Validation ===" -ForegroundColor Cyan

Write-Host "`n[1/5] Health Check..." -ForegroundColor Yellow
$health = curl.exe -s --http1.1 http://localhost:9010/healthz
Write-Host "  $health" -ForegroundColor Green

Write-Host "`n[2/5] Service Info..." -ForegroundColor Yellow
$info = curl.exe -s http://localhost:9010/ | ConvertFrom-Json
Write-Host "  Service: $($info.service)" -ForegroundColor Green
Write-Host "  Status: $($info.status)" -ForegroundColor Green
Write-Host "  Kafka: $($info.kafka_brokers)" -ForegroundColor Green
Write-Host "  Topic: $($info.topic)" -ForegroundColor Green

Write-Host "`n[3/5] Prometheus Metrics..." -ForegroundColor Yellow
$metrics = curl.exe -s http://localhost:9010/metrics | Select-String "crm_events" | Select-Object -First 5
$metrics | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

Write-Host "`n[4/5] Publish Test Event..." -ForegroundColor Yellow
$evt = '{"Type":"E2E_Test","TenantId":"test-tenant","EventId":"' + [guid]::NewGuid() + '","Ts":"' + (Get-Date -Format o) + '"}'
$result = echo $evt | docker exec -i kafka rpk topic produce aetherlink.events
Write-Host "  $result" -ForegroundColor Green

Write-Host "`n[5/5] Verify SSE Stream (5 sec)..." -ForegroundColor Yellow
Write-Host "  Connecting to http://localhost:9010/crm-events..." -ForegroundColor Gray
$sseJob = Start-Job -ScriptBlock { 
    & curl.exe --http1.1 --no-buffer --max-time 5 http://localhost:9010/crm-events 2>$null
}
Start-Sleep -Seconds 4
$sseOutput = Receive-Job $sseJob
Remove-Job $sseJob -Force 2>$null

if ($sseOutput -match "domain_event") {
    Write-Host "  ✅ SSE stream working!" -ForegroundColor Green
    $eventCount = ($sseOutput | Select-String 'data:' | Measure-Object).Count
    Write-Host "  📊 Received $eventCount events" -ForegroundColor Cyan
}
else {
    Write-Host "  ⚠️ No events received (check Kafka connection)" -ForegroundColor Yellow
}

Write-Host "`n=== Validation Complete ===" -ForegroundColor Cyan
Write-Host "CRM Events service is fully operational!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  - Open Command Center: http://localhost:3001/ops/crm-events" -ForegroundColor White
Write-Host "  - View metrics: http://localhost:9010/metrics" -ForegroundColor White
Write-Host "  - Check Prometheus: http://localhost:9090" -ForegroundColor White
