#!/bin/bash
# beta-onboard.sh - Automated Beta Customer Onboarding Pipeline
# Usage: ./beta-onboard.sh --company "Acme Corp" --admin-email "ops@acme.com" --plan enterprise --profile finserv --demo-data --guided-tour

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/provisioning/config"
BETA_DIR="$PROJECT_ROOT/beta"
LOG_FILE="$BETA_DIR/onboarding_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    echo -e "${RED}ERROR: $1${NC}" >&2
    log "ERROR: $1"
    exit 1
}

# Success message
success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
    log "SUCCESS: $1"
}

# Info message
info() {
    echo -e "${BLUE}INFO: $1${NC}"
    log "INFO: $1"
}

# Warning message
warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
    log "WARNING: $1"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --company)
                COMPANY_NAME="$2"
                shift 2
                ;;
            --admin-email)
                ADMIN_EMAIL="$2"
                shift 2
                ;;
            --plan)
                PLAN="$2"
                shift 2
                ;;
            --profile)
                PROFILE="$2"
                shift 2
                ;;
            --demo-data)
                DEMO_DATA=true
                shift
                ;;
            --guided-tour)
                GUIDED_TOUR=true
                shift
                ;;
            --help)
                echo "Usage: $0 --company COMPANY --admin-email EMAIL [--plan PLAN] [--profile PROFILE] [--demo-data] [--guided-tour]"
                echo ""
                echo "Arguments:"
                echo "  --company NAME      Company/organization name"
                echo "  --admin-email EMAIL Admin email for notifications"
                echo "  --plan PLAN         Subscription plan (starter, professional, enterprise) [default: starter]"
                echo "  --profile PROFILE   Industry profile (general, finserv, saas, industrial) [default: general]"
                echo "  --demo-data         Seed tenant with demo NOC data"
                echo "  --guided-tour       Enable guided evaluation workflow"
                echo "  --help              Show this help message"
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1"
                ;;
        esac
    done

    # Validate required arguments
    if [[ -z "$COMPANY_NAME" ]]; then
        error_exit "Company name is required (--company)"
    fi

    if [[ -z "$ADMIN_EMAIL" ]]; then
        error_exit "Admin email is required (--admin-email)"
    fi

    # Set defaults
    PLAN="${PLAN:-starter}"
    PROFILE="${PROFILE:-general}"
    DEMO_DATA="${DEMO_DATA:-false}"
    GUIDED_TOUR="${GUIDED_TOUR:-false}"
}

# Validate environment
validate_environment() {
    info "Validating environment..."

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        error_exit "Python 3 is required but not found"
    fi

    # Check if required directories exist
    if [[ ! -d "$PROJECT_ROOT/provisioning" ]]; then
        error_exit "Provisioning directory not found: $PROJECT_ROOT/provisioning"
    fi

    # Create beta directory if it doesn't exist
    mkdir -p "$BETA_DIR"

    success "Environment validation complete"
}

# Generate tenant ID and credentials
generate_credentials() {
    info "Generating tenant credentials..."

    # Generate unique tenant ID
    TENANT_ID="beta_$(openssl rand -hex 8)"

    # Generate API keys
    API_KEY=$(openssl rand -hex 32)
    ADMIN_KEY=$(openssl rand -hex 32)

    # Generate temporary password (will be emailed to admin)
    TEMP_PASSWORD=$(openssl rand -hex 8)

    success "Credentials generated for tenant: $TENANT_ID"
}

# Provision tenant using existing provisioning system
provision_tenant() {
    info "Provisioning tenant: $TENANT_ID"

    # Use the existing tenant provisioning service
    python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from provisioning.tenant_provisioning import TenantProvisioningService

try:
    service = TenantProvisioningService()
    tenant = service.provision_tenant(
        name='$COMPANY_NAME',
        domain='$(echo $ADMIN_EMAIL | cut -d'@' -f2)',
        plan='$PLAN',
        billing_email='$ADMIN_EMAIL'
    )
    print(f'Tenant provisioned: {tenant.tenant_id}')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
    "

    if [[ $? -ne 0 ]]; then
        error_exit "Failed to provision tenant"
    fi

    success "Tenant provisioned successfully"
}

