#!/usr/bin/env python3
"""
Test script for Phase XXIII: Federation Awareness
Tests the new federation endpoints and background task functionality.
"""

import os

import requests

BASE_URL = "http://localhost:8010"


def test_federation_endpoints():
    """Test federation endpoints with and without auth."""
    print("🧪 Testing Federation Endpoints...")

    # Test federation feed without key (should fail)
    try:
        response = requests.get(f"{BASE_URL}/federation/feed")
        if response.status_code == 403:
            print("✅ Federation feed correctly rejects unauthorized requests")
        else:
            print(f"❌ Federation feed should reject unauthorized: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation feed: {e}")

    # Test federation feed with invalid key (should fail)
    try:
        headers = {"x-fed-key": "invalid-key"}
        response = requests.get(f"{BASE_URL}/federation/feed", headers=headers)
        if response.status_code == 403:
            print("✅ Federation feed correctly rejects invalid keys")
        else:
            print(f"❌ Federation feed should reject invalid keys: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation feed with invalid key: {e}")

    # Test federation feed with valid key (should work)
    fed_key = os.getenv("AETHERLINK_FEDERATION_KEY", "aetherlink-shared-key")
    try:
        headers = {"x-fed-key": fed_key}
        response = requests.get(f"{BASE_URL}/federation/feed", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ Federation feed accepts valid key")
            print(f"   Federation info: {data.get('federation', {})}")
        else:
            print(f"❌ Federation feed should accept valid key: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation feed with valid key: {e}")

    # Test federation explain endpoint
    try:
        headers = {"x-fed-key": fed_key}
        response = requests.get(f"{BASE_URL}/federation/feed/explain", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ Federation explain endpoint works")
            print(f"   Explanation preview: {data.get('explanation', '')[:100]}...")
        else:
            print(f"❌ Federation explain failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation explain: {e}")

    # Test new federation endpoints
    try:
        response = requests.get(f"{BASE_URL}/federation/peers")
        if response.status_code == 200:
            data = response.json()
            print("✅ Federation peers endpoint works")
            print(f"   Node: {data.get('node_id')}, Peers: {len(data.get('peers', []))}")
        else:
            print(f"❌ Federation peers failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation peers: {e}")

    try:
        response = requests.get(f"{BASE_URL}/federation/health")
        if response.status_code == 200:
            data = response.json()
            print("✅ Federation health endpoint works")
            print(
                f"   Status: {data.get('status')}, Peers up: {data.get('peers_up')}/{data.get('peers_total')}"
            )
        else:
            print(f"❌ Federation health failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing federation health: {e}")

    # Test that ops/feed still works with federation key
    try:
        headers = {"x-fed-key": fed_key}
        response = requests.get(f"{BASE_URL}/ops/feed", headers=headers)
        if response.status_code == 200:
            print("✅ Ops feed accepts federation key")
        else:
            print(f"❌ Ops feed should accept federation key: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing ops feed with federation key: {e}")


def test_federation_config():
    """Test federation configuration from environment."""
    print("\n🔧 Testing Federation Configuration...")

    fed_enabled = os.getenv("AETHERLINK_FEDERATION_ENABLED", "true").lower() == "true"
    fed_peers = (
        os.getenv("AETHERLINK_FEDERATION_PEERS", "").split(",")
        if os.getenv("AETHERLINK_FEDERATION_PEERS")
        else []
    )
    fed_interval = int(os.getenv("AETHERLINK_FEDERATION_INTERVAL", "15"))
    fed_node_id = os.getenv("AETHERLINK_NODE_ID", "cc-local")

    print(f"   Federation enabled: {fed_enabled}")
    print(f"   Federation peers: {len(fed_peers)} configured")
    print(f"   Federation interval: {fed_interval}s")
    print(f"   Node ID: {fed_node_id}")

    if fed_enabled and fed_peers:
        print("✅ Federation is configured and enabled")
    elif fed_enabled and not fed_peers:
        print("⚠️  Federation enabled but no peers configured (single-node mode)")
    else:
        print("ℹ️  Federation disabled")


if __name__ == "__main__":
    print("🌐 Phase XXIII: Federation Awareness Test")
    print("=" * 50)

    test_federation_config()
    test_federation_endpoints()

    print("\n✨ Federation implementation test complete!")
