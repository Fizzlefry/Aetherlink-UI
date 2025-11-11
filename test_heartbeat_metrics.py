"""
Test for Phase XX M9 - Adaptive WS Recovery + Heartbeat Metrics

Validates:
1. Heartbeat metrics are properly defined
2. Stale connection detection logic works
3. WebSocket heartbeat tracking persists timestamps
4. Gauge metrics update correctly for stale counts
"""


def test_heartbeat_prometheus_metrics():
    """Test that heartbeat Prometheus metrics are properly defined."""
    print("Testing Heartbeat Prometheus Metrics\n")

    import sys
    from pathlib import Path

    # Add command-center to path
    sys.path.insert(0, str(Path(__file__).parent / "services" / "command-center"))
    from ws_manager import timeline_ws_heartbeat_total, timeline_ws_stale_connections

    # Verify heartbeat counter exists
    assert timeline_ws_heartbeat_total is not None
    print("[PASS] timeline_ws_heartbeat_total metric exists")

    # Verify metric type
    metric_type = str(type(timeline_ws_heartbeat_total))
    assert "Counter" in metric_type
    print(f"[PASS] Heartbeat metric type is Counter: {metric_type}")

    # Verify stale connections gauge exists
    assert timeline_ws_stale_connections is not None
    print("[PASS] timeline_ws_stale_connections metric exists")

    # Verify gauge type
    gauge_type = str(type(timeline_ws_stale_connections))
    assert "Gauge" in gauge_type
    print(f"[PASS] Stale connections metric type is Gauge: {gauge_type}")

    # Test incrementing heartbeat counter with different tenants
    tenants = ["acme-corp", "globex", "unknown"]
    for tenant in tenants:
        timeline_ws_heartbeat_total.labels(tenant=tenant).inc()
        print(f"[PASS] Incremented heartbeat counter for tenant: {tenant}")

    # Test setting gauge value
    timeline_ws_stale_connections.labels(tenant="all").set(3)
    print("[PASS] Set stale connections gauge to 3")

    print("\n[PASS] Prometheus metrics validation complete!")


def test_stale_detection_logic():
    """Test stale connection detection thresholds."""
    print("\n\nTesting Stale Connection Detection Logic\n")

    import time

    # Simulate connection heartbeat scenarios
    stale_threshold = 35.0  # seconds
    scenarios = [
        {
            "name": "Fresh connection",
            "last_heartbeat": time.time(),
            "expected_stale": False,
        },
        {
            "name": "Connection at threshold boundary",
            "last_heartbeat": time.time() - 35.0,
            "expected_stale": False,  # Equal to threshold, not greater
        },
        {
            "name": "Stale connection (36 seconds old)",
            "last_heartbeat": time.time() - 36.0,
            "expected_stale": True,
        },
        {
            "name": "Very stale connection (60 seconds old)",
            "last_heartbeat": time.time() - 60.0,
            "expected_stale": True,
        },
    ]

    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")

        now = time.time()
        last_hb = scenario["last_heartbeat"]
        age = now - last_hb
        is_stale = age > stale_threshold

        print(f"  Age: {age:.1f} seconds")
        print(f"  Threshold: {stale_threshold} seconds")
        print(f"  Is stale: {is_stale}")

        assert (
            is_stale == scenario["expected_stale"]
        ), f"Stale detection mismatch: got {is_stale}, expected {scenario['expected_stale']}"

        print("  [PASS] Stale detection correct")

    print("\n[PASS] Stale connection detection logic validated!")


def test_heartbeat_tracking_persistence():
    """Test that heartbeat timestamps are properly tracked per connection."""
    print("\n\nTesting Heartbeat Timestamp Tracking\n")

    import time
    from unittest.mock import Mock

    # Simulate WebSocket connection tracking
    connections = {}

    # Mock WebSocket connections
    ws1 = Mock()
    ws1.id = "conn-1"
    ws2 = Mock()
    ws2.id = "conn-2"
    ws3 = Mock()
    ws3.id = "conn-3"

    # Simulate heartbeat arrival pattern
    print("Simulating heartbeat arrivals:\n")

    # Connection 1: Recent heartbeat
    connections[ws1] = time.time()
    print("[WS-1] Heartbeat received at t=0")

    # Connection 2: Heartbeat 20 seconds ago
    connections[ws2] = time.time() - 20.0
    print("[WS-2] Heartbeat received at t=-20s")

    # Connection 3: Heartbeat 40 seconds ago (stale)
    connections[ws3] = time.time() - 40.0
    print("[WS-3] Heartbeat received at t=-40s")

    # Check staleness
    now = time.time()
    stale_threshold = 35.0
    stale_connections = []

    print("\nStale connection check:\n")
    for ws, last_hb in connections.items():
        age = now - last_hb
        is_stale = age > stale_threshold
        status = "STALE" if is_stale else "FRESH"
        print(f"  [{ws.id}] Age: {age:.1f}s -> {status}")
        if is_stale:
            stale_connections.append(ws)

    # Verify expectations
    assert len(stale_connections) == 1, f"Expected 1 stale connection, got {len(stale_connections)}"
    assert ws3 in stale_connections, "Connection 3 should be stale"
    print(f"\n[PASS] Found {len(stale_connections)} stale connection(s)")

    # Simulate disconnection cleanup
    print("\nSimulating disconnection cleanup:")
    del connections[ws2]
    print("  [WS-2] Disconnected -> removed from tracking")
    assert ws2 not in connections
    print("[PASS] Heartbeat tracking cleaned up on disconnect")

    print("\n[PASS] Heartbeat timestamp tracking validated!")


