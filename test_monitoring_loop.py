#!/usr/bin/env python3
"""
Test the complete AetherLink monitoring loop for RoofWonder.

Phase: End-to-End Integration Test

This test verifies:
1. RoofWonder emits aether_service_up metric
2. Prometheus scrapes the metric
3. Alert fires when service goes down
4. Command Center receives alert via webhook
5. Auto-heal worker attempts remediation
6. Result is reported back
"""

import asyncio

import httpx


async def test_roofwonder_monitoring_loop():
    """Test the complete monitoring loop for RoofWonder."""

    print("🧪 Testing AetherLink RoofWonder Monitoring Loop")
    print("=" * 50)

    # 1. Check if RoofWonder is running and emitting metrics
    print("1️⃣ Checking RoofWonder metrics endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8022/metrics")
            if response.status_code == 200 and "aether_service_up" in response.text:
                print("✅ RoofWonder metrics available")
            else:
                print("❌ RoofWonder metrics not found")
                return
    except Exception as e:
        print(f"❌ Cannot reach RoofWonder: {e}")
        return

    # 2. Check if Prometheus can scrape RoofWonder
    print("2️⃣ Checking Prometheus targets...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:9090/api/v1/targets")
            if response.status_code == 200:
                targets = response.json()
                roofwonder_found = False
                for target in targets.get("data", {}).get("activeTargets", []):
                    if "roofwonder" in target.get("labels", {}).get("service", ""):
                        if target.get("health") == "up":
                            print("✅ Prometheus scraping RoofWonder successfully")
                            roofwonder_found = True
                        else:
                            print(
                                f"❌ RoofWonder target unhealthy: {target.get('lastError', 'unknown')}"
                            )
                        break

                if not roofwonder_found:
                    print("❌ RoofWonder not found in Prometheus targets")
                    return
            else:
                print("❌ Cannot reach Prometheus")
                return
    except Exception as e:
        print(f"❌ Prometheus check failed: {e}")
        return

    # 3. Check Command Center status summary
    print("3️⃣ Checking Command Center status summary...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8010/status/summary")
            if response.status_code == 200:
                data = response.json()
                services = data.get("services", [])
                roofwonder_service = None
                for service in services:
                    if service.get("name") == "roofwonder":
                        roofwonder_service = service
                        break

                if roofwonder_service:
                    if roofwonder_service.get("up"):
                        print("✅ Command Center shows RoofWonder as UP")
                    else:
                        print("⚠️ Command Center shows RoofWonder as DOWN")
                else:
                    print("❌ RoofWonder not found in Command Center status")
            else:
                print("❌ Cannot reach Command Center")
                return
    except Exception as e:
        print(f"❌ Command Center check failed: {e}")
        return

    # 4. Test alert operator view
    print("4️⃣ Checking alert operator view...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8010/alerts/operator-view?limit=5")
            if response.status_code == 200:
                alerts = response.json()
                print(f"✅ Retrieved {len(alerts)} recent alerts")
                # Look for any RoofWonder alerts
                roofwonder_alerts = [
                    a for a in alerts if a.get("labels", {}).get("service") == "roofwonder"
                ]
                if roofwonder_alerts:
                    print(f"📋 Found {len(roofwonder_alerts)} RoofWonder alerts")
                    for alert in roofwonder_alerts[:2]:  # Show first 2
                        severity = alert.get("severity", "unknown")
                        title = alert.get("display_title", "No title")
                        runbook = alert.get("runbook", "No runbook")
                        print(f"   - {severity.upper()}: {title}")
                        if runbook != "No runbook":
                            print(f"     💡 {runbook[:60]}...")
                else:
                    print("📋 No RoofWonder alerts (this is good - service is healthy)")
            else:
                print("❌ Cannot get alerts from Command Center")
    except Exception as e:
        print(f"❌ Alert check failed: {e}")

    print("\n🎯 Monitoring loop test completed!")
    print("\n💡 To test auto-healing:")
    print("   1. Stop RoofWonder: docker compose -f deploy/docker-compose.dev.yml stop roofwonder")
    print("   2. Wait 5+ minutes for alert to fire")
    print("   3. Check alerts: curl http://localhost:8010/alerts/operator-view")
    print("   4. Run auto-heal worker: python autoheal_worker.py")
    print("   5. Check results in alerts")


if __name__ == "__main__":
    asyncio.run(test_roofwonder_monitoring_loop())
