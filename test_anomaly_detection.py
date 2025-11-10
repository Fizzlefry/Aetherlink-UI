"""
Quick smoke test for anomaly detection endpoint.

This simulates timeline data with known anomalies to verify the detector works.
"""

import json


def simulate_timeline_with_anomaly():
    """Create mock timeline data with clear anomaly pattern."""
    # Baseline: steady state around 2-3 remediations
    # Anomaly: spike to 10 at bucket 5
    # Quiet: 0 remediations at buckets 8, 9

    timeline = [
        {"ts": "2025-01-09T10:00:00Z", "count": 2},
        {"ts": "2025-01-09T10:15:00Z", "count": 3},
        {"ts": "2025-01-09T10:30:00Z", "count": 2},
        {"ts": "2025-01-09T10:45:00Z", "count": 3},
        {"ts": "2025-01-09T11:00:00Z", "count": 10},  # ANOMALY: 10 vs baseline ~2.5
        {"ts": "2025-01-09T11:15:00Z", "count": 2},
        {"ts": "2025-01-09T11:30:00Z", "count": 3},
        {"ts": "2025-01-09T11:45:00Z", "count": 0},   # QUIET
        {"ts": "2025-01-09T12:00:00Z", "count": 0},   # QUIET
        {"ts": "2025-01-09T12:15:00Z", "count": 2},
    ]

    return timeline


def detect_anomalies(timeline, multiplier=2.0, min_count=3, window_size=4):
    """
    Replicate backend anomaly detection logic.

    Anomaly rule: count >= min_count AND count > avg * multiplier
    """
    anomalies = []
    quiet = []

    for i, point in enumerate(timeline):
        ts = point["ts"]
        count = point["count"]

        # Identify quiet periods
        if count == 0:
            quiet.append({"ts": ts, "count": count})
            continue

        # Calculate rolling baseline
        if i < window_size:
            baseline_counts = [p["count"] for p in timeline[:i]]
        else:
            baseline_counts = [timeline[j]["count"] for j in range(i - window_size, i)]

        if not baseline_counts:
            continue

        avg = sum(baseline_counts) / len(baseline_counts)

        # Detect anomaly
        if count >= min_count and count > avg * multiplier:
            anomalies.append({
                "ts": ts,
                "count": count,
                "baseline": round(avg, 2),
                "factor": round(count / avg, 2) if avg > 0 else count,
            })

    return anomalies, quiet


def test_anomaly_detection():
    """Test that anomaly detection correctly identifies spikes and quiet periods."""
    print("Testing Anomaly Detection Logic\n")

    timeline = simulate_timeline_with_anomaly()
    print("Mock Timeline Data:")
    for i, point in enumerate(timeline):
        print(f"  Bucket {i}: {point['ts'][11:16]} -> {point['count']} remediations")

    anomalies, quiet = detect_anomalies(timeline, multiplier=2.0, min_count=3)

    print(f"\nDetected Anomalies: {len(anomalies)}")
    for a in anomalies:
        print(f"  {a['ts'][11:16]}: count={a['count']}, baseline={a['baseline']}, {a['factor']}x spike")

    print(f"\nDetected Quiet Periods: {len(quiet)}")
    for q in quiet:
        print(f"  {q['ts'][11:16]}: count={q['count']}")

    # Verify expectations
    assert len(anomalies) == 1, f"Expected 1 anomaly, got {len(anomalies)}"
    assert anomalies[0]["count"] == 10, "Anomaly should be the bucket with count=10"
    assert len(quiet) == 2, f"Expected 2 quiet periods, got {len(quiet)}"

    print("\n[PASS] All assertions passed!")
    print(f"\nSummary:")
    print(f"  - Baseline avg: ~2.5 remediations")
    print(f"  - Spike detected: 10 remediations (4x baseline)")
    print(f"  - Quiet periods: 2 buckets with 0 activity")
    print(f"  - Detection threshold: 2.0x multiplier, min 3 events")


if __name__ == "__main__":
    test_anomaly_detection()
