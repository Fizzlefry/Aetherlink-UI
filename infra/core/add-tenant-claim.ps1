# Add tenant_id claim to Keycloak tokens
# This makes the JWT include tenant_id so Gateway can extract it

$ErrorActionPreference = "Stop"

Write-Host "Adding tenant_id claim mapper to Keycloak..." -ForegroundColor Cyan
Write-Host ""

# Get admin token
Write-Host "Step 1: Getting admin token..." -ForegroundColor Yellow
$adminToken = (Invoke-RestMethod -Method Post `
        "http://localhost:8180/realms/master/protocol/openid-connect/token" `
        -ContentType "application/x-www-form-urlencoded" `
        -Body "grant_type=password&client_id=admin-cli&username=admin&password=admin123!").access_token
Write-Host "Admin token obtained" -ForegroundColor Green

# Get client internal ID
Write-Host ""
Write-Host "Step 2: Getting client ID..." -ForegroundColor Yellow
$clients = Invoke-RestMethod -Method Get `
    "http://localhost:8180/admin/realms/aetherlink/clients?clientId=aetherlink-gateway" `
    -Headers @{"Authorization" = "Bearer $adminToken" }
$clientUuid = $clients[0].id
Write-Host "Client UUID: $clientUuid" -ForegroundColor Green

# Create protocol mapper for tenant_id
Write-Host ""
Write-Host "Step 3: Creating tenant_id protocol mapper..." -ForegroundColor Yellow
$mapperBody = @{
    name            = "tenant-id-mapper"
    protocol        = "openid-connect"
    protocolMapper  = "oidc-hardcoded-claim-mapper"
    consentRequired = $false
    config          = @{
        "claim.name"           = "tenant_id"
        "claim.value"          = "acme"
        "jsonType.label"       = "String"
        "id.token.claim"       = "true"
        "access.token.claim"   = "true"
        "userinfo.token.claim" = "true"
    }
} | ConvertTo-Json -Depth 3

try {
    $null = Invoke-WebRequest -Method Post `
        "http://localhost:8180/admin/realms/aetherlink/clients/$clientUuid/protocol-mappers/models" `
        -Headers @{
        "Authorization" = "Bearer $adminToken"
        "Content-Type"  = "application/json"
    } `
        -Body $mapperBody
    Write-Host "Mapper 'tenant-id-mapper' created" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode -eq 409) {
        Write-Host "Mapper already exists" -ForegroundColor Yellow
    }
    else {
        throw
    }
}

# Test token to verify claim
Write-Host ""
Write-Host "Step 4: Testing token with tenant_id claim..." -ForegroundColor Yellow
$testToken = (Invoke-RestMethod -Method Post `
        "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" `
        -ContentType "application/x-www-form-urlencoded" `
        -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo").access_token

# Decode JWT (without verification - just for display)
$parts = $testToken.Split('.')
$payload = $parts[1]
# Pad base64 string if needed
while ($payload.Length % 4 -ne 0) { $payload += "=" }
$jsonBytes = [System.Convert]::FromBase64String($payload)
$jsonString = [System.Text.Encoding]::UTF8.GetString($jsonBytes)
$claims = $jsonString | ConvertFrom-Json

Write-Host ""
Write-Host "Token claims:" -ForegroundColor Cyan
Write-Host "  sub: $($claims.sub)" -ForegroundColor White
Write-Host "  preferred_username: $($claims.preferred_username)" -ForegroundColor White
Write-Host "  tenant_id: $($claims.tenant_id)" -ForegroundColor White
Write-Host "  iss: $($claims.iss)" -ForegroundColor Gray
Write-Host ""

if ($claims.tenant_id) {
    Write-Host "SUCCESS - tenant_id claim is present in token!" -ForegroundColor Green
}
else {
    Write-Host "WARNING - tenant_id claim not found in token" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next: Gateway will extract tenant_id from JWT and inject x-tenant-id header" -ForegroundColor Cyan
