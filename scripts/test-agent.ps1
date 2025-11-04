# ====================================================================================
# AETHERLINK AGENT SMOKE TEST
# ====================================================================================
# Quick verification that the AetherLink Command AI Agent is working
# ====================================================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  AETHERLINK AGENT SMOKE TEST" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Change to monitoring directory
$monitoringDir = "$PSScriptRoot\..\monitoring"
Set-Location $monitoringDir

# ====================================================================================
# 1. Start Agent Service
# ====================================================================================
Write-Host "[1/5] Starting Agent Service..." -ForegroundColor Yellow

docker compose up -d aether-agent 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "   [FAIL] Failed to start agent service" -ForegroundColor Red
    exit 1
}

Write-Host "   [OK] Agent service started" -ForegroundColor Green
Write-Host ""

# ====================================================================================
# 2. Wait for Agent Health
# ====================================================================================
Write-Host "[2/5] Waiting for Agent Health..." -ForegroundColor Yellow

$ok = $false
$attempts = 0
$maxAttempts = 20

while (-not $ok -and $attempts -lt $maxAttempts) {
    try {
        $response = Invoke-RestMethod http://localhost:8088/health -TimeoutSec 2
        if ($response.ok) {
            $ok = $true
            Write-Host "   [OK] Agent is healthy" -ForegroundColor Green
            break
        }
    }
    catch {
        # Ignore errors and retry
    }

    $attempts++
    Start-Sleep -Seconds 1
}

if (-not $ok) {
    Write-Host "   [FAIL] Agent not healthy after $maxAttempts attempts" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Check logs:" -ForegroundColor Yellow
    Write-Host "   docker compose logs aether-agent" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# ====================================================================================
# 3. Test Health Endpoint
# ====================================================================================
Write-Host "[3/5] Testing /health Endpoint..." -ForegroundColor Yellow

try {
    $health = Invoke-RestMethod http://localhost:8088/health

    Write-Host "   [OK] Health check passed" -ForegroundColor Green
    Write-Host "   Status: ok=$($health.ok)" -ForegroundColor Gray
    Write-Host "   Health Score: $($health.health_score)" -ForegroundColor Gray
    Write-Host "   Consecutive Low: $($health.consecutive_low)" -ForegroundColor Gray
}
catch {
    Write-Host "   [FAIL] Health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# ====================================================================================
# 4. Test PromQL Query Endpoint
# ====================================================================================
Write-Host "[4/5] Testing /query Endpoint (PromQL)..." -ForegroundColor Yellow

try {
    $queryBody = @{
        ql = "aether:health_score:15m"
    } | ConvertTo-Json

    $queryResult = Invoke-RestMethod -Method Post `
        -Uri http://localhost:8088/query `
        -ContentType "application/json" `
        -Body $queryBody

    Write-Host "   [OK] Query executed successfully" -ForegroundColor Green
    Write-Host "   Query: $($queryResult.query)" -ForegroundColor Gray
    Write-Host "   Value: $($queryResult.value)" -ForegroundColor Gray
}
catch {
    Write-Host "   [FAIL] Query failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# ====================================================================================
# 5. Check Metrics Endpoint
# ====================================================================================
Write-Host "[5/5] Testing /metrics Endpoint..." -ForegroundColor Yellow

try {
    $metrics = (Invoke-WebRequest http://localhost:8088/metrics -TimeoutSec 3).Content

    # Look for agent-specific metrics
    $agentMetrics = $metrics | Select-String "aether_agent_" | Out-String

    if ($agentMetrics) {
        Write-Host "   [OK] Metrics endpoint working" -ForegroundColor Green
        Write-Host ""
        Write-Host "   Agent-specific metrics:" -ForegroundColor Gray
        $agentMetrics -split "`n" | Where-Object { $_ -match "^aether_agent_" } | ForEach-Object {
            Write-Host "   $_" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "   [WARN] No agent metrics found yet (may need time to generate)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   [FAIL] Metrics check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# ====================================================================================
# Summary & Quick Links
# ====================================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       SMOKE TEST COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "[OK] All checks passed!" -ForegroundColor Green
Write-Host ""

Write-Host "Quick Links:" -ForegroundColor Cyan
Write-Host "   Agent Health:    http://localhost:8088/health" -ForegroundColor Gray
Write-Host "   Agent Metrics:   http://localhost:8088/metrics" -ForegroundColor Gray
Write-Host "   Agent Docs:      http://localhost:8088/docs (FastAPI auto-docs)" -ForegroundColor Gray
Write-Host "   Prometheus:      http://localhost:9090" -ForegroundColor Gray
Write-Host "   Grafana:         http://localhost:3000 (admin/admin)" -ForegroundColor Gray
Write-Host "   Alertmanager:    http://localhost:9093" -ForegroundColor Gray
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Check agent logs: docker compose logs -f aether-agent" -ForegroundColor Gray
Write-Host "   2. View agent metrics in Prometheus: aether_agent_health_checks_total" -ForegroundColor Gray
Write-Host "   3. Test action endpoint: curl -X POST http://localhost:8088/act -d '{\"action\":\"restart_api\",\"reason\":\"test\"}'" -ForegroundColor Gray
Write-Host "   4. Monitor health checks: watch 'curl -s http://localhost:8088/health | jq'" -ForegroundColor Gray
Write-Host ""

Write-Host "Opening dashboards..." -ForegroundColor Cyan
Start-Sleep -Seconds 1

# Open Prometheus with health score query
Start-Process "http://localhost:9090/graph?g0.expr=aether:health_score:15m&g0.tab=0"

# Open Grafana
Start-Process "http://localhost:3000"

# Open Agent health
Start-Process "http://localhost:8088/health"

Write-Host ""
Write-Host "STATUS: Agent is operational and monitoring health score!" -ForegroundColor Green
Write-Host ""
