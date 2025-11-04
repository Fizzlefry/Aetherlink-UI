$ErrorActionPreference = 'Stop'
Write-Host "`n=== Autoheal Audit (last 200) ===" -ForegroundColor Cyan

try {
    $txt = Invoke-RestMethod 'http://localhost:9009/audit?n=200'
    $txt -split "`n" | ForEach-Object {
        if ($_ -ne "") {
            $obj = $_ | ConvertFrom-Json
            $alertname = if ($obj.alertname) { $obj.alertname } elseif ($obj.cmd) { $obj.cmd } else { $obj.reason }
            "{0} | {1,-20} | {2}" -f ([DateTimeOffset]::FromUnixTimeSeconds([int]$obj.ts).ToLocalTime().ToString("HH:mm:ss")), $obj.kind, $alertname
        }
    }
}
catch {
    Write-Warning "Audit endpoint unavailable: $($_.Exception.Message)"
}
Write-Host ""
