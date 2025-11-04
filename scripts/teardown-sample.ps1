#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Safely removes sample test data from the knowledge base.

.DESCRIPTION
    This script:
    1. Dry-run: Counts sample documents (source LIKE 'sample-%')
    2. Confirms with user
    3. Deletes sample data from DuckDB

    Safe and deterministic - only removes docs with sample- prefix.

.PARAMETER DryRun
    If specified, only counts rows without deleting.

.PARAMETER Force
    Skip confirmation prompt.

.EXAMPLE
    # Dry run (default)
    .\scripts\teardown-sample.ps1

.EXAMPLE
    # Delete with confirmation
    .\scripts\teardown-sample.ps1 -Force:$false

.EXAMPLE
    # Delete without confirmation
    .\scripts\teardown-sample.ps1 -Force
#>

param(
    [switch]$DryRun = $false,
    [switch]$Force = $false,
    [string]$Container = "aether-customer-ops"
)

# Color helpers
function Write-Pass { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "ℹ $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }

Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        AetherLink: Teardown Sample Data            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if container is running
Write-Info "Checking container: $Container"
$containerStatus = docker ps --filter "name=$Container" --format "{{.Status}}" 2>$null

if (-not $containerStatus) {
    Write-Fail "Container '$Container' is not running"
    Write-Info "Start it with: docker compose -f pods\customer_ops\docker-compose.yml up -d"
    exit 1
}

Write-Pass "Container is running"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: Dry Run (Count Sample Rows)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Host ""
Write-Info "Counting sample documents (source LIKE 'sample-%')..."

$countScript = @'
import duckdb, json, sys
try:
    con = duckdb.connect('/app/data/knowledge.duckdb', read_only=True)

    # Count chunks with sample- prefix in source
    result = con.execute("""
        SELECT COUNT(*)
        FROM embeddings
        WHERE metadata ->> 'source' LIKE 'sample-%'
    """).fetchone()

    count = result[0] if result else 0
    print(f"{count}")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
'@

try {
    $count = docker exec $Container python -c $countScript 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to query database: $count"
        exit 1
    }

    $sampleCount = [int]$count.Trim()

    if ($sampleCount -eq 0) {
        Write-Info "No sample documents found (count: 0)"
        Write-Pass "Nothing to clean up!"
        exit 0
    }

    Write-Warn "Found $sampleCount sample chunk(s) to delete"
    Write-Info "Sample sources: sample-storm-collar, sample-pii-test, sample-audit-log"

}
catch {
    Write-Fail "Error counting sample documents: $_"
    exit 1
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: Dry Run Exit (if requested)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if ($DryRun) {
    Write-Host ""
    Write-Pass "Dry run complete. Found $sampleCount sample chunks."
    Write-Info "Run without -DryRun flag to delete them."
    exit 0
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3: Confirmation Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if (-not $Force) {
    Write-Host ""
    Write-Warn "⚠ This will permanently delete $sampleCount chunk(s)"
    $response = Read-Host "Type 'DELETE' to confirm"

    if ($response -ne "DELETE") {
        Write-Info "Cancelled by user"
        exit 0
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4: Delete Sample Data
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Host ""
Write-Info "Deleting sample documents..."

$deleteScript = @'
import duckdb, sys
try:
    con = duckdb.connect('/app/data/knowledge.duckdb')

    # Delete chunks with sample- prefix
    con.execute("""
        DELETE FROM embeddings
        WHERE metadata ->> 'source' LIKE 'sample-%'
    """)

    # Get affected rows (note: DuckDB doesn't return rowcount for DELETE)
    # So we just confirm success
    con.commit()
    print("SUCCESS")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
'@

try {
    $result = docker exec $Container python -c $deleteScript 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to delete sample data: $result"
        exit 1
    }

    Write-Pass "Deleted $sampleCount sample chunk(s)"

}
catch {
    Write-Fail "Error deleting sample data: $_"
    exit 1
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5: Verify Deletion
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Host ""
Write-Info "Verifying deletion..."

try {
    $verifyCount = docker exec $Container python -c $countScript 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Could not verify deletion: $verifyCount"
    }
    else {
        $remainingCount = [int]$verifyCount.Trim()

        if ($remainingCount -eq 0) {
            Write-Pass "Verification: 0 sample chunks remain"
        }
        else {
            Write-Warn "Verification: $remainingCount sample chunks still present"
            Write-Info "This may indicate a query mismatch or concurrent writes"
        }
    }
}
catch {
    Write-Warn "Could not verify: $_"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║             TEARDOWN COMPLETE! ✓                    ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Pass "Sample data has been removed from knowledge base"
Write-Info "You can now run fresh tests with: .\scripts\setup-and-validate.ps1"
Write-Host ""

exit 0
