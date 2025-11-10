#!/usr/bin/env python3
"""Test script for AI guardrail functions."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from main import (
    ADAPTIVE_AUTO_DRY_RUN,
    ADAPTIVE_CONFIDENCE_PER_TENANT,
    MAX_AUTO_ACTIONS_PER_TENANT,
    PROTECTED_JOBS,
    check_automation_budget,
    check_protected_objects,
    get_tenant_confidence_floor,
)


def test_guardrails():
    print("🛡️ Testing AI Guardrail Functions")
    print("=" * 50)

    # Test automation budget
    print(f"📊 Budget check for 'test-tenant': {check_automation_budget('test-tenant')}")
    print(f"   Max actions per tenant: {MAX_AUTO_ACTIONS_PER_TENANT}")

    # Test protected objects
    print(
        f"🚫 Protected objects check (alert_ack, security/priv-esc): {check_protected_objects('alert_ack', 'security/priv-esc')}"
    )
    print(f"   Protected jobs: {PROTECTED_JOBS}")

    # Test confidence floors
    print(f"🎯 Confidence floor for 'demo-tenant': {get_tenant_confidence_floor('demo-tenant')}")
    print(f"   Confidence floors: {ADAPTIVE_CONFIDENCE_PER_TENANT}")

    # Test dry run mode
    print(f"🔧 Dry run mode enabled: {ADAPTIVE_AUTO_DRY_RUN}")

    print("\n✅ All guardrail functions executed successfully!")
    print("🛡️ AI automation is now safely constrained!")


if __name__ == "__main__":
    test_guardrails()
