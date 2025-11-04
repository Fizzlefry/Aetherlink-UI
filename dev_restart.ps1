Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

Write-Host "🔄 Restarting AetherLink stack..."
& "$PSScriptRoot\dev_stop.ps1" | Out-Null
Start-Sleep -Seconds 1
& "$PSScriptRoot\dev_setup.ps1"
