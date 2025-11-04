# Aetherlink Ship Pack - Simple Deployment Script
# Grafana Dashboard, Kafka Consumer, EF Core Migrations

Write-Host "🚀 Aetherlink Ship Pack Deployment" -ForegroundColor Cyan
Write-Host ("=" * 60)

# Navigate to repo root
$RepoRoot = "C:\Users\jonmi\OneDrive\Documents\AetherLink"
Set-Location $RepoRoot

# ============================================================================
# 1. Create Kafka Topic
# ============================================================================
Write-Host "`n📨 Creating Kafka topic: aetherlink.events" -ForegroundColor Yellow

try {
    docker exec kafka rpk topic create aetherlink.events --partitions 3 --replicas 1 2>&1 | Out-Null
    $topics = docker exec kafka rpk topic list 2>&1
    if ($topics -match "aetherlink.events") {
        Write-Host "   ✅ Topic created successfully" -ForegroundColor Green
        docker exec kafka rpk topic describe aetherlink.events | Select-Object -First 5
    }
    else {
        Write-Host "   ⚠️  Topic may already exist" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ❌ Failed to create topic: $_" -ForegroundColor Red
}

# ============================================================================
# 2. Build and Start CRM Events Service
# ============================================================================
Write-Host "`n🔧 Building and starting crm-events service" -ForegroundColor Yellow

Set-Location (Join-Path $RepoRoot "monitoring")

try {
    Write-Host "   Building crm-events container..." -ForegroundColor Gray
    docker compose build crm-events 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Build successful" -ForegroundColor Green

        Write-Host "   Starting crm-events service..." -ForegroundColor Gray
        docker compose up -d crm-events 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Service started" -ForegroundColor Green
            Start-Sleep -Seconds 3

            try {
                $health = Invoke-RestMethod 'http://localhost:9010/' -ErrorAction Stop
                Write-Host "   ✅ Health check passed" -ForegroundColor Green
                Write-Host "      Status: $($health.status)" -ForegroundColor Gray
            }
            catch {
                Write-Host "   ⚠️  Health check failed. Service may still be starting." -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "   ❌ Failed to start service" -ForegroundColor Red
        }
    }
    else {
        Write-Host "   ❌ Build failed" -ForegroundColor Red
    }
}
catch {
    Write-Host "   ❌ Error: $_" -ForegroundColor Red
}

Set-Location $RepoRoot

# ============================================================================
# Summary
# ============================================================================
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "✅ Ship Pack Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Manual Steps:" -ForegroundColor Cyan
Write-Host "1. Import Grafana dashboard:" -ForegroundColor White
Write-Host "   - Open http://localhost:3000" -ForegroundColor Gray
Write-Host "   - Dashboards → Import" -ForegroundColor Gray
Write-Host "   - Upload: monitoring\grafana\dashboards\autoheal_oidc_error_budget.json" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Apply EF Core migration (if needed):" -ForegroundColor White
Write-Host "   cd peakpro" -ForegroundColor Gray
Write-Host "   dotnet ef database update" -ForegroundColor Gray
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  CRM Events:  http://localhost:9010" -ForegroundColor Gray
Write-Host "  Grafana:     http://localhost:3000" -ForegroundColor Gray
Write-Host "  Prometheus:  http://localhost:9090" -ForegroundColor Gray
Write-Host "  Command Ctr: http://localhost:3001/ops/crm-events" -ForegroundColor Gray
Write-Host ""
