# CRM Events Service Validation Script

Write-Host "🧪 CRM Events Service Validation" -ForegroundColor Cyan
Write-Host ("=" * 60)

# Test 1: Check if container is running
Write-Host "`n📦 Test 1: Container Status" -ForegroundColor Yellow
$container = docker ps --filter "name=aether-crm-events" --format "{{.Status}}"
if ($container -match "Up") {
    Write-Host "   ✅ Container is running: $container" -ForegroundColor Green
}
else {
    Write-Host "   ❌ Container not running" -ForegroundColor Red
    exit 1
}

# Test 2: Check logs for startup
Write-Host "`n📋 Test 2: Startup Logs" -ForegroundColor Yellow
$logs = docker logs aether-crm-events 2>&1 | Select-String "Uvicorn running"
if ($logs) {
    Write-Host "   ✅ Service started successfully" -ForegroundColor Green
    Write-Host "   $logs" -ForegroundColor Gray
}
else {
    Write-Host "   ⚠️  Startup message not found" -ForegroundColor Yellow
}

# Test 3: Test healthz endpoint (using curl.exe to avoid PS alias)
Write-Host "`n🏥 Test 3: Health Endpoint" -ForegroundColor Yellow
try {
    $response = & curl.exe -s http://localhost:9010/healthz
    $json = $response | ConvertFrom-Json
    if ($json.ok -eq $true) {
        Write-Host "   ✅ Health check passed" -ForegroundColor Green
        Write-Host "   Response: $response" -ForegroundColor Gray
    }
    else {
        Write-Host "   ⚠️  Unexpected response" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ❌ Health check failed: $_" -ForegroundColor Red
}

# Test 4: Test root endpoint
Write-Host "`n🌐 Test 4: Root Endpoint" -ForegroundColor Yellow
try {
    $response = & curl.exe -s http://localhost:9010/
    $json = $response | ConvertFrom-Json
    if ($json.ok -eq $true) {
        Write-Host "   ✅ Root endpoint passed" -ForegroundColor Green
        Write-Host "   Service: $($json.service)" -ForegroundColor Gray
        Write-Host "   Status: $($json.status)" -ForegroundColor Gray
        Write-Host "   Kafka Brokers: $($json.kafka_brokers)" -ForegroundColor Gray
        Write-Host "   Topic: $($json.topic)" -ForegroundColor Gray
    }
    else {
        Write-Host "   ⚠️  Unexpected response" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ❌ Root endpoint failed: $_" -ForegroundColor Red
}

# Test 5: Check if Kafka topic exists
Write-Host "`n📨 Test 5: Kafka Topic" -ForegroundColor Yellow
try {
    $topics = docker exec kafka rpk topic list 2>&1
    if ($topics -match "aetherlink.events") {
        Write-Host "   ✅ Topic exists: aetherlink.events" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  Topic not found" -ForegroundColor Yellow
        Write-Host "   Create with: docker exec kafka rpk topic create aetherlink.events --partitions 3 --replicas 1" -ForegroundColor Gray
    }
}
catch {
    Write-Host "   ⚠️  Kafka not available or topic check failed" -ForegroundColor Yellow
}

# Test 6: Test SSE endpoint (just check if it responds, don't wait for events)
Write-Host "`n📡 Test 6: SSE Endpoint (Quick Check)" -ForegroundColor Yellow
Write-Host "   Testing http://localhost:9010/crm-events..." -ForegroundColor Gray
$job = Start-Job -ScriptBlock {
    & curl.exe -s -N http://localhost:9010/crm-events | Select-Object -First 1
}
$result = Wait-Job $job -Timeout 3 | Receive-Job
Remove-Job $job -Force

if ($result) {
    Write-Host "   ✅ SSE endpoint responding" -ForegroundColor Green
    Write-Host "   First event: $result" -ForegroundColor Gray
}
else {
    Write-Host "   ⚠️  No events received (may be normal if topic is empty)" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "✅ Validation Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  Health:      http://localhost:9010/healthz" -ForegroundColor Gray
Write-Host "  Root:        http://localhost:9010/" -ForegroundColor Gray
Write-Host "  SSE Stream:  http://localhost:9010/crm-events" -ForegroundColor Gray
Write-Host "  Dashboard:   http://localhost:3001/ops/crm-events" -ForegroundColor Gray
Write-Host ""