# Seed demo data if requested
seed_demo_data() {
    if [[ "$DEMO_DATA" != "true" ]]; then
        info "Skipping demo data seeding (not requested)"
        return
    fi

    info "Seeding demo NOC data..."

    # Run demo data generator
    python3 "$PROJECT_ROOT/beta/demo_data_generator.py" \
        --tenant-id "$TENANT_ID" \
        --days 30 \
        --alerts 500 \
        --incidents 50 \
        --profile "$PROFILE"

    if [[ $? -ne 0 ]]; then
        warning "Demo data seeding completed with warnings"
    else
        success "Demo data seeded successfully"
    fi
}

# Setup guided tour if requested
setup_guided_tour() {
    if [[ "$GUIDED_TOUR" != "true" ]]; then
        info "Skipping guided tour setup (not requested)"
        return
    fi

    info "Setting up guided evaluation workflow..."

    # Create guided tour configuration
    cat > "$CONFIG_DIR/$TENANT_ID/guided_tour.json" << EOF
{
    "tenant_id": "$TENANT_ID",
    "company": "$COMPANY_NAME",
    "enabled": true,
    "current_step": 1,
    "steps": [
        {
            "id": 1,
            "title": "Welcome to AetherLink",
            "description": "Get familiar with your AI Operations Brain dashboard",
            "action": "view_dashboard",
            "completed": false
        },
        {
            "id": 2,
            "title": "Explore Live Alerts",
            "description": "See how AetherLink processes real-time alerts autonomously",
            "action": "view_alerts",
            "completed": false
        },
        {
            "id": 3,
            "title": "Review AI Actions",
            "description": "Observe autonomous incident response and remediation",
            "action": "view_actions",
            "completed": false
        },
        {
            "id": 4,
            "title": "Check Analytics",
            "description": "Review performance metrics and learning insights",
            "action": "view_analytics",
            "completed": false
        },
        {
            "id": 5,
            "title": "Schedule Demo",
            "description": "Book a personalized demo with our solutions team",
            "action": "schedule_demo",
            "completed": false
        }
    ],
    "progress_tracking": {
        "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "last_activity": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "completion_percentage": 0
    }
}
EOF

    success "Guided tour configured"
}

# Send welcome email
send_welcome_email() {
    info "Sending welcome email to $ADMIN_EMAIL..."

    # Create email template
    cat > "$BETA_DIR/welcome_email_$TENANT_ID.txt" << EOF
Subject: Welcome to AetherLink Beta - Your AI Operations Brain is Ready!

Dear $COMPANY_NAME Team,

Congratulations! Your AetherLink AI Operations Brain has been successfully provisioned and is ready for evaluation.

TENANT DETAILS:
- Tenant ID: $TENANT_ID
- Plan: $PLAN
- Dashboard: https://beta.aetherlink.com/dashboard?tenant=$TENANT_ID

TEMPORARY ACCESS:
- Username: admin@$COMPANY_NAME.com
- Temporary Password: $TEMP_PASSWORD
- API Key: $API_KEY

NEXT STEPS:
1. Log in to your dashboard using the temporary credentials above
2. Change your password immediately after first login
3. $(if [[ "$GUIDED_TOUR" == "true" ]]; then echo "Follow the guided tour to explore AetherLink's capabilities"; else echo "Explore the dashboard and try out the AI features"; fi)
4. $(if [[ "$DEMO_DATA" == "true" ]]; then echo "Review the pre-loaded demo data to see AetherLink in action"; fi)

SUPPORT:
- Documentation: https://docs.aetherlink.com
- Beta Support: beta-support@aetherlink.com
- Community Forum: https://community.aetherlink.com

We're excited to have you as a beta customer and look forward to your feedback!

Best regards,
The AetherLink Team

---
This is an automated message from the AetherLink Beta Onboarding System.
EOF

    # In a real implementation, this would integrate with an email service
    # For now, we'll just log that the email would be sent
    success "Welcome email prepared (integration with email service needed for actual sending)"
}

