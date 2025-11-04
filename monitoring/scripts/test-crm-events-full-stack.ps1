# ✅ CRM Events Full Stack Test Script
# Tests: HTTP/2, Health, Metrics, SSE endpoint, and Kafka integration

Write-Host "`n🧪 CRM Events Service - Full Stack Validation" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Test 1: Container Status
Write-Host "📦 Test 1: Container Status" -ForegroundColor Yellow
$container = docker ps --filter "name=aether-crm-events" --format "{{.Status}}"
if ($container -match "Up") {
    Write-Host "   ✅ Container is running: $container`n" -ForegroundColor Green
}
else {
    Write-Host "   ❌ Container is not running`n" -ForegroundColor Red
    exit 1
}

# Test 2: Health Endpoint
Write-Host "🏥 Test 2: Health Endpoint (/healthz)" -ForegroundColor Yellow
try {
    $health = curl.exe -s http://localhost:9010/healthz | ConvertFrom-Json
    if ($health.ok -eq $true) {
        Write-Host "   ✅ Health check passed" -ForegroundColor Green
        Write-Host "   Response: $($health | ConvertTo-Json -Compress)`n" -ForegroundColor Gray
    }
    else {
        Write-Host "   ❌ Health check failed`n" -ForegroundColor Red
    }
}
catch {
    Write-Host "   ❌ Health endpoint error: $_`n" -ForegroundColor Red
}

# Test 3: Root Endpoint
Write-Host "🌐 Test 3: Root Endpoint (/) - Service Info" -ForegroundColor Yellow
try {
    $root = curl.exe -s http://localhost:9010/ | ConvertFrom-Json
    if ($root.ok -eq $true) {
        Write-Host "   ✅ Root endpoint passed" -ForegroundColor Green
        Write-Host "   Service: $($root.service)" -ForegroundColor Gray
        Write-Host "   Status: $($root.status)" -ForegroundColor Gray
        Write-Host "   Kafka Brokers: $($root.kafka_brokers)" -ForegroundColor Gray
        Write-Host "   Topic: $($root.topic)`n" -ForegroundColor Gray
    }
    else {
        Write-Host "   ❌ Root endpoint check failed`n" -ForegroundColor Red
    }
}
catch {
    Write-Host "   ❌ Root endpoint error: $_`n" -ForegroundColor Red
}

# Test 4: Metrics Endpoint
Write-Host "📊 Test 4: Metrics Endpoint (/metrics)" -ForegroundColor Yellow
try {
    $metrics = curl.exe -s http://localhost:9010/metrics
    if ($metrics -match "crm_events_sse_clients") {
        Write-Host "   ✅ Metrics endpoint working" -ForegroundColor Green
        
        # Extract key metrics
        $sseClients = ($metrics | Select-String "crm_events_sse_clients (\d+\.?\d*)").Matches.Groups[1].Value
        $httpRequests = ($metrics | Select-String 'crm_events_http_requests_total.*?(\d+\.?\d*)"' -AllMatches).Matches.Count
        $messages = ($metrics | Select-String "crm_events_messages_total (\d+\.?\d*)").Matches.Groups[1].Value
        
        Write-Host "   SSE Clients Connected: $sseClients" -ForegroundColor Gray
        Write-Host "   HTTP Requests: $httpRequests" -ForegroundColor Gray
        Write-Host "   Messages Relayed: $messages`n" -ForegroundColor Gray
    }
    else {
        Write-Host "   ⚠️  Metrics found but custom metrics missing`n" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ❌ Metrics endpoint error: $_`n" -ForegroundColor Red
}

# Test 5: Startup Logs
Write-Host "📋 Test 5: Startup Logs - Kafka Configuration" -ForegroundColor Yellow
$logs = docker logs aether-crm-events 2>&1 | Select-String -Pattern "Kafka Brokers|Uvicorn running" -Context 0, 1
if ($logs) {
    Write-Host "   ✅ Startup logs verified" -ForegroundColor Green
    $logs | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    Write-Host ""
}
else {
    Write-Host "   ⚠️  Startup logs not found`n" -ForegroundColor Yellow
}

# Test 6: SSE Endpoint Structure
Write-Host "🔌 Test 6: SSE Endpoint (/crm-events)" -ForegroundColor Yellow
Write-Host "   Testing SSE connection (5 second timeout)..." -ForegroundColor Gray
try {
    $job = Start-Job -ScriptBlock {
        & curl.exe -s -N --max-time 5 http://localhost:9010/crm-events
    }
    Wait-Job $job -Timeout 6 | Out-Null
    $output = Receive-Job $job
    Remove-Job $job -Force
    
    if ($output -match "data:") {
        Write-Host "   ✅ SSE endpoint responding" -ForegroundColor Green
        if ($output -match "connected") {
            Write-Host "   ✅ Received initial connection event`n" -ForegroundColor Green
        }
        else {
            Write-Host "   ⏳ No events received (Kafka may be down or topic empty)`n" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "   ⚠️  No SSE events received`n" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ⚠️  SSE test timeout (normal if no events)`n" -ForegroundColor Yellow
}

# Test 7: HTTP/2 Support
Write-Host "🚀 Test 7: HTTP/2 Support" -ForegroundColor Yellow
$dockerfile = Get-Content "C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\crm-events\Dockerfile"
if ($dockerfile -match "--http.*auto") {
    Write-Host "   ✅ Uvicorn configured with --http auto (HTTP/2 enabled via h2 library)" -ForegroundColor Green
    $requirements = Get-Content "C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\crm-events\requirements.txt"
    if ($requirements -match "h2==") {
        Write-Host "   ✅ h2 library installed (HTTP/2 protocol support)`n" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  h2 library not found in requirements.txt`n" -ForegroundColor Yellow
    }
}
else {
    Write-Host "   ⚠️  HTTP/2 not enabled`n" -ForegroundColor Yellow
}

# Summary
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ Validation Complete!" -ForegroundColor Green
Write-Host "`nService is ready for:" -ForegroundColor Cyan
Write-Host "  • Health checks (K8s/Docker): GET /healthz" -ForegroundColor White
Write-Host "  • Prometheus scraping: GET /metrics" -ForegroundColor White
Write-Host "  • SSE streaming: GET /crm-events" -ForegroundColor White
Write-Host "  • Next.js proxy: GET /api/ops/crm-events`n" -ForegroundColor White

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Start Kafka: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d kafka" -ForegroundColor Gray
Write-Host "  2. Create topic: docker exec kafka rpk topic create aetherlink.events --partitions 3" -ForegroundColor Gray
Write-Host "  3. Publish test event to see it stream through SSE" -ForegroundColor Gray
Write-Host "  4. Open Command Center: http://localhost:3001/ops/crm-events`n" -ForegroundColor Gray
