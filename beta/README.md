# AetherLink Beta Onboarding

Automated beta customer onboarding infrastructure for AetherLink.

## Overview

This directory contains tools for setting up realistic beta environments with industry-specific demo data, ensuring beta customers see relevant scenarios instead of empty dashboards.

## Components

### `beta-onboard.sh` / `beta-onboard.ps1`
Automated onboarding scripts that:
- Provision tenant via existing TenantProvisioningService
- Generate industry-specific demo data
- Configure guided tours and telemetry
- Send welcome emails

### `demo_data_generator.py`
Generates realistic NOC data including:
- Alerts, incidents, and AI actions
- Performance metrics and system health data
- Industry-tailored scenarios

### `profiles.json`
Industry profile definitions with:
- Alert category distributions
- Severity weightings
- Target audiences and descriptions

## Industry Profiles

| Profile | Focus | Key Characteristics |
|---------|-------|-------------------|
| `general` | Balanced NOC | Mixed alerts across all categories |
| `finserv` | Security/Compliance | 50% security alerts, PCI/compliance focus |
| `saas` | Application Performance | 50% application alerts, scalability focus |
| `industrial` | Infrastructure/OT | 60% infrastructure alerts, industrial scenarios |

## Usage

### Command Line
```bash
# Generate demo data directly
python beta/demo_data_generator.py --tenant-id TENANT --profile finserv --alerts 500

# Full onboarding (Bash)
./beta-onboard.sh --company "SecureBank" --profile finserv --demo-data

# Full onboarding (PowerShell)
.\beta-onboard.ps1 -Company "SecureBank" -Profile finserv -DemoData
```

### Profile Selection
Choose the profile that matches your beta customer's industry:

- **Financial Services**: `--profile finserv`
- **SaaS/Cloud**: `--profile saas`
- **Industrial/Manufacturing**: `--profile industrial`
- **General IT**: `--profile general` (default)

## Data Structure

Generated data is stored in `provisioning/config/{TENANT_ID}/`:
- `demo_alerts.json` - Alert history
- `demo_incidents.json` - Incident records
- `demo_actions.json` - AI autonomous actions
- `demo_metrics.json` - Performance metrics and profile info

## UI Integration

The metrics file includes profile information that can be displayed in the dashboard:
```json
{
  "profile": {
    "name": "finserv",
    "display_name": "Financial Services",
    "description": "Security and compliance-focused alerts...",
    "target_audience": "Banks, payment processors..."
  }
}
```

This allows the UI to show "Viewing demo data for: Financial Services" context.