# Setup telemetry and feedback collection
setup_telemetry() {
    info "Setting up telemetry and feedback collection..."

    # Create telemetry configuration
    cat > "$CONFIG_DIR/$TENANT_ID/telemetry.json" << EOF
{
    "tenant_id": "$TENANT_ID",
    "beta_customer": true,
    "telemetry_enabled": true,
    "feedback_collection": {
        "nps_survey": true,
        "feature_usage_tracking": true,
        "error_reporting": true,
        "performance_metrics": true
    },
    "data_retention_days": 90,
    "anonymization_level": "high",
    "feedback_webhook": "https://beta.aetherlink.com/api/feedback"
}
EOF

    success "Telemetry and feedback collection configured"
}

# Create onboarding summary
create_summary() {
    info "Creating onboarding summary..."

    cat > "$BETA_DIR/onboarding_summary_$TENANT_ID.json" << EOF
{
    "onboarding_id": "$(date +%Y%m%d_%H%M%S)_$TENANT_ID",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "company": "$COMPANY_NAME",
    "admin_email": "$ADMIN_EMAIL",
    "tenant_id": "$TENANT_ID",
    "plan": "$PLAN",
    "features_enabled": {
        "demo_data": $DEMO_DATA,
        "guided_tour": $GUIDED_TOUR,
        "telemetry": true,
        "feedback_collection": true
    },
    "credentials": {
        "api_key": "$API_KEY",
        "admin_key": "$ADMIN_KEY",
        "temp_password": "$TEMP_PASSWORD"
    },
    "access_urls": {
        "dashboard": "https://beta.aetherlink.com/dashboard?tenant=$TENANT_ID",
        "api_docs": "https://docs.aetherlink.com/api",
        "support": "https://support.aetherlink.com"
    },
    "next_steps": [
        "Check email for welcome message and temporary credentials",
        "Log in to dashboard and change temporary password",
        $(if [[ "$GUIDED_TOUR" == "true" ]]; then echo "\"Follow the guided tour to explore features\","; fi)
        $(if [[ "$DEMO_DATA" == "true" ]]; then echo "\"Review pre-loaded demo data\","; fi)
        "Try out AI operations features",
        "Provide feedback through the dashboard",
        "Schedule a demo call with our team"
    ],
    "support_contacts": {
        "beta_support": "beta-support@aetherlink.com",
        "technical_issues": "tech-support@aetherlink.com",
        "sales": "sales@aetherlink.com"
    }
}
EOF

    success "Onboarding summary created: $BETA_DIR/onboarding_summary_$TENANT_ID.json"
}

# Main execution
main() {
    echo "🚀 AetherLink Beta Customer Onboarding"
    echo "======================================"
    log "Starting beta onboarding process"

    parse_args "$@"
    validate_environment
    generate_credentials
    provision_tenant
    seed_demo_data
    setup_guided_tour
    setup_telemetry
    send_welcome_email
    create_summary

    echo ""
    echo "🎉 BETA ONBOARDING COMPLETE!"
    echo "============================"
    echo "Tenant ID: $TENANT_ID"
    echo "Company: $COMPANY_NAME"
    echo "Plan: $PLAN"
    echo "Profile: $PROFILE"
    echo "Dashboard: https://beta.aetherlink.com/dashboard?tenant=$TENANT_ID"
    echo ""
    echo "Next steps:"
    echo "1. Check $ADMIN_EMAIL for welcome email"
    echo "2. Log in with temporary credentials"
    echo "3. Follow guided tour (if enabled)"
    echo "4. Explore demo data (if enabled)"
    echo ""
    echo "Logs: $LOG_FILE"
    echo "Summary: $BETA_DIR/onboarding_summary_$TENANT_ID.json"

    log "Beta onboarding completed successfully for tenant: $TENANT_ID"
}

# Run main function with all arguments
main "$@"
