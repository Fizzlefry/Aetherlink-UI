# provisioning/tenant_provisioning.py
"""
AetherLink Tenant Provisioning System

Automated tenant setup, billing integration, and resource management for
commercial deployments of the AI Operations Brain.
"""

import json
import logging
import os
import secrets
import string
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TenantLimits:
    """Resource limits for a tenant."""

    max_operations_per_month: int = 10000
    max_ai_actions_per_month: int = 1000
    max_alerts_per_day: int = 1000
    max_api_calls_per_minute: int = 60
    max_storage_gb: int = 10
    max_users: int = 5


@dataclass
class TenantBilling:
    """Billing configuration for a tenant."""

    stripe_customer_id: str | None = None
    subscription_id: str | None = None
    plan_id: str = "starter"
    billing_email: str = ""
    payment_method: str | None = None
    next_billing_date: datetime | None = None
    usage_this_month: dict[str, int] = None

    def __post_init__(self):
        if self.usage_this_month is None:
            self.usage_this_month = {
                "operations": 0,
                "ai_actions": 0,
                "api_calls": 0,
                "storage_used_gb": 0,
            }


@dataclass
class TenantConfig:
    """Complete tenant configuration."""

    tenant_id: str
    name: str
    domain: str
    api_key: str
    admin_key: str
    created_at: datetime
    status: str = "active"  # active, suspended, cancelled
    limits: TenantLimits = None
    billing: TenantBilling = None
    features: dict[str, bool] = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.limits is None:
            self.limits = TenantLimits()
        if self.billing is None:
            self.billing = TenantBilling()
        if self.features is None:
            self.features = {
                "ai_operations_brain": True,
                "autonomous_actions": True,
                "learning_optimizer": True,
                "audit_trails": True,
                "multi_tenant": False,
                "custom_integrations": False,
                "advanced_analytics": False,
                "federated_operations": False,
                "custom_ai_models": False,
                "white_label": False,
            }
        if self.metadata is None:
            self.metadata = {}


