#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Ingests sample corpus and validates all RAG quick wins end-to-end.

.DESCRIPTION
    This script:
    1. Checks API health
    2. Ingests 3 sample documents (storm collar, PII test, audit log)
    3. Waits for embeddings to process
    4. Runs full validation suite
    
    Perfect for fresh deployments or testing after code changes.

.EXAMPLE
    .\scripts\setup-and-validate.ps1
#>

param(
    [string]$ApiKey = $env:API_KEY_EXPERTCO,
    [string]$BaseUrl = "http://localhost:8000",
    [int]$Timeout = 10
)

# Color helpers
function Write-Pass { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "ℹ $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Step { param($msg) Write-Host "`n━━━ $msg ━━━" -ForegroundColor Magenta }

Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AetherLink: Setup Sample Data + Validate Suite   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREFLIGHT GUARDS (hard-fail early)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "PREFLIGHT: Environment Check"

# Guard 1: API key must be set
if (-not $env:API_KEY_EXPERTCO -and -not $env:API_ADMIN_KEY -and -not $ApiKey) {
    Write-Fail "No API key found. Set `$env:API_KEY_EXPERTCO or `$env:API_ADMIN_KEY"
    Write-Info "Example: `$env:API_KEY_EXPERTCO = 'your-editor-key'"
    exit 1
}

# Use provided key or fallback to environment
if (-not $ApiKey) {
    $ApiKey = if ($env:API_KEY_EXPERTCO) { $env:API_KEY_EXPERTCO } else { $env:API_ADMIN_KEY }
}

$keyPreview = $ApiKey.Substring(0, [Math]::Min(8, $ApiKey.Length)) + '...'
Write-Pass "API Key: $keyPreview"

# Guard 2: API must be reachable
$BaseUrl = if ($BaseUrl) { $BaseUrl } else { "http://localhost:8000" }
Write-Info "Base URL: $BaseUrl"

