# Aetherlink Ship Pack - Deployment Script
# Grafana Dashboard, Kafka Consumer, EF Core Migrations

param(
    [switch]$SkipKafka,
    [switch]$SkipMigration,
    [switch]$SkipService
)

Write-Host "🚀 Aetherlink Ship Pack Deployment" -ForegroundColor Cyan
Write-Host "=" * 60

# Navigate to repo root
$RepoRoot = "C:\Users\jonmi\OneDrive\Documents\AetherLink"
Set-Location $RepoRoot

# ============================================================================
# 1. Create Kafka Topic
# ============================================================================
if (-not $SkipKafka) {
    Write-Host "`n📨 Creating Kafka topic: aetherlink.events" -ForegroundColor Yellow

    try {
        docker exec kafka rpk topic create aetherlink.events --partitions 3 --replicas 1 2>&1 | Out-Null

        # Verify topic creation
        $topics = docker exec kafka rpk topic list 2>&1
        if ($topics -match "aetherlink.events") {
            Write-Host "   ✅ Topic created successfully" -ForegroundColor Green

            # Show topic details
            Write-Host "   Topic details:" -ForegroundColor Gray
            docker exec kafka rpk topic describe aetherlink.events | Select-Object -First 5
        }
        else {
            Write-Host "   ⚠️  Topic may already exist or creation failed" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "   ❌ Failed to create topic: $_" -ForegroundColor Red
        Write-Host "   Make sure Kafka is running: docker ps | grep kafka" -ForegroundColor Gray
    }
}

# ============================================================================
# 2. Apply EF Core Migration
# ============================================================================
if (-not $SkipMigration) {
    Write-Host "`n🗄️  Applying EF Core migrations (Outbox + Idempotency)" -ForegroundColor Yellow

    $PeakProPath = Join-Path $RepoRoot "peakpro"

    if (Test-Path $PeakProPath) {
        Set-Location $PeakProPath

        Write-Host "   Checking for existing migrations..." -ForegroundColor Gray

        # Note: This requires .NET SDK and EF Core tools installed
        # dotnet tool install --global dotnet-ef

        try {
            # Check if migration already exists
            $migrationExists = Test-Path "Migrations\*Init_Outbox_Idempotency*"

            if ($migrationExists) {
                Write-Host "   Migration file already exists, applying to database..." -ForegroundColor Gray
                dotnet ef database update 2>&1

                if ($LASTEXITCODE -eq 0) {
                    Write-Host "   ✅ Migration applied successfully" -ForegroundColor Green
                }
                else {
                    Write-Host "   ⚠️  Migration may have failed. Check connection string." -ForegroundColor Yellow
                }
            }
            else {
                Write-Host "   ⚠️  Migration file not found in Migrations folder" -ForegroundColor Yellow
                Write-Host "   Expected: Migrations\20251102_Init_Outbox_Idempotency.cs" -ForegroundColor Gray
            }

            # Verify tables created
            Write-Host "   Verifying tables..." -ForegroundColor Gray
            $tables = docker exec postgres-crm psql -U crm -d crm -t -c "\dt" 2>&1

            if ($tables -match "outbox_events" -and $tables -match "idempotency_keys") {
                Write-Host "   ✅ Tables verified: outbox_events, idempotency_keys" -ForegroundColor Green
            }
            else {
                Write-Host "   ⚠️  Tables not found. Migration may need to run." -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "   ❌ Migration failed: $_" -ForegroundColor Red
            Write-Host "   Install EF tools: dotnet tool install --global dotnet-ef" -ForegroundColor Gray
        }

        Set-Location $RepoRoot
    }
    else {
        Write-Host "   ⚠️  PeakPro directory not found at: $PeakProPath" -ForegroundColor Yellow
    }
}

# ============================================================================
# 3. Build and Start CRM Events Service
# ============================================================================
if (-not $SkipService) {
    Write-Host "`n🔧 Building and starting crm-events service" -ForegroundColor Yellow

    Set-Location (Join-Path $RepoRoot "monitoring")

    try {
        # Build the service
        Write-Host "   Building crm-events container..." -ForegroundColor Gray
        docker compose build crm-events 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Build successful" -ForegroundColor Green

            # Start the service
            Write-Host "   Starting crm-events service..." -ForegroundColor Gray
            docker compose up -d crm-events 2>&1 | Out-Null

            if ($LASTEXITCODE -eq 0) {
                Write-Host "   ✅ Service started" -ForegroundColor Green

                # Wait for service to be ready
                Start-Sleep -Seconds 3

                # Health check
                try {
                    $health = Invoke-RestMethod 'http://localhost:9010/' -ErrorAction Stop
                    Write-Host "   ✅ Health check passed" -ForegroundColor Green
                    Write-Host "      Status: $($health.status)" -ForegroundColor Gray
                    Write-Host "      Topic: $($health.topic)" -ForegroundColor Gray
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
}

# ============================================================================
# 4. Import Grafana Dashboard (Manual Step)
# ============================================================================
Write-Host "`n📊 Grafana Dashboard (Manual Import Required)" -ForegroundColor Yellow
Write-Host "   Dashboard file: monitoring\grafana\dashboards\autoheal_oidc_error_budget.json" -ForegroundColor Gray
Write-Host "   To import:" -ForegroundColor Gray
Write-Host "   1. Open http://localhost:3000 (Grafana)" -ForegroundColor Gray
Write-Host "   2. Click Dashboards → Import" -ForegroundColor Gray
Write-Host "   3. Upload JSON file from path above" -ForegroundColor Gray
Write-Host "   4. Select Prometheus data source" -ForegroundColor Gray
Write-Host "   5. Click Import" -ForegroundColor Gray

# ============================================================================
# Summary
# ============================================================================
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "✅ Ship Pack Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Import Grafana dashboard (see above)" -ForegroundColor White
Write-Host "2. Test SSE endpoint: curl http://localhost:9010/crm-events" -ForegroundColor White
Write-Host "3. Open Command Center: http://localhost:3001/ops/crm-events" -ForegroundColor White
Write-Host "4. Trigger domain event (e.g., create a job in CRM)" -ForegroundColor White
Write-Host "5. Watch events stream to Command Center in real-time" -ForegroundColor White
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  CRM Events:  http://localhost:9010" -ForegroundColor Gray
Write-Host "  Grafana:     http://localhost:3000" -ForegroundColor Gray
Write-Host "  Prometheus:  http://localhost:9090" -ForegroundColor Gray
Write-Host "  Command Ctr: http://localhost:3001/ops/crm-events" -ForegroundColor Gray
Write-Host ""
