# Keycloak Realm Setup Script
# Run this after Keycloak is healthy to create realm, client, and test user

$ErrorActionPreference = "Stop"

Write-Host "Keycloak Setup Script" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get admin token
Write-Host "Step 1: Getting admin token..." -ForegroundColor Yellow
$tokenResponse = Invoke-RestMethod -Method Post `
    -Uri "http://localhost:8180/realms/master/protocol/openid-connect/token" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "grant_type=password&client_id=admin-cli&username=admin&password=admin123!"
$adminToken = $tokenResponse.access_token
Write-Host "Admin token obtained" -ForegroundColor Green

# Step 2: Create aetherlink realm
Write-Host ""
Write-Host "Step 2: Creating 'aetherlink' realm..." -ForegroundColor Yellow
$realmBody = @{
    realm       = "aetherlink"
    enabled     = $true
    displayName = "Aetherlink Platform"
    loginTheme  = "keycloak"
} | ConvertTo-Json

try {
    $null = Invoke-WebRequest -Method Post `
        -Uri "http://localhost:8180/admin/realms" `
        -Headers @{
        "Authorization" = "Bearer $adminToken"
        "Content-Type"  = "application/json"
    } `
        -Body $realmBody
    Write-Host "Realm 'aetherlink' created" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode -eq 409) {
        Write-Host "Realm already exists" -ForegroundColor Yellow
    }
    else {
        throw
    }
}

# Step 3: Create aetherlink-gateway client
Write-Host ""
Write-Host "Step 3: Creating 'aetherlink-gateway' client..." -ForegroundColor Yellow
$clientBody = @{
    clientId                  = "aetherlink-gateway"
    enabled                   = $true
    publicClient              = $true
    directAccessGrantsEnabled = $true
    standardFlowEnabled       = $true
    implicitFlowEnabled       = $false
    serviceAccountsEnabled    = $false
    redirectUris              = @("http://localhost/*", "http://*.aetherlink.local/*")
    webOrigins                = @("*")
    protocol                  = "openid-connect"
} | ConvertTo-Json

try {
    $null = Invoke-WebRequest -Method Post `
        -Uri "http://localhost:8180/admin/realms/aetherlink/clients" `
        -Headers @{
        "Authorization" = "Bearer $adminToken"
        "Content-Type"  = "application/json"
    } `
        -Body $clientBody
    Write-Host "Client 'aetherlink-gateway' created" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode -eq 409) {
        Write-Host "Client already exists" -ForegroundColor Yellow
    }
    else {
        throw
    }
}

# Step 4: Create demo user
Write-Host ""
Write-Host "Step 4: Creating 'demo' user..." -ForegroundColor Yellow
$userBody = @{
    username      = "demo"
    enabled       = $true
    emailVerified = $true
    email         = "demo@aetherlink.local"
    firstName     = "Demo"
    lastName      = "User"
    credentials   = @(
        @{
            type      = "password"
            value     = "demo"
            temporary = $false
        }
    )
} | ConvertTo-Json -Depth 3

try {
    $null = Invoke-WebRequest -Method Post `
        -Uri "http://localhost:8180/admin/realms/aetherlink/users" `
        -Headers @{
        "Authorization" = "Bearer $adminToken"
        "Content-Type"  = "application/json"
    } `
        -Body $userBody
    Write-Host "User 'demo' created (password: demo)" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode -eq 409) {
        Write-Host "User already exists" -ForegroundColor Yellow
    }
    else {
        throw
    }
}

# Step 5: Test token retrieval
Write-Host ""
Write-Host "Step 5: Testing token retrieval..." -ForegroundColor Yellow
try {
    $body = "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo"
    $testToken = (Invoke-RestMethod -Method Post `
            -Uri "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" `
            -ContentType "application/x-www-form-urlencoded" `
            -Body $body).access_token

    Write-Host "Token obtained for user 'demo'" -ForegroundColor Green
    Write-Host ""
    Write-Host "Keycloak setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Quick Reference:" -ForegroundColor Cyan
    Write-Host "  Realm: aetherlink" -ForegroundColor White
    Write-Host "  Client: aetherlink-gateway" -ForegroundColor White
    Write-Host "  User: demo / demo" -ForegroundColor White
    Write-Host "  Admin Console: http://localhost:8180" -ForegroundColor White
    Write-Host ""
    Write-Host "To test ApexFlow with JWT authentication:" -ForegroundColor Cyan
    Write-Host '  $t = (irm -Method Post "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" -ContentType "application/x-www-form-urlencoded" -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo").access_token' -ForegroundColor DarkGray
    Write-Host '  irm "http://localhost/leads" -Headers @{"Authorization"="Bearer $t"; "x-tenant-id"="acme"; "Host"="apexflow.aetherlink.local"}' -ForegroundColor DarkGray

}
catch {
    Write-Host "Token test failed: $($_.Exception.Message)" -ForegroundColor Red
    throw
}
