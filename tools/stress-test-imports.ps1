param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$Tenant = "stress-tenant",
    [int]$Count = 100,
    [int]$MinDelayMs = 200,
    [int]$MaxDelayMs = 1200
)

Write-Host "AetherLink Stress Test starting against $ApiBase for tenant '$Tenant'" -ForegroundColor Green

# ensure schedule exists
try {
    $body = @{ interval_sec = 180 } | ConvertTo-Json
    Invoke-WebRequest -Uri "$ApiBase/api/crm/import/acculynx/schedule" `
        -Method POST `
        -Headers @{ "x-tenant" = $Tenant; "x-ops" = "1"; "Content-Type" = "application/json" } `
        -Body $body | Out-Null
    Write-Host "Ensured schedule exists for $Tenant"
}
catch {
    Write-Warning "Failed to create schedule (maybe it exists): $_"
}

$ok = 0
$fail = 0

for ($i = 1; $i -le $Count; $i++) {
    $delay = Get-Random -Minimum $MinDelayMs -Maximum $MaxDelayMs
    try {
        $resp = Invoke-WebRequest -Uri "$ApiBase/api/crm/import/acculynx/run-now" `
            -Method POST `
            -Headers @{ "x-tenant" = $Tenant; "x-ops" = "1" } `
            -TimeoutSec 10
        $json = $resp.Content | ConvertFrom-Json
        if ($json.ok -eq $true) {
            $ok++
            Write-Host ("[{0}/{1}] OK  ({2})" -f $i, $Count, $json.message) -ForegroundColor Green
        }
        else {
            $fail++
            Write-Warning ("[{0}/{1}] FAIL: backend reported not ok" -f $i, $Count)
        }
    }
    catch {
        $fail++
        Write-Warning ("[{0}/{1}] ERROR: {2}" -f $i, $Count, $_.Exception.Message)
    }

    Start-Sleep -Milliseconds $delay
}

Write-Host "== STRESS TEST COMPLETE ==" -ForegroundColor Cyan
Write-Host "Success: $ok"
Write-Host "Failed : $fail"
Write-Host "Check data dir for audit growth and /ops/health for stability."
