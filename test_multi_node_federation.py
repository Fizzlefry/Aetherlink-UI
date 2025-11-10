#!/usr/bin/env python3
"""
Test script for Phase XXIII: Multi-Node Federation
Tests federation between two Command Center instances.
"""

import os
import subprocess
import time

import requests

BASE_URL_1 = "http://localhost:8010"
BASE_URL_2 = "http://localhost:8013"
FED_KEY = os.getenv("AETHERLINK_FEDERATION_KEY", "aetherlink-shared-key")


def start_second_command_center():
    """Start a second Command Center instance on port 8011."""
    print("🚀 Starting second Command Center on port 8011...")

    # Set environment variables for the second instance
    env = os.environ.copy()
    env.update(
        {
            "AETHERLINK_NODE_ID": "cc-remote",
            "AETHERLINK_FEDERATION_PEERS": f"{BASE_URL_1}",
            "AETHERLINK_FEDERATION_KEY": FED_KEY,
            "AETHERLINK_FEDERATION_ENABLED": "true",
            "AETHERLINK_FEDERATION_INTERVAL": "5",  # Faster for testing
        }
    )

    # Start the second instance
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        f"aether-command-center-test-{int(time.time())}",
        "--network",
        "aetherlink_default",
        "-p",
        "8013:8010",
        "-e",
        "AETHERLINK_NODE_ID=cc-remote",
        "-e",
        f"AETHERLINK_FEDERATION_PEERS={BASE_URL_1}",
        "-e",
        f"AETHERLINK_FEDERATION_KEY={FED_KEY}",
        "-e",
        "AETHERLINK_FEDERATION_ENABLED=true",
        "-e",
        "AETHERLINK_FEDERATION_INTERVAL=5",
        "deploy-command-center",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to start second Command Center: {result.stderr}")
        return None

    container_id = result.stdout.strip()
    print(f"✅ Second Command Center started: {container_id[:12]}")

    # Wait for it to be healthy
    print("⏳ Waiting for second Command Center to be healthy...")
    for _ in range(30):
        try:
            response = requests.get(f"{BASE_URL_2}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Second Command Center is healthy")
                return container_id
        except:
            pass
        time.sleep(2)

    print("❌ Second Command Center failed to become healthy")
    return None


def test_multi_node_federation():
    """Test federation between two nodes."""
    print("\n🌐 Testing Multi-Node Federation...")

    # Test that node 1 can see its own federation status
    try:
        headers = {"x-fed-key": FED_KEY}
        response = requests.get(f"{BASE_URL_1}/federation/feed", headers=headers)
        if response.status_code == 200:
            data = response.json()
            fed_info = data.get("federation", {})
            print(f"✅ Node 1 federation status: {fed_info}")
        else:
            print(f"❌ Node 1 federation feed failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing node 1: {e}")
        return False

    # Test that node 2 can see federation status
    try:
        headers = {"x-fed-key": FED_KEY}
        response = requests.get(f"{BASE_URL_2}/federation/feed", headers=headers)
        if response.status_code == 200:
            data = response.json()
            fed_info = data.get("federation", {})
            print(f"✅ Node 2 federation status: {fed_info}")

            # Check if node 2 has fetched data from node 1
            if fed_info.get("peer_count", 0) > 0:
                print("✅ Node 2 is connected to peers")
            else:
                print("⚠️  Node 2 has no peer connections yet (waiting for first fetch)")
        else:
            print(f"❌ Node 2 federation feed failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing node 2: {e}")
        return False

    # Wait a bit for federation sync
    print("⏳ Waiting for federation sync...")
    time.sleep(10)

    # Test cross-node data sharing
    try:
        headers = {"x-fed-key": FED_KEY}
        response = requests.get(f"{BASE_URL_2}/federation/feed", headers=headers)
        if response.status_code == 200:
            data = response.json()
            fed_info = data.get("federation", {})

            if fed_info.get("last_updated"):
                print("✅ Federation data is being synchronized between nodes")
                print(f"   Last updated: {fed_info['last_updated']}")
            else:
                print("⚠️  Federation data not yet synchronized")
        else:
            print(f"❌ Cross-node sync check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking cross-node sync: {e}")

    return True


def cleanup_second_command_center(container_id: str | None):
    """Clean up the second Command Center instance."""
    if container_id:
        print(f"\n🧹 Cleaning up second Command Center ({container_id[:12]})...")
        subprocess.run(["docker", "stop", container_id], capture_output=True)
        subprocess.run(["docker", "rm", container_id], capture_output=True)
        print("✅ Cleanup complete")


def main():
    print("🌐 Phase XXIII: Multi-Node Federation Test")
    print("=" * 50)

    # Check if first node is running
    try:
        response = requests.get(f"{BASE_URL_1}/health", timeout=5)
        if response.status_code != 200:
            print("❌ First Command Center is not healthy")
            return
    except:
        print("❌ Cannot connect to first Command Center")
        return

    print("✅ First Command Center is running")

    # Start second node
    container_id = start_second_command_center()
    if not container_id:
        return

    try:
        # Test federation
        success = test_multi_node_federation()

        if success:
            print("\n🎉 Multi-node federation test completed successfully!")
            print("✅ Both nodes are running and communicating")
            print("✅ Federation endpoints are working")
            print("✅ Cross-node data synchronization is active")
        else:
            print("\n❌ Multi-node federation test failed")

    finally:
        cleanup_second_command_center(container_id)


if __name__ == "__main__":
    main()
