# provisioning/billing_integration.py
"""
AetherLink Billing Integration

Stripe-based billing system for SaaS subscriptions with usage tracking,
invoice generation, and payment processing.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# Mock Stripe integration (replace with actual stripe SDK in production)
class MockStripeClient:
    """Mock Stripe client for development/testing."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.customers: dict[str, dict[str, Any]] = {}
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.payment_methods: dict[str, dict[str, Any]] = {}

    def create_customer(self, email: str, name: str, metadata: dict[str, Any] | None = None) -> str:
        """Create a customer and return customer ID."""
        customer_id = f"cus_{len(self.customers) + 1}"
        self.customers[customer_id] = {
            "id": customer_id,
            "email": email,
            "name": name,
            "metadata": metadata or {},
            "created": datetime.now().isoformat(),
        }
        return customer_id

    def create_subscription(
        self, customer_id: str, price_id: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Create a subscription and return subscription ID."""
        subscription_id = f"sub_{len(self.subscriptions) + 1}"
        self.subscriptions[subscription_id] = {
            "id": subscription_id,
            "customer": customer_id,
            "status": "active",
            "current_period_start": datetime.now().isoformat(),
            "current_period_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "metadata": metadata or {},
        }
        return subscription_id

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Get customer details."""
        return self.customers.get(customer_id)

    def get_subscription(self, subscription_id: str) -> dict[str, Any] | None:
        """Get subscription details."""
        return self.subscriptions.get(subscription_id)

    def cancel_subscription(self, subscription_id: str):
        """Cancel a subscription."""
        if subscription_id in self.subscriptions:
            self.subscriptions[subscription_id]["status"] = "canceled"


class BillingService:
    """Billing service for subscription management and usage tracking."""

    # Pricing plans (in cents)
    PLANS = {
        "starter": {
            "name": "Starter",
            "price_monthly": 49900,  # $499
            "operations_limit": 10000,
            "ai_actions_limit": 1000,
            "stripe_price_id": "price_starter",
        },
        "professional": {
            "name": "Professional",
            "price_monthly": 249900,  # $2,499
            "operations_limit": 100000,
            "ai_actions_limit": 10000,
            "stripe_price_id": "price_professional",
        },
        "enterprise": {
            "name": "Enterprise",
            "price_monthly": 999900,  # $9,999
            "operations_limit": 1000000,
            "ai_actions_limit": 100000,
            "stripe_price_id": "price_enterprise",
        },
    }

    # Overage rates (per unit in cents)
    OVERAGE_RATES = {
        "operations": 5,  # $0.05 per operation over limit
        "ai_actions": 25,  # $0.25 per AI action over limit
    }

    def __init__(self, stripe_api_key: str | None = None):
        self.stripe_api_key = stripe_api_key or os.getenv("STRIPE_API_KEY", "sk_test_mock")
        self.stripe = MockStripeClient(self.stripe_api_key)
        self.usage_file = "provisioning/billing/usage.json"
        self.invoices_file = "provisioning/billing/invoices.json"
        os.makedirs("provisioning/billing", exist_ok=True)
        self._load_data()

    def _load_data(self):
        """Load billing data from disk."""
        self.usage_data = {}
        self.invoices = {}

        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file) as f:
                    self.usage_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load usage data: {e}")

        if os.path.exists(self.invoices_file):
            try:
                with open(self.invoices_file) as f:
                    self.invoices = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load invoices: {e}")

    def _save_data(self):
        """Save billing data to disk."""
        with open(self.usage_file, "w") as f:
            json.dump(self.usage_data, f, indent=2)

        with open(self.invoices_file, "w") as f:
            json.dump(self.invoices, f, indent=2)

    def create_subscription(
        self, tenant_id: str, plan_id: str, billing_email: str, organization_name: str
    ) -> dict[str, Any]:
        """
        Create a new subscription for a tenant.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan identifier (starter, professional, enterprise)
            billing_email: Email for billing
            organization_name: Organization name

        Returns:
            Subscription details
        """
        if plan_id not in self.PLANS:
            raise ValueError(f"Invalid plan: {plan_id}")

        # Create Stripe customer
        customer_id = self.stripe.create_customer(
            email=billing_email, name=organization_name, metadata={"tenant_id": tenant_id}
        )

        # Create subscription
        price_id = self.PLANS[plan_id]["stripe_price_id"]
        subscription_id = self.stripe.create_subscription(
            customer_id=customer_id,
            price_id=price_id,
            metadata={"tenant_id": tenant_id, "plan_id": plan_id},
        )

        # Initialize usage tracking
        self.usage_data[tenant_id] = {
            "plan_id": plan_id,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "billing_email": billing_email,
            "current_period_start": datetime.now().isoformat(),
            "current_period_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "usage": {"operations": 0, "ai_actions": 0, "api_calls": 0, "storage_used_gb": 0},
            "limits": {
                "operations": self.PLANS[plan_id]["operations_limit"],
                "ai_actions": self.PLANS[plan_id]["ai_actions_limit"],
            },
        }

        self._save_data()

        logger.info(f"Created subscription for tenant {tenant_id}: {subscription_id}")
        return {
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "plan_id": plan_id,
            "status": "active",
            "current_period_end": self.usage_data[tenant_id]["current_period_end"],
        }

    def record_usage(self, tenant_id: str, metric: str, amount: int = 1):
        """
        Record usage for a tenant.

        Args:
            tenant_id: Tenant identifier
            metric: Usage metric (operations, ai_actions, api_calls, storage_used_gb)
            amount: Amount to add to usage
        """
        if tenant_id not in self.usage_data:
            logger.warning(f"No billing data for tenant: {tenant_id}")
            return

        if metric not in self.usage_data[tenant_id]["usage"]:
            logger.warning(f"Unknown metric: {metric}")
            return

        self.usage_data[tenant_id]["usage"][metric] += amount
        self._save_data()

    def get_usage_summary(self, tenant_id: str) -> dict[str, Any] | None:
        """Get usage summary for a tenant."""
        if tenant_id not in self.usage_data:
            return None

        data = self.usage_data[tenant_id]
        usage = data["usage"]
        limits = data["limits"]

        # Calculate overage
        overage = {}
        for metric in ["operations", "ai_actions"]:
            if metric in limits and usage[metric] > limits[metric]:
                overage[metric] = usage[metric] - limits[metric]

        return {
            "plan_id": data["plan_id"],
            "current_period_start": data["current_period_start"],
            "current_period_end": data["current_period_end"],
            "usage": usage,
            "limits": limits,
            "overage": overage,
            "estimated_cost": self._calculate_estimated_cost(tenant_id),
        }

    def _calculate_estimated_cost(self, tenant_id: str) -> float:
        """Calculate estimated monthly cost including overage."""
        if tenant_id not in self.usage_data:
            return 0.0

        data = self.usage_data[tenant_id]
        plan_id = data["plan_id"]
        usage = data["usage"]

        # Base plan cost
        base_cost = self.PLANS[plan_id]["price_monthly"] / 100.0  # Convert cents to dollars

        # Calculate overage costs
        overage_cost = 0.0
        for metric, rate in self.OVERAGE_RATES.items():
            limit = data["limits"].get(metric, 0)
            if usage[metric] > limit:
                overage_amount = usage[metric] - limit
                overage_cost += (overage_amount * rate) / 100.0  # Convert cents to dollars

        return base_cost + overage_cost

    def generate_invoice(self, tenant_id: str) -> dict[str, Any] | None:
        """Generate an invoice for the current billing period."""
        if tenant_id not in self.usage_data:
            return None

        usage_summary = self.get_usage_summary(tenant_id)
        if not usage_summary:
            return None

        invoice_id = f"inv_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        invoice = {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
            "period_start": usage_summary["current_period_start"],
            "period_end": usage_summary["current_period_end"],
            "plan_id": usage_summary["plan_id"],
            "base_cost": self.PLANS[usage_summary["plan_id"]]["price_monthly"] / 100.0,
            "usage": usage_summary["usage"],
            "overage": usage_summary["overage"],
            "total_cost": usage_summary["estimated_cost"],
            "status": "pending",
            "generated_at": datetime.now().isoformat(),
        }

        self.invoices[invoice_id] = invoice
        self._save_data()

        return invoice

    def cancel_subscription(self, tenant_id: str):
        """Cancel a tenant's subscription."""
        if tenant_id in self.usage_data:
            subscription_id = self.usage_data[tenant_id]["subscription_id"]
            self.stripe.cancel_subscription(subscription_id)
            self.usage_data[tenant_id]["status"] = "cancelled"
            self._save_data()
            logger.info(f"Cancelled subscription for tenant: {tenant_id}")

    def list_invoices(self, tenant_id: str) -> list[dict[str, Any]]:
        """List all invoices for a tenant."""
        return [inv for inv in self.invoices.values() if inv["tenant_id"] == tenant_id]


