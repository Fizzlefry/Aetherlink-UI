# AetherLink Monitoring Setup Script
# This script helps configure Prometheus to scrape AetherLink metrics

param(
    [string]$PrometheusConfigPath = "C:\ProgramData\prometheus\prometheus.yml",
    [string]$AlertRulesPath = "C:\ProgramData\prometheus\rules\aetherlink-analytics.yml",
    [switch]$Install,
    [switch]$Configure,
    [switch]$Test
)

function Install-Prometheus {
    Write-Host "Installing Prometheus..." -ForegroundColor Cyan

    # Download Prometheus (adjust version as needed)
    $prometheusVersion = "2.45.0"
    $downloadUrl = "https://github.com/prometheus/prometheus/releases/download/v$prometheusVersion/prometheus-$prometheusVersion.windows-amd64.tar.gz"
    $tempPath = "$env:TEMP\prometheus.tar.gz"
    $extractPath = "$env:TEMP\prometheus"

    Invoke-WebRequest -Uri $downloadUrl -OutFile $tempPath
    & tar -xzf $tempPath -C $env:TEMP

    # Move to ProgramData
    $installPath = "C:\ProgramData\prometheus"
    if (!(Test-Path $installPath)) {
        New-Item -ItemType Directory -Path $installPath -Force
    }

    Copy-Item "$extractPath\prometheus.exe" $installPath -Force
    Copy-Item "$extractPath\promtool.exe" $installPath -Force

    # Create directories
    New-Item -ItemType Directory -Path "$installPath\rules" -Force
    New-Item -ItemType Directory -Path "$installPath\data" -Force

    Write-Host "Prometheus installed to $installPath" -ForegroundColor Green
}

function Set-PrometheusConfig {
    Write-Host "Configuring Prometheus for AetherLink..." -ForegroundColor Cyan

    # Copy alert rules
    Copy-Item "monitoring\aetherlink-ops-analytics.rules.yml" $AlertRulesPath -Force

    # Update prometheus.yml
    $config = @"
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules\aetherlink-analytics.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - localhost:9093

scrape_configs:
  - job_name: 'aetherlink-command-center'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
"@

    $config | Out-File -FilePath $PrometheusConfigPath -Encoding UTF8

    Write-Host "Prometheus configured. Alert rules copied to $AlertRulesPath" -ForegroundColor Green
}

function Test-Monitoring {
    Write-Host "Testing AetherLink monitoring setup..." -ForegroundColor Cyan

    # Test metrics endpoint
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -UseBasicParsing
        if ($response.Content -match "aetherlink_ops_analytics") {
            Write-Host "✓ Metrics endpoint responding with AetherLink analytics" -ForegroundColor Green
        }
        else {
            Write-Host "⚠ Metrics endpoint responding but no AetherLink analytics found" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "✗ Cannot reach metrics endpoint: $_" -ForegroundColor Red
    }

    # Test analytics API
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/ops/analytics" -Headers @{"x-api-key" = $env:API_KEY_EXPERTCO } -UseBasicParsing
        $data = $response.Content | ConvertFrom-Json
        if ($data.groups) {
            Write-Host "✓ Analytics API responding with groups data" -ForegroundColor Green
            Write-Host "  Available operation groups:" -ForegroundColor Cyan
            $data.groups.PSObject.Properties | ForEach-Object {
                Write-Host "    $($_.Name): $($_.Value.all_time) total, $($_.Value.last_24h) last 24h" -ForegroundColor Gray
            }
        }
        else {
            Write-Host "⚠ Analytics API responding but no groups data found" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "✗ Cannot reach analytics API: $_" -ForegroundColor Red
    }
}

# Main execution
$action = $null
if ($Install) { $action = "Install" }
elseif ($Configure) { $action = "Configure" }
elseif ($Test) { $action = "Test" }

switch ($action) {
    "Install" {
        Install-Prometheus
    }
    "Configure" {
        Set-PrometheusConfig
    }
    "Test" {
        Test-Monitoring
    }
    default {
        Write-Host "AetherLink Monitoring Setup Script" -ForegroundColor Cyan
        Write-Host "Usage:" -ForegroundColor White
        Write-Host "  .\setup-monitoring.ps1 -Install      # Install Prometheus"
        Write-Host "  .\setup-monitoring.ps1 -Configure   # Configure for AetherLink"
        Write-Host "  .\setup-monitoring.ps1 -Test        # Test the setup"
        Write-Host ""
        Write-Host "Example workflow:" -ForegroundColor Gray
        Write-Host "  1. .\setup-monitoring.ps1 -Install -Configure"
        Write-Host "  2. Start Command Center: .\run-command-center.ps1"
        Write-Host "  3. Start Prometheus: & 'C:\ProgramData\prometheus\prometheus.exe' --config.file='C:\ProgramData\prometheus\prometheus.yml'"
        Write-Host "  4. .\setup-monitoring.ps1 -Test"
    }
}
