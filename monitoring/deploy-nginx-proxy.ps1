# Deploy Nginx Reverse Proxy for AetherLink Monitoring
# Usage: .\deploy-nginx-proxy.ps1 -Password "YourSecurePassword123"
# Optional: .\deploy-nginx-proxy.ps1 -User "admin" -Password "YourSecurePassword123"

param(
    [string]$User = "aether",
    [Parameter(Mandatory = $true)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host "=== DEPLOYING NGINX REVERSE PROXY ===" -ForegroundColor Cyan
Write-Host ""

# Get script root
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$nginxDir = Join-Path $root "nginx"

# Create nginx directory if it doesn't exist
Write-Host "📁 Creating nginx directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $nginxDir | Out-Null

# Generate htpasswd using httpd container (Windows-friendly, BCrypt hash)
Write-Host "🔐 Generating .htpasswd file..." -ForegroundColor Yellow
$cmd = "docker run --rm httpd:2.4 htpasswd -nbB $User $Password"
$cred = (& cmd /c $cmd 2>$null)

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to generate htpasswd file" -ForegroundColor Red
    Write-Host "   Make sure Docker is running" -ForegroundColor Yellow
    exit 1
}

$htpasswdPath = Join-Path $nginxDir ".htpasswd"
$cred | Out-File -Encoding ascii $htpasswdPath
Write-Host "✅ Created nginx/.htpasswd" -ForegroundColor Green
Write-Host "   User: $User" -ForegroundColor White
Write-Host ""

# Check if nginx.conf exists
$nginxConfPath = Join-Path $nginxDir "nginx.conf"
if (-not (Test-Path $nginxConfPath)) {
    Write-Host "⚠️  nginx/nginx.conf not found!" -ForegroundColor Red
    Write-Host "   Expected at: $nginxConfPath" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Found nginx.conf" -ForegroundColor Green
Write-Host ""

# Update hosts file instructions
Write-Host "📝 NEXT STEP: Add these lines to your hosts file:" -ForegroundColor Cyan
Write-Host "   File: C:\Windows\System32\drivers\etc\hosts" -ForegroundColor White
Write-Host ""
Write-Host "   127.0.0.1 grafana.aetherlink.local" -ForegroundColor Yellow
Write-Host "   127.0.0.1 alertmanager.aetherlink.local" -ForegroundColor Yellow
Write-Host ""
Write-Host "   (Run Notepad as Administrator to edit this file)" -ForegroundColor Gray
Write-Host ""

# Pause for user confirmation
$response = Read-Host "Have you added the hosts entries? (y/n)"
if ($response -ne "y") {
    Write-Host "⚠️  Please add hosts entries and run this script again" -ForegroundColor Yellow
    exit 0
}

# Deploy nginx proxy
Write-Host "🚀 Starting Nginx proxy..." -ForegroundColor Yellow
docker compose -f docker-compose.nginx.yml up -d nginx-proxy

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start Nginx proxy" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== DEPLOYMENT COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Nginx proxy running on port 80" -ForegroundColor Green
Write-Host ""
Write-Host "🧪 TEST URLS:" -ForegroundColor Cyan
Write-Host "   Grafana:      http://grafana.aetherlink.local" -ForegroundColor White
Write-Host "   Alertmanager: http://alertmanager.aetherlink.local (auth required)" -ForegroundColor White
Write-Host ""
Write-Host "🔐 CREDENTIALS:" -ForegroundColor Cyan
Write-Host "   Username: $User" -ForegroundColor White
Write-Host "   Password: ********" -ForegroundColor White
Write-Host ""
Write-Host "🧪 TEST COMMANDS:" -ForegroundColor Cyan
Write-Host "   curl -I http://grafana.aetherlink.local" -ForegroundColor White
Write-Host "   curl -I -u ${User}:${Password} http://alertmanager.aetherlink.local" -ForegroundColor White
Write-Host ""
Write-Host "📊 View logs:" -ForegroundColor Cyan
Write-Host "   docker logs -f aether-proxy" -ForegroundColor White
Write-Host ""
