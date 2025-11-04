# Setup Internal DNS for AetherLink Monitoring
# Run as Administrator: .\setup-hosts.ps1

param(
    [string]$IPAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ This script must be run as Administrator" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run:" -ForegroundColor Yellow
    Write-Host "   .\setup-hosts.ps1" -ForegroundColor White
    exit 1
}

Write-Host "=== SETTING UP INTERNAL DNS ===" -ForegroundColor Cyan
Write-Host ""

$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entries = @(
    "grafana.aetherlink.local",
    "alertmanager.aetherlink.local",
    "prometheus.aetherlink.local"
)

Write-Host "📝 Adding entries to: $hostsFile" -ForegroundColor Yellow
Write-Host ""

# Backup hosts file
$backupFile = "$hostsFile.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $hostsFile $backupFile
Write-Host "✅ Backup created: $backupFile" -ForegroundColor Green
Write-Host ""

# Read current hosts file
$hostsContent = Get-Content $hostsFile

# Check which entries are missing
$entriesToAdd = @()
foreach ($hostname in $entries) {
    $exists = $hostsContent | Where-Object { $_ -match "^\s*$IPAddress\s+$hostname\s*$" }
    if (-not $exists) {
        $entriesToAdd += $hostname
    }
    else {
        Write-Host "⏭️  Already exists: $hostname" -ForegroundColor Gray
    }
}

if ($entriesToAdd.Count -eq 0) {
    Write-Host ""
    Write-Host "✅ All entries already exist!" -ForegroundColor Green
    Write-Host ""
    exit 0
}

# Add missing entries
Write-Host ""
Write-Host "Adding entries:" -ForegroundColor Yellow
$newEntries = @()
$newEntries += ""
$newEntries += "# AetherLink Monitoring - Added $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
foreach ($hostname in $entriesToAdd) {
    $newEntries += "$IPAddress`t$hostname"
    Write-Host "  ✅ $hostname" -ForegroundColor Green
}

# Append to hosts file
Add-Content -Path $hostsFile -Value $newEntries

Write-Host ""
Write-Host "=== SETUP COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "🧪 TEST COMMANDS:" -ForegroundColor Cyan
Write-Host "   ping grafana.aetherlink.local" -ForegroundColor White
Write-Host "   ping alertmanager.aetherlink.local" -ForegroundColor White
Write-Host ""
Write-Host "🚀 NEXT STEP:" -ForegroundColor Cyan
Write-Host "   Deploy Nginx proxy: .\deploy-nginx-proxy.ps1 -Password 'YourPassword'" -ForegroundColor White
Write-Host ""
