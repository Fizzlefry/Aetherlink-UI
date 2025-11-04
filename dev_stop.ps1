<#
Stops the spawned API/Worker PowerShell windows and the Redis/Postgres containers.
Use -Prune to also remove containers. Non-destructive by default.
#>
param(
    [switch]$Prune  # also docker rm
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'SilentlyContinue'

Write-Host "🛑 Stopping AetherLink dev processes and containers..."

# Close API/Worker windows by title (matches what dev_setup.ps1 creates)
Get-Process powershell |
Where-Object { $_.MainWindowTitle -match '^(API|Worker)( |\()' } |
ForEach-Object {
    Write-Host "  • Closing $($_.MainWindowTitle)"
    $_.CloseMainWindow() | Out-Null
}

Start-Sleep -Seconds 2

# Stop docker containers if running
$containers = @('aether-redis', 'aether-postgres')
foreach ($n in $containers) {
    if (docker ps --format "{{.Names}}" | Select-String -SimpleMatch $n) {
        Write-Host "  • docker stop $n"
        docker stop $n | Out-Null
    }
    if ($Prune -and (docker ps -a --format "{{.Names}}" | Select-String -SimpleMatch $n)) {
        Write-Host "  • docker rm $n"
        docker rm $n | Out-Null
    }
}

Write-Host "✅ Done."
