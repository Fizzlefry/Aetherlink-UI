#!/usr/bin/env python3
"""
Test script for adaptive recommendations functionality.
"""

import requests

BASE_URL = "http://localhost:8000"


def test_adaptive_recommendations():
    print("Testing Adaptive Recommendations")
    print("=" * 40)

    try:
        # Test recommendations endpoint
        print("1. Getting adaptive recommendations...")
        response = requests.get(f"{BASE_URL}/ops/adaptive/recommendations")
        response.raise_for_status()
        data = response.json()

        print(f"   Status: {response.status_code}")
        print(f"   OK: {data.get('ok', False)}")
        print(f"   Window: {data.get('window_hours', 'N/A')} hours")
        print(f"   Events analyzed: {data.get('total_events_analyzed', 0)}")

        # Show top actions
        top_actions = data.get("top_operator_actions", [])
        print(f"   Top operator actions: {len(top_actions)}")
        for i, action in enumerate(top_actions[:3]):  # Show first 3
            print(f"     {i+1}. {action['operation']} ({action['count']} times)")
            print(f"        → {action['recommendation']}")

        # Show auto-ack candidates
        auto_ack = data.get("auto_ack_candidates", [])
        print(f"   Auto-ack candidates: {len(auto_ack)}")
        for candidate in auto_ack[:2]:  # Show first 2
            print(f"     • {candidate['alert_id']} ({candidate['confidence']*100:.0f}% confidence)")

        # Test feedback endpoint
        print("\n2. Testing feedback submission...")
        feedback_payload = {
            "type": "action_recommendation",
            "target": "operator.alert.ack",
            "feedback": "good",
            "tenant": "system",
        }

        response = requests.post(
            f"{BASE_URL}/ops/adaptive/feedback",
            json=feedback_payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   Feedback submitted: {result.get('ok', False)}")
        else:
            print(f"   Feedback failed: {response.status_code}")

        print("\n✓ Adaptive recommendations test completed successfully!")

    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to server. Is it running?")
    except Exception as e:
        print(f"   ✗ Test failed: {e}")


if __name__ == "__main__":
    test_adaptive_recommendations()
