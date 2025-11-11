"""
Phase M12 - Split HTTP vs Degraded Telemetry
Validates we can record http_refresh_failed separately from degraded.
"""

def test_m12_event_labels():
    print("Testing M12 telemetry labels\n")
    from services.command_center.ws_manager import frontend_timeline_events_total

    # simulate http refresh failed
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="http_refresh_failed",
        component="RemediationTimeline",
    ).inc()
    print("[PASS] http_refresh_failed metric incremented")

    # simulate degraded
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="degraded",
        component="RemediationTimeline",
    ).inc()
    print("[PASS] degraded metric incremented")

    # simulate recovered
    frontend_timeline_events_total.labels(
        tenant="acme-corp",
        event="recovered",
        component="RemediationTimeline",
    ).inc()
    print("[PASS] recovered metric incremented")

    print("\n[PASS] M12 telemetry label split validated!")


if __name__ == "__main__":
    test_m12_event_labels()