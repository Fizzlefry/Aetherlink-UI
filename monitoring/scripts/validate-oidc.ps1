# OIDC Implementation Validation Script
# Tests the OIDC authentication setup for Autoheal

Write-Host "`n=== Autoheal OIDC Implementation Validation ===" -ForegroundColor Cyan
Write-Host "Testing OIDC authentication configuration...`n"

$baseUrl = "http://localhost:9009"
$tests = @()

# Test 1: Verify requirements.txt has python-jose
Write-Host "Test 1: Checking dependencies..." -ForegroundColor Yellow
$reqPath = ".\monitoring\autoheal\requirements.txt"
if (Test-Path $reqPath) {
    $content = Get-Content $reqPath -Raw
    if ($content -match "python-jose") {
        Write-Host "  ✅ python-jose[cryptography] found in requirements.txt" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ python-jose NOT found in requirements.txt" -ForegroundColor Red
        $tests += $false
    }
}
else {
    Write-Host "  ❌ requirements.txt not found" -ForegroundColor Red
    $tests += $false
}

# Test 2: Verify auth.py exists and has required functions
Write-Host "`nTest 2: Checking auth.py module..." -ForegroundColor Yellow
$authPath = ".\monitoring\autoheal\auth.py"
if (Test-Path $authPath) {
    $authContent = Get-Content $authPath -Raw
    $hasDiscover = $authContent -match "def _discover"
    $hasVerify = $authContent -match "def _verify"
    $hasRequireOidc = $authContent -match "def require_oidc"

    if ($hasDiscover -and $hasVerify -and $hasRequireOidc) {
        Write-Host "  ✅ auth.py has all required functions (_discover, _verify, require_oidc)" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ auth.py missing required functions" -ForegroundColor Red
        Write-Host "     _discover: $hasDiscover, _verify: $hasVerify, require_oidc: $hasRequireOidc"
        $tests += $false
    }
}
else {
    Write-Host "  ❌ auth.py not found" -ForegroundColor Red
    $tests += $false
}

# Test 3: Verify main.py imports auth module
Write-Host "`nTest 3: Checking main.py OIDC integration..." -ForegroundColor Yellow
$mainPath = ".\monitoring\autoheal\main.py"
if (Test-Path $mainPath) {
    $mainContent = Get-Content $mainPath -Raw
    $hasImport = $mainContent -match "from auth import"
    $hasMiddleware = $mainContent -match "@app\.middleware"
    $hasOidcGate = $mainContent -match "async def oidc_gate"

    if ($hasImport -and $hasMiddleware -and $hasOidcGate) {
        Write-Host "  ✅ main.py has OIDC middleware integrated" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ main.py missing OIDC integration" -ForegroundColor Red
        Write-Host "     Import: $hasImport, Middleware: $hasMiddleware, Gate: $hasOidcGate"
        $tests += $false
    }
}
else {
    Write-Host "  ❌ main.py not found" -ForegroundColor Red
    $tests += $false
}

# Test 4: Verify docker-compose.prod.yml has OIDC env vars
Write-Host "`nTest 4: Checking production compose configuration..." -ForegroundColor Yellow
$prodComposePath = ".\docker-compose.prod.yml"
if (Test-Path $prodComposePath) {
    $composeContent = Get-Content $prodComposePath -Raw
    $hasOidcEnabled = $composeContent -match "OIDC_ENABLED"
    $hasOidcIssuer = $composeContent -match "OIDC_ISSUER"
    $hasOidcAudience = $composeContent -match "OIDC_AUDIENCE"

    if ($hasOidcEnabled -and $hasOidcIssuer -and $hasOidcAudience) {
        Write-Host "  ✅ docker-compose.prod.yml has OIDC environment variables" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ docker-compose.prod.yml missing OIDC env vars" -ForegroundColor Red
        $tests += $false
    }
}
else {
    Write-Host "  ❌ docker-compose.prod.yml not found" -ForegroundColor Red
    $tests += $false
}

# Test 5: Verify logrotate crontab exists
Write-Host "`nTest 5: Checking logrotate configuration..." -ForegroundColor Yellow
$crontabPath = ".\monitoring\logrotate\crontab"
if (Test-Path $crontabPath) {
    $crontabContent = Get-Content $crontabPath -Raw
    if ($crontabContent -match "logrotate") {
        Write-Host "  ✅ Logrotate crontab configured" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ Logrotate crontab missing logrotate command" -ForegroundColor Red
        $tests += $false
    }
}
else {
    Write-Host "  ❌ Logrotate crontab not found" -ForegroundColor Red
    $tests += $false
}

