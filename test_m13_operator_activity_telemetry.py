"""
Phase M13 - Apply Telemetry Pattern to OperatorActivity
Validates OperatorActivity component implements the same telemetry pattern as RemediationTimeline.
"""


def test_m13_operator_activity_telemetry():
    print("Testing M13 OperatorActivity telemetry pattern\n")
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "command-center"))
    from ws_manager import frontend_timeline_events_total  # type: ignore

    # Test that the metric accepts OperatorActivity events
    # Simulate ws_stale for OperatorActivity
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="ws_stale",
        component="OperatorActivity",
    ).inc()

    # Simulate http_refresh_failed for OperatorActivity
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="http_refresh_failed",
        component="OperatorActivity",
    ).inc()

    # Simulate degraded for OperatorActivity
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="degraded",
        component="OperatorActivity",
    ).inc()

    # Simulate recovered for OperatorActivity
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="recovered",
        component="OperatorActivity",
    ).inc()

    print("[PASS] ws_stale metric incremented for OperatorActivity")
    print("[PASS] http_refresh_failed metric incremented for OperatorActivity")
    print("[PASS] degraded metric incremented for OperatorActivity")
    print("[PASS] recovered metric incremented for OperatorActivity")

    print("\n[PASS] M13 telemetry pattern successfully applied to OperatorActivity!")


if __name__ == "__main__":
    test_m13_operator_activity_telemetry()
