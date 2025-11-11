$payload = @(
    @{source="sensor_01";description="Temp spike";severity=4},
    @{source="camera_02";description="Motion detected";severity=3},
    @{source="gateway_03";description="Packet loss event";severity=2}
)

foreach ($p in $payload) {
    $json = ($p | ConvertTo-Json)
    try {
        $response = Invoke-RestMethod `
            -Uri "http://localhost:8000/ops/anomalies/" `
            -Method POST `
            -ContentType "application/json" `
            -Body $json `
            -ErrorAction Stop
        Write-Host " Created anomaly with ID $response" -ForegroundColor Green
    }
    catch {
        Write-Host " Failed: $_" -ForegroundColor Red
    }
}

Write-Host "`nSeed complete  anomalies inserted." -ForegroundColor Green