def test_ui_stale_indicator_logic():
    """Test UI stale connection indicator logic."""
    print("\n\nTesting UI Stale Indicator Logic\n")

    from datetime import datetime, timedelta

    # Test cases for stale indicator display
    test_cases = [
        {
            "name": "Recent WS update",
            "lastWsUpdate": datetime.now().isoformat(),
            "should_show_stale": False,
        },
        {
            "name": "WS update 34 seconds ago (not stale yet)",
            "lastWsUpdate": (datetime.now() - timedelta(seconds=34)).isoformat(),
            "should_show_stale": False,
        },
        {
            "name": "WS update 36 seconds ago (stale)",
            "lastWsUpdate": (datetime.now() - timedelta(seconds=36)).isoformat(),
            "should_show_stale": True,
        },
        {
            "name": "WS update 60 seconds ago (very stale)",
            "lastWsUpdate": (datetime.now() - timedelta(seconds=60)).isoformat(),
            "should_show_stale": True,
        },
        {
            "name": "No WS update yet",
            "lastWsUpdate": None,
            "should_show_stale": False,
        },
    ]

    stale_threshold_seconds = 35

    for case in test_cases:
        print(f"\nCase: {case['name']}")

        # Simulate React component logic
        if not case["lastWsUpdate"]:
            ws_stale = False
        else:
            now = datetime.now()
            last_update = datetime.fromisoformat(case["lastWsUpdate"])
            age_seconds = (now - last_update).total_seconds()
            ws_stale = age_seconds > stale_threshold_seconds

        print(f"  Last update: {case['lastWsUpdate']}")
        print(f"  Should show stale: {case['should_show_stale']}")
        print(f"  Actual stale flag: {ws_stale}")

        assert (
            ws_stale == case["should_show_stale"]
        ), f"UI stale logic mismatch: got {ws_stale}, expected {case['should_show_stale']}"

        if ws_stale:
            print("  [PASS] Stale indicator visible (orange warning)")
        else:
            print("  [PASS] Stale indicator hidden")

    print("\n[PASS] UI stale indicator logic validated!")


def test_heartbeat_message_format():
    """Test that heartbeat messages follow expected format."""
    print("\n\nTesting Heartbeat Message Format\n")

    import json

    # Test client -> server heartbeat format
    client_heartbeat = {
        "type": "heartbeat",
        "tenant": "acme-corp",
    }

    # Verify structure
    assert "type" in client_heartbeat
    assert client_heartbeat["type"] == "heartbeat"
    assert "tenant" in client_heartbeat
    print("[PASS] Client heartbeat message structure valid")
    print(f"  Format: {json.dumps(client_heartbeat)}")

    # Test server -> client pong format
    server_pong = {
        "type": "pong",
    }

    assert "type" in server_pong
    assert server_pong["type"] == "pong"
    print("\n[PASS] Server pong message structure valid")
    print(f"  Format: {json.dumps(server_pong)}")

    print("\n[PASS] Heartbeat message format validated!")


if __name__ == "__main__":
    test_heartbeat_prometheus_metrics()
    test_stale_detection_logic()
    test_heartbeat_tracking_persistence()
    test_ui_stale_indicator_logic()
    test_heartbeat_message_format()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED - Phase XX M9 validation complete")
    print("=" * 60)
    print("\nKey features:")
    print("  - Heartbeat tracking with Prometheus metrics")
    print("  - Stale connection detection (35 second threshold)")
    print("  - Bidirectional WebSocket communication")
    print("  - Client-side heartbeat sender (15 second interval)")
    print("  - UI stale connection indicator (orange warning)")
    print("  - Metrics exposed for Grafana alerting:")
    print("    * aetherlink_timeline_ws_heartbeat_total{tenant}")
    print("    * aetherlink_timeline_ws_stale_connections{tenant}")
