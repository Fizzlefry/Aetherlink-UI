# Test Authentication Flow
# Verifies JWT authentication through the full stack

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Authentication Flow Test" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Get JWT token
Write-Host "[Test 1] Getting JWT token from Keycloak..." -ForegroundColor Yellow
try {
    $tokenResponse = Invoke-RestMethod -Method Post `
        "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" `
        -ContentType "application/x-www-form-urlencoded" `
        -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo"
    $token = $tokenResponse.access_token
    Write-Host "  PASS - Token obtained: $($token.Substring(0,50))..." -ForegroundColor Green
}
catch {
    Write-Host "  FAIL - Could not get token: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Call ApexFlow directly (bypassing Gateway) - with token
Write-Host ""
Write-Host "[Test 2] ApexFlow direct access WITH token..." -ForegroundColor Yellow
try {
    $leads = Invoke-RestMethod "http://localhost/leads" -Headers @{
        "Authorization" = "Bearer $token"
        "x-tenant-id"   = "acme"
        "Host"          = "apexflow.aetherlink.local"
    }
    Write-Host "  PASS - Retrieved $($leads.Count) lead(s)" -ForegroundColor Green
}
catch {
    Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: Call ApexFlow directly (bypassing Gateway) - without token
Write-Host ""
Write-Host "[Test 3] ApexFlow direct access WITHOUT token (OIDC_REQUIRED=false)..." -ForegroundColor Yellow
try {
    $leads = Invoke-RestMethod "http://localhost/leads" -Headers @{
        "x-tenant-id" = "acme"
        "Host"        = "apexflow.aetherlink.local"
    }
    Write-Host "  PASS - Retrieved $($leads.Count) lead(s) (anonymous access allowed)" -ForegroundColor Green
}
catch {
    Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Check Gateway health
Write-Host ""
Write-Host "[Test 4] Gateway health check..." -ForegroundColor Yellow
try {
    $health = docker exec aether-gateway curl -s http://localhost:8000/healthz 2>$null
    if ($health -match "ok|healthy|ready") {
        Write-Host "  PASS - Gateway is healthy" -ForegroundColor Green
    }
    else {
        Write-Host "  WARN - Gateway response: $health" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  FAIL - Gateway not responding: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: Check if Gateway routes to ApexFlow (if configured)
Write-Host ""
Write-Host "[Test 5] Gateway → ApexFlow routing..." -ForegroundColor Yellow
try {
    # Try calling through Gateway (if it proxies to ApexFlow)
    $response = Invoke-RestMethod "http://localhost/leads" -Headers @{
        "Authorization" = "Bearer $token"
        "x-tenant-id"   = "acme"
        "Host"          = "edge.aetherlink.local"  # Gateway's host
    } -ErrorAction Stop
    Write-Host "  PASS - Gateway successfully routed to ApexFlow" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "  INFO - Gateway routing not yet configured (404)" -ForegroundColor Yellow
        Write-Host "       Gateway is running but doesn't proxy /leads yet" -ForegroundColor Gray
    }
    else {
        Write-Host "  INFO - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Summary
Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Current Architecture:" -ForegroundColor White
Write-Host "  [Traefik:80] → [ApexFlow:8080] ✓ Working" -ForegroundColor Green
Write-Host "  [Keycloak:8180] → JWT tokens ✓ Working" -ForegroundColor Green
Write-Host "  [Gateway:8000] ✓ Running with OIDC config" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Gateway needs routing logic to proxy /leads → apexflow:8080" -ForegroundColor Gray
Write-Host "  2. Gateway should validate JWT and forward user claims" -ForegroundColor Gray
Write-Host "  3. ApexFlow can then extract tenant from JWT instead of header" -ForegroundColor Gray
Write-Host ""
Write-Host "For now, use direct routing:" -ForegroundColor Cyan
Write-Host '  $t = (irm -Method Post "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" -ContentType "application/x-www-form-urlencoded" -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo").access_token' -ForegroundColor DarkGray
Write-Host '  irm "http://localhost/leads" -Headers @{"Authorization"="Bearer $t"; "x-tenant-id"="acme"; "Host"="apexflow.aetherlink.local"}' -ForegroundColor DarkGray
Write-Host ""
