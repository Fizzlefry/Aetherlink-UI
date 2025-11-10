#!/usr/bin/env python3
"""
Test script for alert acknowledgment functionality.
"""

import os
import time

import requests

BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("API_KEY_EXPERTCO", "expertco-key-123")
ADMIN_KEY = os.getenv("API_ADMIN_KEY", "admin-secret-123")


def test_alert_acknowledgment():
    print("Testing Alert Acknowledgment Functionality")
    print("=" * 50)

    # First, get the current alerts
    print("1. Getting current alerts...")
    try:
        response = requests.get(f"{BASE_URL}/ui/bundle")
        response.raise_for_status()
        bundle = response.json()
        alerts = bundle.get("alerts", [])
        print(f"   Found {len(alerts)} alerts")

        if not alerts:
            print("   No alerts to test with. System appears healthy.")
            return

        # Pick the first alert for testing
        test_alert = alerts[0]
        alert_id = test_alert["id"]
        print(f"   Testing with alert: {alert_id} ({test_alert['title']})")

        # Check initial ack state
        initial_ack = test_alert.get("ack", False)
        print(f"   Initial ack state: {initial_ack}")

        # Acknowledge the alert
        print("2. Acknowledging alert...")
        ack_response = requests.post(
            f"{BASE_URL}/ui/alerts/{alert_id}/ack",
            headers={
                "x-api-key": API_KEY,
                "x-admin-key": ADMIN_KEY,
                "Content-Type": "application/json",
            },
        )

        if ack_response.status_code == 200:
            print("   ✓ Acknowledgment successful")
        else:
            print(f"   ✗ Acknowledgment failed: {ack_response.status_code} - {ack_response.text}")
            return

        # Wait a moment and check the bundle again
        time.sleep(1)
        print("3. Verifying acknowledgment in bundle...")
        response = requests.get(f"{BASE_URL}/ui/bundle")
        response.raise_for_status()
        bundle = response.json()
        alerts = bundle.get("alerts", [])

        # Find our test alert
        updated_alert = next((a for a in alerts if a["id"] == alert_id), None)
        if updated_alert:
            updated_ack = updated_alert.get("ack", False)
            print(f"   Updated ack state: {updated_ack}")
            if updated_ack:
                print("   ✓ Alert is now acknowledged")
            else:
                print("   ✗ Alert acknowledgment not reflected in bundle")
        else:
            print("   ✗ Test alert not found in updated bundle")

        # Unacknowledge the alert
        print("4. Unacknowledging alert...")
        unack_response = requests.post(
            f"{BASE_URL}/ui/alerts/{alert_id}/unack",
            headers={
                "x-api-key": API_KEY,
                "x-admin-key": ADMIN_KEY,
                "Content-Type": "application/json",
            },
        )

        if unack_response.status_code == 200:
            print("   ✓ Unacknowledgment successful")
        else:
            print(
                f"   ✗ Unacknowledgment failed: {unack_response.status_code} - {unack_response.text}"
            )
            return

        # Final verification
        time.sleep(1)
        print("5. Final verification...")
        response = requests.get(f"{BASE_URL}/ui/bundle")
        response.raise_for_status()
        bundle = response.json()
        alerts = bundle.get("alerts", [])

        final_alert = next((a for a in alerts if a["id"] == alert_id), None)
        if final_alert:
            final_ack = final_alert.get("ack", False)
            print(f"   Final ack state: {final_ack}")
            if not final_ack:
                print("   ✓ Alert acknowledgment cycle completed successfully")
            else:
                print("   ✗ Alert still acknowledged after unack")
        else:
            print("   ✗ Test alert not found in final bundle")

    except Exception as e:
        print(f"   ✗ Test failed with error: {e}")

    print("\nTest completed!")


if __name__ == "__main__":
    test_alert_acknowledgment()
