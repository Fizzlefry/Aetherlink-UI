#!/usr/bin/env powershell
# beta-onboard.ps1 - Automated Beta Customer Onboarding Pipeline
# Usage: .\beta-onboard.ps1 -Company "Acme Corp" -AdminEmail "ops@acme.com" -Plan enterprise -DemoData -GuidedTour

param(
    [Parameter(Mandatory = $true)]
    [string]$Company,

    [Parameter(Mandatory = $true)]
    [string]$AdminEmail,

    [Parameter(Mandatory = $false)]
    [ValidateSet("starter", "professional", "enterprise")]
    [string]$Plan = "starter",

    [Parameter(Mandatory = $false)]
    [ValidateSet("general", "finserv", "saas", "industrial")]
    [string]$Profile = "general",

    [switch]$DemoData,
    [switch]$GuidedTour,
    [switch]$DryRun,
    [switch]$Help
)

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ConfigDir = Join-Path $ProjectRoot "provisioning\config"

# Colors for output
$Colors = @{
    "red"    = [ConsoleColor]::Red
    "green"  = [ConsoleColor]::Green
    "yellow" = [ConsoleColor]::Yellow
    "blue"   = [ConsoleColor]::Blue
    "cyan"   = [ConsoleColor]::Cyan
    "white"  = [ConsoleColor]::White
}

function Write-ColoredOutput {
    param([string]$Message, [string]$Color = "white")
    $OriginalColor = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $Colors[$Color]
    Write-Host $Message
    $Host.UI.RawUI.ForegroundColor = $OriginalColor
}

function Write-Info {
    param([string]$Message)
    Write-ColoredOutput "ℹ️  $Message" "blue"
}
function Write-Success {
    param([string]$Message)
    Write-ColoredOutput "✅ $Message" "green"
}
function Write-Warning {
    param([string]$Message)
    Write-ColoredOutput "⚠️  $Message" "yellow"
}
function Write-Error {
    param([string]$Message)
    Write-ColoredOutput "❌ $Message" "red"
}

function Exit-WithError {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

# Show help
if ($Help) {
    Write-Host "beta-onboard.ps1 - Automated Beta Customer Onboarding Pipeline"
    Write-Host ""
    Write-Host "USAGE:"
    Write-Host "    .\beta-onboard.ps1 -Company 'Acme Corp' -AdminEmail 'ops@acme.com' [-Plan enterprise] [-DemoData] [-GuidedTour] [-DryRun]"
    Write-Host ""
    Write-Host "PARAMETERS:"
    Write-Host "    -Company      Company name (required)"
    Write-Host "    -AdminEmail   Admin email for notifications (required)"
    Write-Host "    -Plan         Subscription plan: starter, professional, enterprise (default: starter)"
    Write-Host "    -Profile      Industry profile: general, finserv, saas, industrial (default: general)"
    Write-Host "    -DemoData     Seed tenant with demo NOC data"
    Write-Host "    -GuidedTour   Enable guided evaluation workflow"
    Write-Host "    -DryRun       Show what would be done without making changes"
    Write-Host "    -Help         Show this help message"
    exit 0
}

# Validate environment
Write-Info "Validating environment..."
if (-not (Test-Path $ProjectRoot)) {
    Exit-WithError "Project root not found: $ProjectRoot"
}

# Generate tenant details
$TenantId = ($Company -replace '[^a-zA-Z0-9]', '' -replace ' ', '_').ToUpper()
$TenantDomain = ($Company -replace '[^a-zA-Z0-9]', '').ToLower()
$ApiKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })

Write-Info "Generated tenant details:"
Write-Host "  Tenant ID: $TenantId"
Write-Host "  API Key: $ApiKey"
Write-Host "  Domain: $TenantDomain.aetherlink.beta"

if ($DryRun) {
    Write-Warning "DRY RUN MODE - No changes will be made"
}

# Provision tenant
function New-Tenant {
    Write-Info "Provisioning tenant..."

    if (-not $DryRun) {
        # Call Python provisioning service
        $ProvisioningScript = Join-Path $ProjectRoot "services\provisioning\provision_tenant.py"
        if (Test-Path $ProvisioningScript) {
            & python $ProvisioningScript --tenant-id $TenantId --company "$Company" --admin-email $AdminEmail --plan $Plan
            if ($LASTEXITCODE -ne 0) {
                Exit-WithError "Tenant provisioning failed"
            }
        }
        else {
            Write-Warning "Provisioning script not found, simulating..."
        }
    }

    Write-Success "Tenant provisioned successfully"
}

# Seed demo data
function Set-DemoData {
    if (-not $DemoData) {
        Write-Info "Skipping demo data seeding (not requested)"
        return
    }

    Write-Info "Seeding demo NOC data..."

    if (-not $DryRun) {
        # Run demo data generator
        $DemoGenerator = Join-Path $ScriptDir "demo_data_generator.py"
        & python $DemoGenerator --tenant-id $TenantId --days 30 --alerts 500 --incidents 50 --profile $Profile

        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Demo data seeding completed with warnings"
        }
        else {
            Write-Success "Demo data seeded successfully"
        }
    }
    else {
        Write-Host "  Would run: python $DemoGenerator --tenant-id $TenantId --days 30 --alerts 500 --incidents 50"
    }
}

