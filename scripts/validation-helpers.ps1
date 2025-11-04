# PowerShell Helper Functions for Validation Scripts
# Source this file in your scripts with: . "$PSScriptRoot\validation-helpers.ps1"

<#
.SYNOPSIS
    Invokes a web request with exponential backoff retry logic.
    
.DESCRIPTION
    Retries HTTP requests with jitter to prevent thundering herd.
    Perfect for CI environments with network flakiness.
    
.PARAMETER Uri
    The URI to request.
    
.PARAMETER Headers
    Optional headers dictionary.
    
.PARAMETER Method
    HTTP method (GET, POST, etc). Default: GET
    
.PARAMETER Body
    Optional request body.
    
.PARAMETER MaxRetries
    Maximum number of retry attempts. Default: 4
    
.PARAMETER TimeoutSec
    Request timeout in seconds. Default: 5
    
.EXAMPLE
    $response = Invoke-WithRetry -Uri "http://localhost:8000/health"
    
.EXAMPLE
    $headers = @{"x-api-key" = "test-key"}
    $response = Invoke-WithRetry -Uri "http://localhost:8000/answer?q=test" -Headers $headers -MaxRetries 3
#>
function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        
        [hashtable]$Headers = @{},
        
        [string]$Method = "GET",
        
        [string]$Body = $null,
        
        [int]$MaxRetries = 4,
        
        [int]$TimeoutSec = 5
    )
    
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            $params = @{
                Uri             = $Uri
                Method          = $Method
                Headers         = $Headers
                TimeoutSec      = $TimeoutSec
                UseBasicParsing = $true
                ErrorAction     = "Stop"
            }
            
            if ($Body) {
                $params.Body = $Body
            }
            
            return Invoke-WebRequest @params
            
        }
        catch {
            $lastError = $_
            
            if ($attempt -eq $MaxRetries) {
                throw "Failed after $MaxRetries attempts: $lastError"
            }
            
            # Exponential backoff with jitter
            $baseDelay = [math]::Pow(2, $attempt - 1) * 300  # 300ms, 600ms, 1200ms, 2400ms
            $jitter = Get-Random -Minimum 0 -Maximum 400
            $delay = $baseDelay + $jitter
            
            Write-Verbose "Attempt $attempt failed, retrying in ${delay}ms..."
            Start-Sleep -Milliseconds $delay
        }
    }
}

<#
.SYNOPSIS
    Polls an endpoint until a condition is met or timeout.
    
.DESCRIPTION
    Useful for waiting on async operations like embeddings processing.
    
.PARAMETER Uri
    The URI to poll.
    
.PARAMETER Condition
    ScriptBlock that receives the response content and returns $true when ready.
    
.PARAMETER TimeoutSeconds
    Maximum time to wait. Default: 30
    
.PARAMETER PollIntervalMs
    Time between polls in milliseconds. Default: 800
    
.PARAMETER Headers
    Optional headers for the request.
    
.EXAMPLE
    $ready = Poll-Until -Uri "http://localhost:8000/metrics" -Condition {
        param($content)
        return $content -match "worker_jobs_completed"
    }
#>
function Poll-Until {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        
        [Parameter(Mandatory = $true)]
        [scriptblock]$Condition,
        
        [int]$TimeoutSeconds = 30,
        
        [int]$PollIntervalMs = 800,
        
        [hashtable]$Headers = @{}
    )
    
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $attempts = 0
    
    while ((Get-Date) -lt $deadline) {
        $attempts++
        
        try {
            $response = Invoke-WebRequest -Uri $Uri -Headers $Headers -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            
            if (& $Condition $response.Content) {
                return @{
                    Success     = $true
                    Attempts    = $attempts
                    TimeElapsed = $TimeoutSeconds - (($deadline - (Get-Date)).TotalSeconds)
                }
            }
            
        }
        catch {
            # Ignore errors during polling
        }
        
        Start-Sleep -Milliseconds $PollIntervalMs
    }
    
    return @{
        Success     = $false
        Attempts    = $attempts
        TimeElapsed = $TimeoutSeconds
    }
}

<#
.SYNOPSIS
    Extracts metrics matching a pattern from Prometheus endpoint.
    
.DESCRIPTION
    Parses Prometheus metrics text format and filters by regex pattern.
    
.PARAMETER BaseUrl
    Base URL of the API (e.g., http://localhost:8000)
    
.PARAMETER Pattern
    Regex pattern to match metric names.
    
.PARAMETER MaxResults
    Maximum number of metrics to return. Default: 20
    
.EXAMPLE
    $cacheMetrics = Get-MetricsSnapshot -BaseUrl "http://localhost:8000" -Pattern "aether_rag_cache"
#>
function Get-MetricsSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,
        
        [string]$Pattern = "aether_rag_",
        
        [int]$MaxResults = 20
    )
    
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/metrics" -TimeoutSec 5 -UseBasicParsing
        $metrics = $response.Content | Select-String -Pattern $Pattern | Select-Object -First $MaxResults
        
        return $metrics | ForEach-Object { $_.Line }
        
    }
    catch {
        Write-Warning "Could not fetch metrics: $_"
        return @()
    }
}

<#
.SYNOPSIS
    Validates that required environment variables are set.
    
.DESCRIPTION
    Checks for presence of environment variables and exits with error if missing.
    
.PARAMETER Required
    Array of required environment variable names.
    
.PARAMETER Optional
    Array of optional environment variable names (shows warnings only).
    
.EXAMPLE
    Test-EnvironmentVariables -Required @("API_KEY_EXPERTCO", "DATABASE_URL")
#>
function Test-EnvironmentVariables {
    param(
        [string[]]$Required = @(),
        [string[]]$Optional = @()
    )
    
    $missing = @()
    
    foreach ($var in $Required) {
        if (-not (Get-Item "env:$var" -ErrorAction SilentlyContinue)) {
            $missing += $var
            Write-Host "✗ Missing required environment variable: $var" -ForegroundColor Red
        }
    }
    
    foreach ($var in $Optional) {
        if (-not (Get-Item "env:$var" -ErrorAction SilentlyContinue)) {
            Write-Host "⚠ Optional environment variable not set: $var" -ForegroundColor Yellow
        }
    }
    
    if ($missing.Count -gt 0) {
        Write-Host "`nSet required variables before continuing." -ForegroundColor Red
        exit 1
    }
}

<#
.SYNOPSIS
    Pretty-prints a test result with icon and color.
    
.DESCRIPTION
    Standardized output for validation test results.
    
.PARAMETER Name
    Test name.
    
.PARAMETER Passed
    Whether the test passed.
    
.PARAMETER Message
    Optional additional message.
    
.EXAMPLE
    Write-TestResult -Name "Cache Hit Rate" -Passed $true -Message "5 hits, 2 misses"
#>
function Write-TestResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        
        [Parameter(Mandatory = $true)]
        [bool]$Passed,
        
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "  ✓ $Name" -ForegroundColor Green
        if ($Message) {
            Write-Host "    $Message" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "  ✗ $Name" -ForegroundColor Red
        if ($Message) {
            Write-Host "    $Message" -ForegroundColor Yellow
        }
    }
}

# Export functions (PowerShell 5.1 compatible)
Export-ModuleMember -Function @(
    'Invoke-WithRetry',
    'Poll-Until',
    'Get-MetricsSnapshot',
    'Test-EnvironmentVariables',
    'Write-TestResult'
)