class TenantProvisioningService:
    """Service for automated tenant provisioning and management."""

    def __init__(self, config_dir: str = "provisioning/config"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
        self.tenants_file = os.path.join(config_dir, "tenants.json")
        self._load_tenants()

    def _load_tenants(self):
        """Load tenant configurations from disk."""
        if os.path.exists(self.tenants_file):
            try:
                with open(self.tenants_file) as f:
                    data = json.load(f)
                    self.tenants = {}
                    for tenant_id, tenant_data in data.items():
                        # Convert datetime strings back to datetime objects
                        if "created_at" in tenant_data:
                            tenant_data["created_at"] = datetime.fromisoformat(
                                tenant_data["created_at"]
                            )
                        if tenant_data.get("billing", {}).get("next_billing_date"):
                            tenant_data["billing"]["next_billing_date"] = datetime.fromisoformat(
                                tenant_data["billing"]["next_billing_date"]
                            )
                        # Convert billing dict back to TenantBilling object
                        if "billing" in tenant_data:
                            billing_dict = tenant_data["billing"]
                            if isinstance(billing_dict, dict):
                                tenant_data["billing"] = TenantBilling(**billing_dict)
                        self.tenants[tenant_id] = TenantConfig(**tenant_data)
            except Exception as e:
                logger.error(f"Failed to load tenants: {e}")
                self.tenants = {}
        else:
            self.tenants = {}

    def _save_tenants(self):
        """Save tenant configurations to disk."""
        data = {}
        for tenant_id, tenant in self.tenants.items():
            tenant_dict = asdict(tenant)
            # Convert datetime objects to ISO strings
            tenant_dict["created_at"] = tenant.created_at.isoformat()
            if tenant.billing.next_billing_date:
                tenant_dict["billing"]["next_billing_date"] = (
                    tenant.billing.next_billing_date.isoformat()
                )
            data[tenant_id] = tenant_dict

        with open(self.tenants_file, "w") as f:
            json.dump(data, f, indent=2)

    def generate_api_key(self, length: int = 32) -> str:
        """Generate a secure API key."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def provision_tenant(
        self, name: str, domain: str, plan: str = "starter", billing_email: str = ""
    ) -> TenantConfig:
        """
        Provision a new tenant with automated setup.

        Args:
            name: Organization name
            domain: Primary domain
            plan: Subscription plan (starter, professional, enterprise, enterprise_plus)
            billing_email: Email for billing notifications

        Returns:
            TenantConfig: Complete tenant configuration
        """
        tenant_id = f"tenant_{secrets.token_hex(8)}"
        api_key = self.generate_api_key()
        admin_key = self.generate_api_key()

        # Set limits based on plan
        limits = self._get_plan_limits(plan)

        # Set features based on plan
        features = self._get_plan_features(plan)

        # Create billing config
        billing = TenantBilling(plan_id=plan, billing_email=billing_email)

        tenant = TenantConfig(
            tenant_id=tenant_id,
            name=name,
            domain=domain,
            api_key=api_key,
            admin_key=admin_key,
            created_at=datetime.now(),
            limits=limits,
            billing=billing,
            features=features,
        )

        self.tenants[tenant_id] = tenant
        self._save_tenants()

        # Create tenant-specific configuration files
        self._create_tenant_config_files(tenant)

        logger.info(f"Provisioned new tenant: {tenant_id} ({name})")
        return tenant

    def _get_plan_limits(self, plan: str) -> TenantLimits:
        """Get resource limits for a plan."""
        limits_map = {
            "starter": TenantLimits(
                max_operations_per_month=10000,
                max_ai_actions_per_month=1000,
                max_alerts_per_day=1000,
                max_api_calls_per_minute=60,
                max_storage_gb=10,
                max_users=5,
            ),
            "professional": TenantLimits(
                max_operations_per_month=100000,
                max_ai_actions_per_month=10000,
                max_alerts_per_day=5000,
                max_api_calls_per_minute=300,
                max_storage_gb=100,
                max_users=25,
            ),
            "enterprise": TenantLimits(
                max_operations_per_month=1000000,
                max_ai_actions_per_month=100000,
                max_alerts_per_day=50000,
                max_api_calls_per_minute=1000,
                max_storage_gb=1000,
                max_users=100,
            ),
            "enterprise_plus": TenantLimits(
                max_operations_per_month=10000000,  # 10M
                max_ai_actions_per_month=1000000,  # 1M
                max_alerts_per_day=100000,
                max_api_calls_per_minute=5000,
                max_storage_gb=10000,
                max_users=1000,
            ),
        }
        return limits_map.get(plan, limits_map["starter"])

    def _get_plan_features(self, plan: str) -> dict[str, bool]:
        """Get feature flags for a plan."""
        base_features = {
            "ai_operations_brain": True,
            "autonomous_actions": True,
            "learning_optimizer": True,
            "audit_trails": True,
        }

        plan_features = {
            "starter": {
                **base_features,
                "multi_tenant": False,
                "custom_integrations": False,
                "advanced_analytics": False,
                "federated_operations": False,
                "custom_ai_models": False,
                "white_label": False,
            },
            "professional": {
                **base_features,
                "multi_tenant": True,
                "custom_integrations": True,
                "advanced_analytics": True,
                "federated_operations": False,
                "custom_ai_models": False,
                "white_label": False,
            },
            "enterprise": {
                **base_features,
                "multi_tenant": True,
                "custom_integrations": True,
                "advanced_analytics": True,
                "federated_operations": True,
                "custom_ai_models": True,
                "white_label": False,
            },
            "enterprise_plus": {
                **base_features,
                "multi_tenant": True,
                "custom_integrations": True,
                "advanced_analytics": True,
                "federated_operations": True,
                "custom_ai_models": True,
                "white_label": True,
            },
        }
        return plan_features.get(plan, plan_features["starter"])

    def _create_tenant_config_files(self, tenant: TenantConfig):
        """Create tenant-specific configuration files."""
        tenant_dir = os.path.join(self.config_dir, tenant.tenant_id)
        os.makedirs(tenant_dir, exist_ok=True)

        # Create environment file
        env_file = os.path.join(tenant_dir, ".env")
        with open(env_file, "w") as f:
            f.write(f"# AetherLink Tenant Configuration: {tenant.name}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"TENANT_ID={tenant.tenant_id}\n")
            f.write(f"TENANT_NAME={tenant.name}\n")
            f.write(f"TENANT_DOMAIN={tenant.domain}\n")
            f.write(f"API_KEY={tenant.api_key}\n")
            f.write(f"ADMIN_KEY={tenant.admin_key}\n")
            f.write(f"PLAN_ID={tenant.billing.plan_id}\n")
            f.write(f"BILLING_EMAIL={tenant.billing.billing_email}\n\n")
            f.write("# Resource Limits\n")
            f.write(f"MAX_OPERATIONS_PER_MONTH={tenant.limits.max_operations_per_month}\n")
            f.write(f"MAX_AI_ACTIONS_PER_MONTH={tenant.limits.max_ai_actions_per_month}\n")
            f.write(f"MAX_ALERTS_PER_DAY={tenant.limits.max_alerts_per_day}\n")
            f.write(f"MAX_API_CALLS_PER_MINUTE={tenant.limits.max_api_calls_per_minute}\n")
            f.write(f"MAX_STORAGE_GB={tenant.limits.max_storage_gb}\n")
            f.write(f"MAX_USERS={tenant.limits.max_users}\n")

        # Create docker-compose override for tenant
        compose_file = os.path.join(tenant_dir, "docker-compose.override.yml")
        with open(compose_file, "w") as f:
            f.write(f"""version: '3.8'

# Tenant-specific configuration for {tenant.name}
# Apply with: docker compose -f docker-compose.yml -f {tenant.tenant_id}/docker-compose.override.yml up

services:
  command-center:
    environment:
      - TENANT_ID={tenant.tenant_id}
      - TENANT_NAME={tenant.name}
      - TENANT_DOMAIN={tenant.domain}
      - API_KEY={tenant.api_key}
      - ADMIN_KEY={tenant.admin_key}
      - PLAN_ID={tenant.billing.plan_id}
      - MAX_OPERATIONS_PER_MONTH={tenant.limits.max_operations_per_month}
      - MAX_AI_ACTIONS_PER_MONTH={tenant.limits.max_ai_actions_per_month}
      - MAX_ALERTS_PER_DAY={tenant.limits.max_alerts_per_day}
      - MAX_API_CALLS_PER_MINUTE={tenant.limits.max_api_calls_per_minute}
      - MAX_STORAGE_GB={tenant.limits.max_storage_gb}
      - MAX_USERS={tenant.limits.max_users}
    volumes:
      - ./data/{tenant.tenant_id}:/app/data
      - ./audit/{tenant.tenant_id}:/app/audit
""")

    def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        """Get tenant configuration by ID."""
        return self.tenants.get(tenant_id)

    def list_tenants(self) -> list[TenantConfig]:
        """List all tenants."""
        return list(self.tenants.values())

    def update_tenant_limits(self, tenant_id: str, limits: TenantLimits):
        """Update tenant resource limits."""
        if tenant_id in self.tenants:
            self.tenants[tenant_id].limits = limits
            self._save_tenants()
            self._create_tenant_config_files(self.tenants[tenant_id])
            logger.info(f"Updated limits for tenant: {tenant_id}")

    def suspend_tenant(self, tenant_id: str):
        """Suspend a tenant."""
        if tenant_id in self.tenants:
            self.tenants[tenant_id].status = "suspended"
            self._save_tenants()
            logger.info(f"Suspended tenant: {tenant_id}")

    def reactivate_tenant(self, tenant_id: str):
        """Reactivate a suspended tenant."""
        if tenant_id in self.tenants:
            self.tenants[tenant_id].status = "active"
            self._save_tenants()
            logger.info(f"Reactivated tenant: {tenant_id}")

    def delete_tenant(self, tenant_id: str):
        """Delete a tenant (soft delete - mark as cancelled)."""
        if tenant_id in self.tenants:
            self.tenants[tenant_id].status = "cancelled"
            self._save_tenants()
            logger.info(f"Cancelled tenant: {tenant_id}")


# Global provisioning service instance
provisioning_service = TenantProvisioningService()

# CLI Interface for tenant management
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AetherLink Tenant Provisioning")
    parser.add_argument("action", choices=["create", "list", "suspend", "reactivate", "delete"])
    parser.add_argument("--tenant-id", help="Tenant ID for operations")
    parser.add_argument("--name", help="Organization name")
    parser.add_argument("--domain", help="Primary domain")
    parser.add_argument("--plan", default="starter", help="Subscription plan")
    parser.add_argument("--email", help="Billing email")

    args = parser.parse_args()

    if args.action == "create":
        if not args.name or not args.domain:
            print("Error: --name and --domain required for create")
            exit(1)

        tenant = provisioning_service.provision_tenant(
            name=args.name, domain=args.domain, plan=args.plan, billing_email=args.email or ""
        )

        print(f"✅ Created tenant: {tenant.tenant_id}")
        print(f"   Name: {tenant.name}")
        print(f"   Domain: {tenant.domain}")
        print(f"   API Key: {tenant.api_key}")
        print(f"   Admin Key: {tenant.admin_key}")
        print(f"   Plan: {tenant.billing.plan_id}")

    elif args.action == "list":
        tenants = provisioning_service.list_tenants()
        print(f"Found {len(tenants)} tenants:")
        for tenant in tenants:
            print(
                f"  {tenant.tenant_id}: {tenant.name} ({tenant.status}) - {tenant.billing.plan_id}"
            )

    elif args.action in ["suspend", "reactivate", "delete"]:
        if not args.tenant_id:
            print("Error: --tenant-id required")
            exit(1)

        if args.action == "suspend":
            provisioning_service.suspend_tenant(args.tenant_id)
            print(f"✅ Suspended tenant: {args.tenant_id}")
        elif args.action == "reactivate":
            provisioning_service.reactivate_tenant(args.tenant_id)
            print(f"✅ Reactivated tenant: {args.tenant_id}")
        elif args.action == "delete":
            provisioning_service.delete_tenant(args.tenant_id)
            print(f"✅ Cancelled tenant: {args.tenant_id}")
