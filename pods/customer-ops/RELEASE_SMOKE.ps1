# RELEASE_SMOKE.ps1
# One-liner smoke test for AetherLink deployment verification
# Tests: health, ingestion, search, admin dashboard, and audit log integrity

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "🔥 AetherLink Release Smoke Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"
$passed = 0
$failed = 0

# Headers
$h_viewer = @{'x-api-key' = 'test-key'; 'x-role' = 'viewer' }
$h_editor = @{'x-api-key' = 'test-key'; 'x-role' = 'editor'; 'Content-Type' = 'application/json' }
$h_admin = @{'x-api-key' = 'test-key'; 'x-admin-key' = 'admin-secret-123' }

# Test 1: Health Check
Write-Host "1️⃣  Testing /health endpoint..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod "http://localhost:8000/health" -UseBasicParsing
    if ($health.ok -eq $true) {
        Write-Host "   ✅ Health OK - Uptime: $($health.uptime_human)" -ForegroundColor Green
        Write-Host "      DB: $($health.db) | Redis: $($health.redis)" -ForegroundColor Gray
        $passed++
    }
    else {
        Write-Host "   ❌ Health check failed" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ❌ Health endpoint error: $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Test 2: Async Text Ingestion
Write-Host "`n2️⃣  Testing async text ingestion..." -ForegroundColor Yellow
try {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $body = @{
        text   = "Release smoke test document created at $timestamp"
        source = "smoke_$timestamp"
    } | ConvertTo-Json

    $job = Invoke-RestMethod "http://localhost:8000/knowledge/ingest-text-async" -Method POST -Headers $h_editor -Body $body -UseBasicParsing
    if ($job.job_id) {
        Write-Host "   ✅ Ingestion job queued: $($job.job_id)" -ForegroundColor Green
        $passed++
    }
    else {
        Write-Host "   ❌ No job ID returned" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ❌ Ingestion error: $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Wait for ingestion to complete
Write-Host "   ⏳ Waiting 3 seconds for ingestion..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# Test 3: Semantic Search
Write-Host "`n3️⃣  Testing semantic search..." -ForegroundColor Yellow
try {
    $searchUrl = "http://localhost:8000/search?q=smoke test document`&k=3"
    $search = Invoke-RestMethod $searchUrl -Headers $h_viewer -UseBasicParsing
    if ($search.ok -eq $true -and $search.count -gt 0) {
        Write-Host "   ✅ Search returned $($search.count) results" -ForegroundColor Green
        if ($search.results[0].score) {
            Write-Host "      Top score: $($search.results[0].score)" -ForegroundColor Gray
        }
        $passed++
    }
    else {
        Write-Host "   ❌ Search returned no results" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ❌ Search error: $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Test 4: Admin Dashboard
Write-Host "`n4️⃣  Testing admin dashboard..." -ForegroundColor Yellow
try {
    $admin = Invoke-RestMethod "http://localhost:8000/admin/overview?limit=3" -Headers $h_admin -UseBasicParsing
    if ($admin.ok -eq $true -and $admin.count -gt 0) {
        Write-Host "   ✅ Admin dashboard OK - $($admin.count) documents tracked" -ForegroundColor Green
        $passed++
    }
    else {
        Write-Host "   ❌ Admin dashboard returned no data" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ❌ Admin error: $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Test 5: Audit Log Integrity
Write-Host "`n5️⃣  Testing audit log integrity..." -ForegroundColor Yellow
try {
    $audit = docker exec aether-customer-ops python pods/customer_ops/audit_verify.py 2>$null
    if ($LASTEXITCODE -eq 0 -and $audit -match "Status: VALID") {
        $entries = $audit | Select-String "Total Entries: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
        Write-Host "   ✅ Audit log valid - $entries entries verified" -ForegroundColor Green
        $passed++
    }
    else {
        Write-Host "   ❌ Audit log verification failed" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ❌ Audit verify error: $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Test 6: Container Health
Write-Host "`n6️⃣  Testing container health..." -ForegroundColor Yellow
try {
    $containers = docker compose ps --format json | ConvertFrom-Json
    $healthy_count = 0
    $total_count = 0

    foreach ($container in $containers) {
        $total_count++
        if ($container.Health -eq "healthy") {
            $healthy_count++
        }
    }

    if ($healthy_count -eq $total_count) {
        Write-Host "   ✅ All $total_count containers healthy" -ForegroundColor Green
        $passed++
    }
    else {
        Write-Host "   ❌ Only $healthy_count/$total_count containers healthy" -ForegroundColor Red
        $failed++
    }
}
catch {
    Write-Host "   ⚠️  Could not check container health (docker compose may not be running)" -ForegroundColor Yellow
    $failed++
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📊 Smoke Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Passed: $passed" -ForegroundColor Green
Write-Host "❌ Failed: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })

if ($failed -eq 0) {
    Write-Host "`n🎉 All tests passed! Release is ready.`n" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`n⚠️  Some tests failed. Review before deploying.`n" -ForegroundColor Yellow
    exit 1
}
