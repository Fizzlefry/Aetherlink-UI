"""
Phase XXXV - Anomaly History & Insights
Tests for file-based anomaly history persistence.
"""

def test_append_and_read():
    print("Testing anomaly history append/read...")
    import sys
    import os
    import time
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "command-center"))
    from anomaly_history import append_anomaly_record, read_anomaly_records

    now = time.time()
    append_anomaly_record({
        "tenant": "acme-corp",
        "kind": "remediation_event",
        "occurred_at": "2025-11-10T17:45:00Z",
    })
    items = read_anomaly_records(tenant="acme-corp", since_ts=now - 10)
    assert len(items) >= 1
    print("[PASS] anomaly history append/read works")

if __name__ == "__main__":
    test_append_and_read()
    print("ALL TESTS PASSED - Phase XXXV anomaly history")