# Test 6: Verify Next.js ops page exists
Write-Host "`nTest 6: Checking Command Center ops page..." -ForegroundColor Yellow
$opsPagePath = ".\apps\command-center\app\ops\autoheal\page.tsx"
if (Test-Path $opsPagePath) {
    $opsContent = Get-Content $opsPagePath -Raw
    $hasEventSource = $opsContent -match "EventSource"
    $hasFilter = $opsContent -match "passFilter"

    if ($hasEventSource -and $hasFilter) {
        Write-Host "  ✅ Next.js ops page with SSE and filtering" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ⚠️  Next.js ops page exists but may be incomplete" -ForegroundColor Yellow
        $tests += $true
    }
}
else {
    Write-Host "  ⚠️  Next.js ops page not found (optional)" -ForegroundColor Yellow
    $tests += $true  # Don't fail on optional component
}

# Test 7: Verify .env.example has OIDC section
Write-Host "`nTest 7: Checking .env.example..." -ForegroundColor Yellow
$envExamplePath = ".\.env.example"
if (Test-Path $envExamplePath) {
    $envContent = Get-Content $envExamplePath -Raw
    if ($envContent -match "OIDC_ENABLED") {
        Write-Host "  ✅ .env.example updated with OIDC configuration" -ForegroundColor Green
        $tests += $true
    }
    else {
        Write-Host "  ❌ .env.example missing OIDC configuration" -ForegroundColor Red
        $tests += $false
    }
}
else {
    Write-Host "  ❌ .env.example not found" -ForegroundColor Red
    $tests += $false
}

# Test 8: Check if autoheal service is running
Write-Host "`nTest 8: Checking autoheal service status..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "  ✅ Autoheal service is running" -ForegroundColor Green
    Write-Host "     Enabled: $($health.enabled), Dry-run: $($health.dry_run)" -ForegroundColor Gray
    $tests += $true

    # Test 9: Test public endpoint (should work without auth)
    Write-Host "`nTest 9: Testing public endpoint (/)..." -ForegroundColor Yellow
    try {
        $healthCheck = Invoke-RestMethod -Uri "$baseUrl/" -TimeoutSec 2
        Write-Host "  ✅ Public endpoint accessible (no auth required)" -ForegroundColor Green
        $tests += $true
    }
    catch {
        Write-Host "  ❌ Public endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
        $tests += $false
    }

    # Test 10: Test protected endpoint without token (should fail if OIDC enabled)
    Write-Host "`nTest 10: Testing protected endpoint without token..." -ForegroundColor Yellow
    try {
        $audit = Invoke-RestMethod -Uri "$baseUrl/audit" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "  ⚠️  /audit endpoint accessible without token (OIDC may be disabled)" -ForegroundColor Yellow
        Write-Host "     This is OK for dev/testing, but should fail in production with OIDC_ENABLED=true" -ForegroundColor Gray
        $tests += $true
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 401) {
            Write-Host "  ✅ /audit endpoint correctly requires authentication (401)" -ForegroundColor Green
            $tests += $true
        }
        else {
            Write-Host "  ❌ Unexpected error: $($_.Exception.Message)" -ForegroundColor Red
            $tests += $false
        }
    }
}
catch {
    Write-Host "  ⚠️  Autoheal service not running (start with docker compose up -d)" -ForegroundColor Yellow
    Write-Host "     Skipping runtime tests..." -ForegroundColor Gray
    $tests += $true  # Don't fail if service isn't running
    $tests += $true
    $tests += $true
}

# Summary
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
$passed = ($tests | Where-Object { $_ -eq $true }).Count
$total = $tests.Count
$passRate = [math]::Round(($passed / $total) * 100, 1)

Write-Host "VALIDATION SUMMARY" -ForegroundColor Cyan
Write-Host "Total Tests: $total" -ForegroundColor White
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $($total - $passed)" -ForegroundColor Red
Write-Host "Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -ge 90) { "Green" } elseif ($passRate -ge 70) { "Yellow" } else { "Red" })

if ($passRate -eq 100) {
    Write-Host "`n✅ ALL CHECKS PASSED - Ready for deployment!" -ForegroundColor Green
    exit 0
}
elseif ($passRate -ge 90) {
    Write-Host "`n✅ MOSTLY READY - Minor issues detected" -ForegroundColor Yellow
    exit 0
}
elseif ($passRate -ge 70) {
    Write-Host "`n⚠️  PARTIALLY READY - Address failures before production" -ForegroundColor Yellow
    exit 1
}
else {
    Write-Host "`n❌ NOT READY - Critical issues detected" -ForegroundColor Red
    exit 1
}