# Global billing service instance
billing_service = BillingService()

# CLI Interface for billing management
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AetherLink Billing Management")
    parser.add_argument("action", choices=["create", "usage", "invoice", "cancel", "list"])
    parser.add_argument("--tenant-id", required=True, help="Tenant ID")
    parser.add_argument("--plan", default="starter", help="Subscription plan")
    parser.add_argument("--email", help="Billing email")
    parser.add_argument("--org", help="Organization name")
    parser.add_argument("--metric", help="Usage metric")
    parser.add_argument("--amount", type=int, default=1, help="Usage amount")

    args = parser.parse_args()

    if args.action == "create":
        if not args.email or not args.org:
            print("Error: --email and --org required for create")
            exit(1)

        result = billing_service.create_subscription(
            tenant_id=args.tenant_id,
            plan_id=args.plan,
            billing_email=args.email,
            organization_name=args.org,
        )
        print(f"✅ Created subscription: {result['subscription_id']}")

    elif args.action == "usage":
        if not args.metric:
            print("Error: --metric required for usage")
            exit(1)

        billing_service.record_usage(args.tenant_id, args.metric, args.amount)
        print(f"✅ Recorded {args.amount} {args.metric} for tenant {args.tenant_id}")

    elif args.action == "invoice":
        invoice = billing_service.generate_invoice(args.tenant_id)
        if invoice:
            print(f"✅ Generated invoice: {invoice['invoice_id']}")
            print(f"   Total: ${invoice['total_cost']:.2f}")
        else:
            print("❌ Failed to generate invoice")

    elif args.action == "cancel":
        billing_service.cancel_subscription(args.tenant_id)
        print(f"✅ Cancelled subscription for tenant {args.tenant_id}")

    elif args.action == "list":
        invoices = billing_service.list_invoices(args.tenant_id)
        print(f"Invoices for tenant {args.tenant_id}:")
        for inv in invoices:
            print(f"  {inv['invoice_id']}: ${inv['total_cost']:.2f} ({inv['status']})")
