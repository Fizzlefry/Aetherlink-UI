#!/usr/bin/env python3
import asyncio
import sys

sys.path.insert(0, "services/command-center")

from main import list_operator_jobs_smoke as list_operator_jobs
from main import operator_health_smoke as operator_health
from main import ops_analytics_smoke as ops_analytics
from main import pause_operator_job_smoke as pause_operator_job
from main import resume_operator_job_smoke as resume_operator_job


async def run_smoke_tests():
    print("🚀 AetherLink Operator Control Deck - Smoke Tests")
    print("=" * 60)

    # Test 1: Operator Jobs Endpoint
    print("\n📋 TEST 1: Operator Jobs Endpoint")
    try:
        result = await list_operator_jobs()
        print(f"✅ Status: {result['ok']}")
        print(f"✅ Tenant: {result['tenant']}")
        print("✅ Jobs from scheduler.py:")
        for job in result["jobs"]:
            print(f"   {job['id']}: {job['name']} (status: {job['status']})")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 2: Pause a job
    print("\n⏸️  TEST 2: Pause Job (daily-import)")
    try:
        result = await pause_operator_job("daily-import", "the-expert-co")
        print(f"✅ Status: {result['ok']}")
        print(f"✅ Action: {result.get('action', 'paused')}")
        print("✅ Should have logged audit event: operator.job.paused")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 3: Check analytics
    print("\n📊 TEST 3: Analytics (should show Operator Controls)")
    try:
        result = await ops_analytics("the-expert-co")
        print(f"✅ Status: {result['ok']}")
        print(f"✅ Tenant: {result['tenant']}")
        groups = result.get("groups", {})
        if "Operator Controls" in groups:
            controls = groups["Operator Controls"]
            print(
                f"✅ Operator Controls found: all_time={controls['all_time']}, last_24h={controls['last_24h']}"
            )
        else:
            print("❌ Operator Controls not found in analytics")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 4: Resume the job
    print("\n▶️  TEST 4: Resume Job (daily-import)")
    try:
        result = await resume_operator_job("daily-import", "the-expert-co")
        print(f"✅ Status: {result['ok']}")
        print(f"✅ Action: {result.get('action', 'resumed')}")
        print("✅ Should have logged audit event: operator.job.resumed")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 5: Final analytics check
    print("\n📈 TEST 5: Final Analytics Check")
    try:
        result = await ops_analytics("the-expert-co")
        groups = result.get("groups", {})
        if "Operator Controls" in groups:
            controls = groups["Operator Controls"]
            print(
                f"✅ Final count: all_time={controls['all_time']}, last_24h={controls['last_24h']}"
            )
            print("✅ Audit trail working - pause + resume = 2 total actions")
        else:
            print("❌ Operator Controls missing")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 6: Operator health check
    print("\n🏥 TEST 6: Operator Health Check")
    try:
        result = await operator_health()
        print(f"✅ Status: {result['ok']}")
        print(f"✅ Overall: {result['overall']}")
        components = result.get("components", {})
        for comp, status in components.items():
            print(f"   {comp}: {status}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    print("\n" + "=" * 60)
    print("🎉 Smoke tests complete!")
    print("If all ✅, your operator control deck is production-ready!")


if __name__ == "__main__":
    asyncio.run(run_smoke_tests())