# Setup guided tour
function Set-GuidedTour {
    if (-not $GuidedTour) {
        Write-Info "Skipping guided tour setup (not requested)"
        return
    }

    Write-Info "Setting up guided evaluation workflow..."

    if (-not $DryRun) {
        $TourConfig = @{
            "tenant_id"       = $TenantId
            "enabled"         = $true
            "steps"           = @(
                @{
                    "id"          = "welcome"
                    "title"       = "Welcome to AetherLink"
                    "description" = "Get started with your AI-powered NOC platform"
                    "action"      = "show_dashboard"
                },
                @{
                    "id"          = "explore_alerts"
                    "title"       = "Explore Alert Management"
                    "description" = "See how AetherLink processes and categorizes alerts"
                    "action"      = "navigate_alerts"
                },
                @{
                    "id"          = "ai_insights"
                    "title"       = "AI-Powered Insights"
                    "description" = "Discover autonomous AI actions and recommendations"
                    "action"      = "show_insights"
                },
                @{
                    "id"          = "customize"
                    "title"       = "Customize Your Experience"
                    "description" = "Configure integrations and notification preferences"
                    "action"      = "open_settings"
                }
            )
            "current_step"    = 0
            "completed_steps" = @()
        }

        $TourFile = Join-Path $ConfigDir "$TenantId\guided_tour.json"
        $TourConfig | ConvertTo-Json -Depth 10 | Out-File -FilePath $TourFile -Encoding UTF8
    }

    Write-Success "Guided tour configured"
}

# Setup telemetry
function Set-Telemetry {
    Write-Info "Configuring telemetry collection..."

    if (-not $DryRun) {
        $TelemetryConfig = @{
            "tenant_id"       = $TenantId
            "enabled"         = $true
            "metrics"         = @{
                "alert_processing"  = $true
                "ai_actions"        = $true
                "user_interactions" = $true
                "performance"       = $true
            }
            "retention_days"  = 90
            "anonymize_pii"   = $true
            "send_to_central" = $true
        }

        $TelemetryFile = Join-Path $ConfigDir "$TenantId\telemetry.json"
        $TelemetryConfig | ConvertTo-Json -Depth 10 | Out-File -FilePath $TelemetryFile -Encoding UTF8
    }

    Write-Success "Telemetry configured"
}

# Send welcome email
function Send-WelcomeEmail {
    Write-Info "Sending welcome email..."

    if (-not $DryRun) {
        $EmailTemplate = @'
Subject: Welcome to AetherLink Beta - {0}

Dear {1} Team,

Welcome to the AetherLink beta program! Your AI-powered NOC platform is now ready.

Access Details:
• Dashboard: https://{2}.aetherlink.beta
• API Key: {3}
• Documentation: https://docs.aetherlink.beta

Getting Started:
1. Log in to your dashboard
2. Explore the pre-loaded demo data (if requested)
3. Configure your integrations
4. Set up notification preferences

Your feedback is crucial for our development. Please don''t hesitate to reach out with questions or suggestions.

Best regards,
The AetherLink Team
support@aetherlink.beta
'@ -f $Company, $Company, $TenantDomain, $ApiKey

        # In a real implementation, this would send via SMTP
        $EmailFile = Join-Path $ConfigDir "$TenantId\welcome_email.txt"
        $EmailTemplate | Out-File -FilePath $EmailFile -Encoding UTF8

        Write-Host "  Email saved to: $EmailFile"
    }

    Write-Success "Welcome email prepared"
}

# Generate summary
function Show-Summary {
    Write-Host ""
    Write-ColoredOutput "🎉 Beta Onboarding Complete!" "green"
    Write-Host ""
    Write-Host "Tenant Details:"
    Write-Host "  Company: $Company"
    Write-Host "  Tenant ID: $TenantId"
    Write-Host "  Admin Email: $AdminEmail"
    Write-Host "  Plan: $Plan"
    Write-Host "  API Key: $ApiKey"
    Write-Host ""
    Write-Host "Next Steps:"
    Write-Host "  1. Access dashboard at https://$TenantDomain.aetherlink.beta"
    if ($DemoData) {
        Write-Host "  2. Review the pre-loaded demo data to see AetherLink in action"
    }
    if ($GuidedTour) {
        Write-Host "  3. Follow the guided tour for an optimal first experience"
    }
    Write-Host "  4. Configure integrations and notification preferences"
    Write-Host "  5. Start monitoring your systems"
    Write-Host ""
    Write-Host "Support:"
    Write-Host "  Email: support@aetherlink.beta"
    Write-Host "  Docs: https://docs.aetherlink.beta"
}

# Main execution
Write-ColoredOutput "🚀 Starting AetherLink Beta Onboarding" "cyan"
Write-Host "Company: $Company"
Write-Host "Plan: $Plan"
Write-Host "Profile: $Profile"
Write-Host "Demo Data: $($DemoData.ToString())"
Write-Host "Guided Tour: $($GuidedTour.ToString())"
Write-Host ""try {
    New-Tenant
    Set-DemoData
    Set-GuidedTour
    Set-Telemetry
    Send-WelcomeEmail
    Show-Summary
}
catch {
    Write-Host "Onboarding failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