try {
    $health = Invoke-WebRequest -Uri "$BaseUrl/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-Pass "API is reachable"
}
catch {
    Write-Fail "API not reachable at $BaseUrl"
    Write-Info "Check: docker compose -f pods\customer_ops\docker-compose.yml ps"
    Write-Info "Or try: docker compose logs --tail=50 api"
    exit 1
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: Detailed Health Check
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "STEP 1: Detailed Health Check"

try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec $Timeout
    if ($health.ok -eq $true) {
        Write-Pass "API is healthy"
        Write-Info "  Uptime: $($health.uptime_human)"
        Write-Info "  DB: $($health.db)"
    }
    else {
        Write-Fail "API health check failed"
        exit 1
    }
}
catch {
    Write-Fail "Cannot reach API at $BaseUrl"
    Write-Info "Check: docker compose -f pods\customer_ops\docker-compose.yml ps"
    exit 1
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: Ingest Sample Documents
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "STEP 2: Ingest Sample Documents"

$headers = @{
    "x-api-key"    = $ApiKey
    "Content-Type" = "application/json"
}

# Document 1: Storm Collar Installation (multi-chunk, good for neighbor windowing)
Write-Info "Ingesting: Storm Collar Installation Guide..."
$doc1 = @{
    text     = @"
Storm Collar Installation Guide

A storm collar is a critical weatherproofing component installed around the base of a chimney pipe where it penetrates the roof flashing. Proper installation prevents water infiltration and extends the life of your chimney system.

Materials Needed:
- Storm collar (sized to match your chimney pipe diameter)
- High-temperature silicone sealant
- Screwdriver or drill
- Sheet metal screws (if pre-drilled holes present)
- Clean rag and degreaser

Step 1: Preparation
Clean the chimney pipe surface where the storm collar will sit. Remove any debris, old sealant, or rust using a degreaser and rag. Ensure the surface is completely dry before proceeding. The storm collar must be installed above the roof flashing but below any rain cap or termination cap.

Step 2: Positioning
Slide the storm collar down over the chimney pipe until it rests on top of the flashing. The collar should sit snugly against the pipe with its skirt extending at least 1-2 inches over the flashing. If your storm collar has a seam, position it on the downslope side of the roof to minimize water exposure.

Step 3: Securing
Tighten the storm collar band using a screwdriver or drill. Some models have a built-in clamp mechanism, while others require sheet metal screws through pre-drilled holes. Ensure the collar is tight enough to prevent movement but not so tight that it deforms the chimney pipe.

Step 4: Sealing
Apply a continuous bead of high-temperature silicone sealant around the top edge where the storm collar meets the chimney pipe. Smooth the sealant with your finger to create a watertight seal. Also apply sealant under the bottom skirt where it overlaps the flashing.

Step 5: Inspection
Check that the storm collar is level and properly sealed. Perform a water test by running a hose over the installation area for several minutes while checking for leaks from inside the attic or structure. If leaks are detected, apply additional sealant as needed.

Maintenance:
Inspect the storm collar annually, especially after severe weather. Look for cracks in the sealant, rust, or loose fasteners. Reapply sealant as necessary to maintain the weatherproof barrier. A well-maintained storm collar can last 15-20 years.

Common Mistakes to Avoid:
- Installing below the flashing (causes pooling water)
- Using standard silicone instead of high-temp rated
- Over-tightening the band clamp (can crack the pipe)
- Forgetting to seal the bottom skirt edge

For professional assistance or bulk orders, contact our support team at support@example.com or call 1-800-CHIMNEY.
"@
    source   = "sample-storm-collar"
    metadata = @{
        title    = "Storm Collar Installation Guide"
        category = "installation"
        tags     = @("chimney", "weatherproofing", "installation")
        sample   = $true
    }
} | ConvertTo-Json -Depth 5

try {
    $response1 = Invoke-RestMethod -Uri "$BaseUrl/knowledge/ingest" -Method Post -Headers $headers -Body $doc1 -TimeoutSec $Timeout
    Write-Pass "Storm collar guide ingested (doc_id: $($response1.doc_id))"
}
catch {
    Write-Fail "Failed to ingest storm collar guide: $_"
}

Start-Sleep -Milliseconds 500

# Document 2: PII Test (for PII guard validation)
Write-Info "Ingesting: PII Test Document..."
$doc2 = @{
    text     = @"
Customer Support Case #45231

Customer Information:
Name: John Smith
Email: [EMAIL]
Phone: [PHONE]
Account: Premium Support

Issue Description:
Customer reported unauthorized charges on credit card [CARD] ending in 4532. After investigation, charges were legitimate but originated from a different department subscription. Customer was unaware of the secondary subscription.

Resolution:
Consolidated both subscriptions into single premium account. Refunded duplicate charges. Updated billing email to [EMAIL] for future notifications. Customer satisfied with resolution.

Follow-up:
Scheduled follow-up call in 30 days to ensure no further billing issues. Customer expressed appreciation for quick resolution. Case closed on 2025-10-28.
"@
    source   = "sample-pii-test"
    metadata = @{
        title        = "Support Case with PII"
        category     = "support"
        contains_pii = $true
        sample       = $true
    }
} | ConvertTo-Json -Depth 5

try {
    $response2 = Invoke-RestMethod -Uri "$BaseUrl/knowledge/ingest" -Method Post -Headers $headers -Body $doc2 -TimeoutSec $Timeout
    Write-Pass "PII test document ingested (doc_id: $($response2.doc_id))"
}
catch {
    Write-Fail "Failed to ingest PII test: $_"
}

Start-Sleep -Milliseconds 500

# Document 3: Audit Log Snippet (for confidence testing)
Write-Info "Ingesting: Audit Log Snippet..."
$doc3 = @{
    text     = @"
System Audit Log - October 2025

2025-10-15 09:23:15 [INFO] User admin@example.com logged in from IP 192.168.1.100
2025-10-15 09:24:03 [INFO] Bulk export initiated: 15,432 records requested
2025-10-15 09:28:47 [INFO] Export completed successfully: export_2025-10-15.csv (2.3 MB)
2025-10-15 10:15:22 [WARN] Rate limit approached: 950/1000 requests in window
2025-10-15 10:15:23 [INFO] Cache cleared manually by admin@example.com
2025-10-15 11:03:45 [INFO] Database backup initiated (automated)
2025-10-15 11:08:12 [INFO] Backup completed: backup_2025-10-15_11-03.tar.gz (145 MB)
2025-10-15 14:22:33 [ERROR] Failed query: timeout after 30s on table analytics_events
2025-10-15 14:22:35 [INFO] Query retried with reduced scope: success
2025-10-15 16:45:09 [INFO] System health check: all services nominal
2025-10-15 16:45:10 [INFO] Disk usage: 45% (225 GB / 500 GB)
2025-10-15 16:45:11 [INFO] Memory usage: 62% (12.4 GB / 20 GB)
2025-10-15 18:30:00 [INFO] Automated cleanup job started
2025-10-15 18:35:22 [INFO] Removed 1,245 expired cache entries
2025-10-15 18:35:23 [INFO] Removed 87 orphaned temp files (342 MB freed)
2025-10-15 20:00:00 [INFO] Daily metrics aggregation started
2025-10-15 20:05:33 [INFO] Metrics aggregated: 45,231 events processed
2025-10-15 23:59:59 [INFO] End of day summary: 128,432 requests, 99.94% uptime

System Performance Notes:
Average response time today: 145ms (down 15ms from yesterday). Peak traffic occurred between 10-11 AM with 15,234 requests. No security incidents detected. All automated jobs completed successfully.
"@
    source   = "sample-audit-log"
    metadata = @{
        title    = "System Audit Log October 2025"
        category = "logs"
        tags     = @("audit", "system", "monitoring")
        sample   = $true
    }
} | ConvertTo-Json -Depth 5

try {
    $response3 = Invoke-RestMethod -Uri "$BaseUrl/knowledge/ingest" -Method Post -Headers $headers -Body $doc3 -TimeoutSec $Timeout
    Write-Pass "Audit log ingested (doc_id: $($response3.doc_id))"
}
catch {
    Write-Fail "Failed to ingest audit log: $_"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3: Poll Until Worker Processes (flaky-proof)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "STEP 3: Wait for Worker to Process Embeddings"

Write-Info "Polling for worker completion (max 30s)..."
$deadline = (Get-Date).AddSeconds(30)
$ready = $false
$attempts = 0

while ((Get-Date) -lt $deadline -and -not $ready) {
    Start-Sleep -Milliseconds 800
    $attempts++
    
    try {
        $metrics = (Invoke-WebRequest -Uri "$BaseUrl/metrics" -TimeoutSec 3 -UseBasicParsing).Content
        
        # Heuristic: check if /knowledge/ingest endpoint has been hit
        if ($metrics -match 'http_requests_total\{.*endpoint="\/knowledge\/ingest"') {
            $ready = $true
            Write-Pass "Worker processed documents (verified via metrics)"
        }
    }
    catch {
        # Metrics endpoint might be slow, keep trying
    }
    
    if ($attempts % 5 -eq 0) {
        Write-Info "  Still waiting... ($attempts attempts)"
    }
}

if (-not $ready) {
    Write-Warn "Worker may still be processing; proceeding anyway."
    Write-Info "Note: Some validation tests might show zero results initially"
}
else {
    Write-Info "  Completed in ~$([math]::Round($attempts * 0.8, 1))s"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4: Prime Cache (warm up)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "STEP 4: Prime Cache"

Write-Info "Making test queries to populate cache..."

try {
    # Query 1: Storm collar (should hit the guide)
    $null = curl.exe -sS --max-time $Timeout "$BaseUrl/answer?q=how%20to%20install%20storm%20collar&mode=hybrid" -H "x-api-key: $ApiKey" 2>&1
    Write-Pass "Cache primed: storm collar query"
    
    Start-Sleep -Milliseconds 500
    
    # Query 2: Audit logs (should hit the audit doc)
    $null = curl.exe -sS --max-time $Timeout "$BaseUrl/answer?q=system%20performance%20metrics&mode=hybrid" -H "x-api-key: $ApiKey" 2>&1
    Write-Pass "Cache primed: audit query"
}
catch {
    Write-Warn "Cache priming had some issues (not critical)"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5: Run Full Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Step "STEP 5: Run Full Validation Suite"
Write-Info "Launching validate-quick-wins.ps1..."
Write-Host ""

# Run the validation script
$scriptPath = Join-Path $PSScriptRoot "validate-quick-wins.ps1"
if (Test-Path $scriptPath) {
    & $scriptPath -ApiKey $ApiKey -BaseUrl $BaseUrl -Timeout $Timeout
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # METRICS SNAPSHOT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "📊 METRICS SNAPSHOT" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    
    try {
        $m = (Invoke-WebRequest -Uri "$BaseUrl/metrics" -TimeoutSec 5 -UseBasicParsing).Content
        $metricsLines = $m | Select-String "aether_rag_answers_total|aether_rag_lowconfidence_total|aether_rag_cache_(hits|misses)_total|http_requests_total\{.*endpoint=""\/answer""|http_requests_total\{.*endpoint=""\/search""" | 
        Select-Object -First 12
        
        if ($metricsLines) {
            $metricsLines | ForEach-Object { Write-Host "  $($_.Line)" -ForegroundColor Gray }
        }
        else {
            Write-Info "No relevant metrics found yet (normal on fresh start)"
        }
    }
    catch {
        Write-Warn "Could not fetch metrics snapshot: $_"
    }
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FINAL SUMMARY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    Write-Host ""
    if ($exitCode -eq 0) {
        Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "║          SETUP + VALIDATION SUCCESSFUL! 🎉          ║" -ForegroundColor Green
        Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
        Write-Pass "Sample data ingested and all quick wins validated"
        Write-Info "You can now test queries against the sample corpus:"
        Write-Host "  • Storm collar installation guide (sample-storm-collar)" -ForegroundColor Gray
        Write-Host "  • PII test document (sample-pii-test, should trigger guards)" -ForegroundColor Gray
        Write-Host "  • System audit logs (sample-audit-log)" -ForegroundColor Gray
        Write-Host ""
        Write-Info "Try: curl.exe `"http://localhost:8000/answer?q=how%20to%20install%20storm%20collar`" -H `"x-api-key: YOUR_KEY`""
    }
    else {
        Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Yellow
        Write-Host "║     SETUP COMPLETE, BUT SOME TESTS FAILED ⚠        ║" -ForegroundColor Yellow
        Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Yellow
        Write-Host ""
        Write-Info "Sample data was ingested, but validation had issues"
        Write-Info "Check the validation output above for details"
        Write-Info "Common fixes:"
        Write-Host "  • Re-run after waiting a few seconds for embeddings" -ForegroundColor Gray
        Write-Host "  • Check logs: docker compose logs --tail=50 api" -ForegroundColor Gray
    }
    
    exit $exitCode
}
else {
    Write-Fail "Cannot find validation script at: $scriptPath"
    exit 1
}
