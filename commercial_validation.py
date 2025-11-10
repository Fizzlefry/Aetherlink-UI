#!/usr/bin/env python3
"""
AetherLink Commercial Deployment Validation

Comprehensive end-to-end testing of the commercial deployment including:
- Multi-tenant provisioning
- Billing integration
- Resource quota enforcement
- Tenant isolation
- Support workflow validation
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

import requests

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from provisioning.billing_integration import BillingService
from provisioning.tenant_provisioning import TenantProvisioningService


class CommercialValidation:
    """Comprehensive commercial deployment validation."""

    def __init__(self):
        self.provisioning = TenantProvisioningService()
        self.billing = BillingService()
        self.base_url = "http://localhost:8000"
        self.test_results = []
        self.tenants_created = []

    def log_result(
        self, test_name: str, success: bool, message: str, details: dict[str, Any] = None
    ):
        """Log a test result."""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name} - {message}")

    def test_tenant_provisioning(self):
        """Test tenant provisioning functionality."""
        print("\n🔧 Testing Tenant Provisioning...")

        # Test 1: Create starter tenant
        try:
            tenant_id = "VALIDATION_STARTER"
            result = self.provisioning.provision_tenant(
                name="Validation Corp",
                domain="validation.com",
                plan="starter",
                billing_email="billing@validation.com",
            )
            # Store the actual tenant ID returned
            actual_tenant_id = result.tenant_id if hasattr(result, "tenant_id") else tenant_id
            self.tenants_created.append(actual_tenant_id)
            self.log_result(
                "Tenant Creation - Starter",
                True,
                f"Created tenant {actual_tenant_id}",
                {"tenant_id": actual_tenant_id},
            )
        except Exception as e:
            self.log_result(
                "Tenant Creation - Starter", False, f"Failed to create starter tenant: {str(e)}"
            )

        # Test 2: Create enterprise tenant
        try:
            tenant_id = "VALIDATION_ENTERPRISE"
            result = self.provisioning.provision_tenant(
                name="Enterprise Validation Inc",
                domain="enterprise-validation.com",
                plan="enterprise",
                billing_email="billing@enterprise-validation.com",
            )
            # Store the actual tenant ID returned
            actual_tenant_id = result.tenant_id if hasattr(result, "tenant_id") else tenant_id
            self.tenants_created.append(actual_tenant_id)
            self.log_result(
                "Tenant Creation - Enterprise",
                True,
                f"Created tenant {actual_tenant_id}",
                {"tenant_id": actual_tenant_id},
            )
        except Exception as e:
            self.log_result(
                "Tenant Creation - Enterprise",
                False,
                f"Failed to create enterprise tenant: {str(e)}",
            )

        # Test 3: Verify tenant configuration files
        for tenant_id in self.tenants_created:
            config_file = f"provisioning/config/{tenant_id}/.env"
            if os.path.exists(config_file):
                with open(config_file) as f:
                    content = f.read()
                self.log_result(
                    f"Tenant Config - {tenant_id}",
                    True,
                    "Configuration file created",
                    {"file": config_file, "size": len(content)},
                )
            else:
                self.log_result(f"Tenant Config - {tenant_id}", False, "Configuration file missing")

    def test_billing_integration(self):
        """Test billing system integration."""
        print("\n💳 Testing Billing Integration...")

        # Test 1: Create subscription
        try:
            result = self.billing.create_subscription(
                tenant_id="VALIDATION_STARTER",
                plan_id="starter",
                billing_email="billing@validation.com",
                organization_name="Validation Corp",
            )
            self.log_result("Billing Subscription", True, "Created subscription", result)
        except Exception as e:
            self.log_result(
                "Billing Subscription", False, f"Failed to create subscription: {str(e)}"
            )

        # Test 2: Record usage
        try:
            self.billing.record_usage("VALIDATION_STARTER", "operations", 500)
            self.billing.record_usage("VALIDATION_STARTER", "ai_actions", 50)
            self.log_result("Usage Recording", True, "Recorded usage metrics")
        except Exception as e:
            self.log_result("Usage Recording", False, f"Failed to record usage: {str(e)}")

        # Test 3: Get usage summary
        try:
            summary = self.billing.get_usage_summary("VALIDATION_STARTER")
            if summary:
                self.log_result("Usage Summary", True, "Retrieved usage summary", summary)
            else:
                self.log_result("Usage Summary", False, "No usage summary returned")
        except Exception as e:
            self.log_result("Usage Summary", False, f"Failed to get usage summary: {str(e)}")

        # Test 4: Generate invoice
        try:
            invoice = self.billing.generate_invoice("VALIDATION_STARTER")
            if invoice:
                self.log_result("Invoice Generation", True, "Generated invoice", invoice)
            else:
                self.log_result("Invoice Generation", False, "No invoice generated")
        except Exception as e:
            self.log_result("Invoice Generation", False, f"Failed to generate invoice: {str(e)}")

    def test_tenant_isolation(self):
        """Test tenant isolation and resource quotas."""
        print("\n🔒 Testing Tenant Isolation...")

        # Test 1: Verify tenant directories are separate
        tenant_dirs = []
        for tenant_id in self.tenants_created:
            tenant_dir = f"provisioning/config/{tenant_id}"
            if os.path.exists(tenant_dir):
                tenant_dirs.append(tenant_dir)
                # Check for required files
                required_files = [".env", "docker-compose.override.yml"]
                missing_files = []
                for file in required_files:
                    if not os.path.exists(f"{tenant_dir}/{file}"):
                        missing_files.append(file)
                if missing_files:
                    self.log_result(
                        f"Tenant Files - {tenant_id}", False, f"Missing files: {missing_files}"
                    )
                else:
                    self.log_result(
                        f"Tenant Files - {tenant_id}", True, "All required files present"
                    )
            else:
                self.log_result(
                    f"Tenant Directory - {tenant_id}", False, "Tenant directory missing"
                )

        # Test 2: Verify resource limits are enforced (check .env file for limits)
        for tenant_id in self.tenants_created:
            env_file = f"provisioning/config/{tenant_id}/.env"
            if os.path.exists(env_file):
                with open(env_file) as f:
                    content = f.read()
                # Check for key limit variables
                limits_found = []
                if "MAX_OPERATIONS_PER_MONTH" in content:
                    limits_found.append("operations")
                if "MAX_AI_ACTIONS_PER_MONTH" in content:
                    limits_found.append("ai_actions")
                if "MAX_USERS" in content:
                    limits_found.append("users")

                if len(limits_found) >= 3:
                    self.log_result(
                        f"Resource Limits - {tenant_id}", True, f"Limits configured: {limits_found}"
                    )
                else:
                    self.log_result(
                        f"Resource Limits - {tenant_id}",
                        False,
                        f"Missing limits: expected 3, found {len(limits_found)}",
                    )
            else:
                self.log_result(f"Resource Limits - {tenant_id}", False, "Environment file missing")

    def test_api_integration(self):
        """Test API integration with tenant context."""
        print("\n🔗 Testing API Integration...")

        # Test 1: Health check
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                self.log_result("API Health Check", True, "API is healthy")
            else:
                self.log_result(
                    "API Health Check", False, f"API returned status {response.status_code}"
                )
        except Exception as e:
            self.log_result("API Health Check", False, f"API health check failed: {str(e)}")

        # Test 2: Tenant-specific operations (mock)
        for tenant_id in self.tenants_created:
            try:
                # Load tenant API key from .env file
                env_file = f"provisioning/config/{tenant_id}/.env"
                api_key = None
                if os.path.exists(env_file):
                    with open(env_file) as f:
                        for line in f:
                            if line.startswith("API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break

                if api_key:
                    headers = {"x-api-key": api_key}
                    # Test chat endpoint (if available)
                    try:
                        response = requests.post(
                            f"{self.base_url}/chat",
                            headers=headers,
                            json={"message": "Test message for validation"},
                            timeout=10,
                        )
                        if response.status_code in [200, 201]:
                            self.log_result(
                                f"API Chat - {tenant_id}", True, "Chat endpoint accessible"
                            )
                        else:
                            self.log_result(
                                f"API Chat - {tenant_id}",
                                False,
                                f"Chat returned status {response.status_code}",
                            )
                    except Exception as e:
                        self.log_result(
                            f"API Chat - {tenant_id}", False, f"Chat test failed: {str(e)}"
                        )
                else:
                    self.log_result(
                        f"API Keys - {tenant_id}", False, "No API key found in .env file"
                    )
            except Exception as e:
                self.log_result(
                    f"API Integration - {tenant_id}", False, f"API test failed: {str(e)}"
                )

    def test_support_workflow(self):
        """Test support workflow and documentation."""
        print("\n📞 Testing Support Workflow...")

        # Test 1: Check documentation exists
        docs_to_check = [
            "COMMERCIAL_LICENSING.md",
            "ENTERPRISE_SUPPORT_PLAN.md",
            "COMMERCIAL_PRESENTATION.md",
            "README.md",
        ]

        for doc in docs_to_check:
            if os.path.exists(doc):
                # Check file size (basic validation)
                size = os.path.getsize(doc)
                if size > 1000:  # At least 1KB
                    self.log_result(
                        f"Documentation - {doc}", True, f"Documentation exists ({size} bytes)"
                    )
                else:
                    self.log_result(f"Documentation - {doc}", False, "Documentation too small")
            else:
                self.log_result(f"Documentation - {doc}", False, "Documentation missing")

        # Test 2: Check provisioning scripts
        scripts_to_check = [
            "provisioning/tenant_provisioning.py",
            "provisioning/billing_integration.py",
        ]

        for script in scripts_to_check:
            if os.path.exists(script):
                # Try to import/run basic validation
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "py_compile", script],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        self.log_result(
                            f"Script Validation - {script}", True, "Script compiles successfully"
                        )
                    else:
                        self.log_result(
                            f"Script Validation - {script}",
                            False,
                            f"Script compilation failed: {result.stderr}",
                        )
                except Exception as e:
                    self.log_result(
                        f"Script Validation - {script}",
                        False,
                        f"Script validation failed: {str(e)}",
                    )
            else:
                self.log_result(f"Script - {script}", False, "Script missing")

    def cleanup(self):
        """Clean up test tenants and data."""
        print("\n🧹 Cleaning up test data...")

        for tenant_id in self.tenants_created:
            try:
                # Remove tenant directory
                tenant_dir = f"provisioning/tenants/{tenant_id}"
                if os.path.exists(tenant_dir):
                    import shutil

                    shutil.rmtree(tenant_dir)
                    self.log_result(f"Cleanup - {tenant_id}", True, "Tenant directory removed")
                else:
                    self.log_result(
                        f"Cleanup - {tenant_id}", True, "Tenant directory already removed"
                    )
            except Exception as e:
                self.log_result(f"Cleanup - {tenant_id}", False, f"Cleanup failed: {str(e)}")

        # Clean up billing data
        try:
            for tenant_id in self.tenants_created:
                self.billing.cancel_subscription(tenant_id)
            self.log_result("Billing Cleanup", True, "Billing data cleaned up")
        except Exception as e:
            self.log_result("Billing Cleanup", False, f"Billing cleanup failed: {str(e)}")

    def run_all_tests(self):
        """Run all validation tests."""
        print("🚀 Starting AetherLink Commercial Deployment Validation")
        print("=" * 60)

        start_time = time.time()

        # Run all test suites
        self.test_tenant_provisioning()
        self.test_billing_integration()
        self.test_tenant_isolation()
        self.test_api_integration()
        self.test_support_workflow()

        # Calculate results
        end_time = time.time()
        duration = end_time - start_time

        passed = sum(1 for r in self.test_results if r["success"])
        total = len(self.test_results)

        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {passed/total*100:.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        # Save detailed results
        results_file = f"commercial_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total_tests": total,
                        "passed": passed,
                        "failed": total - passed,
                        "success_rate": passed / total if total > 0 else 0,
                        "duration_seconds": duration,
                    },
                    "results": self.test_results,
                },
                f,
                indent=2,
            )

        print(f"📄 Detailed results saved to: {results_file}")

        # Cleanup
        self.cleanup()

        return passed == total


def main():
    """Main validation entry point."""
    validator = CommercialValidation()
    success = validator.run_all_tests()

    if success:
        print("\n🎉 COMMERCIAL DEPLOYMENT VALIDATION PASSED!")
        print("AetherLink is ready for commercial deployment.")
        sys.exit(0)
    else:
        print("\n❌ COMMERCIAL DEPLOYMENT VALIDATION FAILED!")
        print("Please review the test results and fix any issues before deployment.")
        sys.exit(1)


if __name__ == "__main__":
    main()
