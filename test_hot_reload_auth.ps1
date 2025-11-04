# Hot-reload auth test
# Prerequisites: API running with $env:API_KEY_EXPERTCO set

Write-Host "1) Initial health check..."
.\makefile.ps1 health

Write-Host "`n2) Add a new API key to environment..."
$env:API_KEY_TEMP = "NEWKEY123"

Write-Host "`n3) Reload auth keys from environment..."
$headers = @{ "x-api-key" = $env:API_KEY_EXPERTCO }
try {
    $result = Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $headers
    Write-Host "✅ Reloaded: $($result | ConvertTo-Json)"
}
catch {
    Write-Host "❌ Reload failed: $_"
    exit 1
}

Write-Host "`n4) Test new key on protected endpoint..."
$newHeaders = @{ "x-api-key" = "NEWKEY123" }
try {
    $status = Invoke-RestMethod http://localhost:8000/ops/model-status -Headers $newHeaders
    Write-Host "✅ New key works: $($status | ConvertTo-Json -Depth 2)"
}
catch {
    Write-Host "❌ New key rejected: $_"
    exit 1
}

Write-Host "`n✅ Hot-reload test passed!"
