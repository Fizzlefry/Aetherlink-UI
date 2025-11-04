# 🚀 ApexFlow CRM v1 - Deployment Script
# Auto-deploy ApexFlow with DNS + Docker build

param(
    [switch]$SkipDNS = $false,
    [switch]$Rebuild = $false
)

$ErrorActionPreference = "Stop"
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"

Write-Host "`n🚀 ApexFlow CRM v1 Deployment" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# === Step 1: Add DNS Entry ===
if (-not $SkipDNS) {
    Write-Host "📍 Step 1: Adding DNS entry for apexflow.aetherlink.local..." -ForegroundColor Yellow

    $hostsFile = "C:\Windows\System32\drivers\etc\hosts"
    $entry = "127.0.0.1 apexflow.aetherlink.local"

    # Check if running as admin
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "   ⚠️  Not running as Administrator - skipping DNS modification" -ForegroundColor Yellow
        Write-Host "   Run this command manually as Admin:" -ForegroundColor Yellow
        Write-Host "   Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value '127.0.0.1 apexflow.aetherlink.local'" -ForegroundColor Gray
    }
    else {
        # Check if entry already exists
        $content = Get-Content $hostsFile
        if ($content -match "apexflow.aetherlink.local") {
            Write-Host "   ✅ DNS entry already exists" -ForegroundColor Green
        }
        else {
            Add-Content -Path $hostsFile -Value "`n# Aetherlink ApexFlow CRM`n$entry"
            Write-Host "   ✅ DNS entry added" -ForegroundColor Green
        }
    }
}
else {
    Write-Host "📍 Step 1: Skipping DNS setup (--SkipDNS flag)" -ForegroundColor Gray
}

# === Step 2: Build Docker Image ===
Write-Host "`n🐳 Step 2: Building ApexFlow Docker image..." -ForegroundColor Yellow

Set-Location "$ROOT\infra\core"

if ($Rebuild) {
    Write-Host "   🔨 Rebuilding from scratch (no cache)..." -ForegroundColor Gray
    docker compose --env-file .env -f docker-compose.core.yml build --no-cache apexflow
}
else {
    docker compose --env-file .env -f docker-compose.core.yml build apexflow
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ Build complete" -ForegroundColor Green

# === Step 3: Start Services ===
Write-Host "`n🚀 Step 3: Starting ApexFlow + Database..." -ForegroundColor Yellow

docker compose --env-file .env -f docker-compose.core.yml up -d db-apexflow apexflow

if ($LASTEXITCODE -ne 0) {
    Write-Host "   ❌ Startup failed!" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ Services started" -ForegroundColor Green

# === Step 4: Wait for Health Check ===
Write-Host "`n🏥 Step 4: Waiting for health check..." -ForegroundColor Yellow

$maxAttempts = 30
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts -and -not $healthy) {
    Start-Sleep -Seconds 2
    $attempt++

    try {
        $response = Invoke-WebRequest -Uri "http://apexflow.aetherlink.local/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $healthy = $true
        }
    }
    catch {
        # Ignore errors, keep trying
    }

    if ($attempt % 5 -eq 0) {
        Write-Host "   ⏳ Still waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    }
}

if ($healthy) {
    Write-Host "   ✅ ApexFlow is healthy!" -ForegroundColor Green
}
else {
    Write-Host "   ⚠️  Health check timeout - check logs manually" -ForegroundColor Yellow
}

# === Step 5: Smoke Tests ===
Write-Host "`n🧪 Step 5: Running smoke tests..." -ForegroundColor Yellow

# Test 1: Health check
Write-Host "   Test 1: Health check..." -ForegroundColor Gray
try {
    $health = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/healthz" -Method Get
    Write-Host "      ✅ Health: $health" -ForegroundColor Green
}
catch {
    Write-Host "      ❌ Health check failed: $_" -ForegroundColor Red
}

# Test 2: Readiness check
Write-Host "   Test 2: Readiness check..." -ForegroundColor Gray
try {
    $ready = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/readyz" -Method Get
    Write-Host "      ✅ Ready: $ready" -ForegroundColor Green
}
catch {
    Write-Host "      ❌ Readiness check failed: $_" -ForegroundColor Red
}

# Test 3: Create a lead
Write-Host "   Test 3: Creating test lead..." -ForegroundColor Gray
try {
    $leadPayload = @{
        name   = "John Roof"
        source = "Inbound"
        phone  = "763-280-1272"
        email  = "john@roofing.com"
    } | ConvertTo-Json

    $lead = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
        -Method Post `
        -ContentType "application/json" `
        -Headers @{"x-tenant-id" = "acme" } `
        -Body $leadPayload

    Write-Host "      ✅ Lead created: ID $($lead.lead.id)" -ForegroundColor Green
}
catch {
    Write-Host "      ❌ Lead creation failed: $_" -ForegroundColor Red
}

# Test 4: List leads
Write-Host "   Test 4: Listing leads..." -ForegroundColor Gray
try {
    $leads = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
        -Method Get `
        -Headers @{"x-tenant-id" = "acme" }

    Write-Host "      ✅ Found $($leads.Count) lead(s)" -ForegroundColor Green
}
catch {
    Write-Host "      ❌ Lead listing failed: $_" -ForegroundColor Red
}

# Test 5: Metrics endpoint
Write-Host "   Test 5: Checking metrics..." -ForegroundColor Gray
try {
    $metrics = Invoke-WebRequest -Uri "http://apexflow.aetherlink.local/metrics" -UseBasicParsing
    if ($metrics.Content -match "apexflow_requests_total") {
        Write-Host "      ✅ Metrics endpoint working" -ForegroundColor Green
    }
    else {
        Write-Host "      ⚠️  Metrics format unexpected" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "      ❌ Metrics check failed: $_" -ForegroundColor Red
}

# === Summary ===
Write-Host "`n✅ ApexFlow CRM v1 Deployment Complete!" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Cyan

Write-Host "🌐 Service URLs:" -ForegroundColor Cyan
Write-Host "   API: http://apexflow.aetherlink.local" -ForegroundColor White
Write-Host "   Docs: http://apexflow.aetherlink.local/docs" -ForegroundColor White
Write-Host "   Metrics: http://apexflow.aetherlink.local/metrics" -ForegroundColor White

Write-Host "`n📊 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Restart Prometheus to scrape ApexFlow metrics:" -ForegroundColor White
Write-Host "      cd $ROOT\monitoring" -ForegroundColor Gray
Write-Host "      docker compose restart prometheus" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Check logs:" -ForegroundColor White
Write-Host "      docker logs -f aether-apexflow" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Create a job or appointment:" -ForegroundColor White
Write-Host "      See infra/core/APEXFLOW_EXAMPLES.md" -ForegroundColor Gray

Write-Host "`n🎉 Your CRM is live!" -ForegroundColor Green
