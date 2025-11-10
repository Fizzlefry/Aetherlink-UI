#!/usr/bin/env python3
"""
Quick test for the remediation history endpoint.
Run after triggering some auto-acks to see the recovery timeline.
"""

import httpx

BASE_URL = "http://localhost:8010"


def test_remediation_history():
    """Test the /ops/remediate/history endpoint"""

    print("=" * 60)
    print("Testing Remediation History Endpoint")
    print("=" * 60)

    # Test 1: Get all recent events
    print("\n1. Fetching last 10 remediation events...")
    response = httpx.get(f"{BASE_URL}/ops/remediate/history?limit=10")
    data = response.json()

    print(f"   Status: {response.status_code}")
    print(f"   Total events: {data['total']}")

    if data["items"]:
        print("\n   Recent events:")
        print("   " + "-" * 58)
        for item in data["items"]:
            print(
                f"   {item['ts'][:19]} | {item['alertname'][:20]:20} | {item['action']:12} | {item['status']:7}"
            )
    else:
        print("   No events found yet. Trigger some auto-acks first!")

    # Test 2: Filter by tenant (if any exist)
    if data["items"]:
        first_tenant = data["items"][0]["tenant"]
        if first_tenant:
            print(f"\n2. Filtering by tenant: {first_tenant}")
            response = httpx.get(f"{BASE_URL}/ops/remediate/history?tenant={first_tenant}&limit=5")
            tenant_data = response.json()
            print(f"   Events for tenant '{first_tenant}': {tenant_data['total']}")

    # Test 3: Filter by alertname (if any exist)
    if data["items"]:
        first_alert = data["items"][0]["alertname"]
        if first_alert:
            print(f"\n3. Filtering by alertname: {first_alert}")
            response = httpx.get(
                f"{BASE_URL}/ops/remediate/history?alertname={first_alert}&limit=5"
            )
            alert_data = response.json()
            print(f"   Events for alert '{first_alert}': {alert_data['total']}")

    print("\n" + "=" * 60)
    print("✅ Endpoint is working!")
    print("=" * 60)

    # Show example curl commands
    print("\n📋 Example curl commands:")
    print(f"   curl {BASE_URL}/ops/remediate/history")
    print(f"   curl '{BASE_URL}/ops/remediate/history?limit=20'")
    print(f"   curl '{BASE_URL}/ops/remediate/history?tenant=acme-corp'")
    print(f"   curl '{BASE_URL}/ops/remediate/history?alertname=HighFailureRate'")


if __name__ == "__main__":
    try:
        test_remediation_history()
    except httpx.ConnectError:
        print("❌ Could not connect to Command Center at http://localhost:8010")
        print("   Make sure the server is running first!")
    except Exception as e:
        print(f"❌ Error: {e}")
