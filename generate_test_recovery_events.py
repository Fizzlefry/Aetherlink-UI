#!/usr/bin/env python3
"""
Generate test recovery events for Grafana dashboard testing.
Creates realistic sample data spanning the last 24 hours.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("monitoring/recovery_events.sqlite")

# Test data configuration
ACTIONS = ["auto_ack", "replay", "escalate", "defer"]
STATUSES = ["success", "success", "success", "error"]  # 75% success rate
TENANTS = ["acme-corp", "test-tenant", "demo-co", "internal"]
ALERTS = [
    "HighFailureRate",
    "ServiceDown",
    "LatencySpike",
    "MemoryPressure",
    "DiskSpaceLow",
    "DeliveryBacklog",
]


def generate_test_events(count=100):
    """Generate test recovery events"""

    print(f"Generating {count} test recovery events...")

    # Ensure DB and table exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create table if needed
    cur.execute("""
        CREATE TABLE IF NOT EXISTS remediation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            alertname TEXT,
            tenant TEXT,
            action TEXT,
            status TEXT,
            details TEXT
        )
    """)

    # Generate events
    events_created = 0
    for i in range(count):
        # Random time in last 24 hours (weighted toward recent)
        hours_ago = random.triangular(0, 24, 2)  # More recent events
        ts = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + "Z"

        action = random.choice(ACTIONS)
        status = random.choice(STATUSES)
        tenant = random.choice(TENANTS)
        alertname = random.choice(ALERTS)

        # Generate realistic details based on status
        if status == "success":
            details = f"Successfully executed {action} for {alertname}"
            if action == "auto_ack":
                details += f" (alert_id: alert_{random.randint(1000, 9999)})"
            elif action == "replay":
                details += f" ({random.randint(1, 25)} deliveries replayed)"
            elif action == "escalate":
                details += f" (priority: {'high' if random.random() > 0.5 else 'medium'})"
        else:
            errors = [
                "Timeout waiting for response",
                "Insufficient permissions",
                "Rate limit exceeded",
                "Target service unavailable",
                "Configuration error",
            ]
            details = f"Failed to execute {action}: {random.choice(errors)}"

        cur.execute(
            """
            INSERT INTO remediation_events (ts, alertname, tenant, action, status, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (ts, alertname, tenant, action, status, details[:500]),
        )

        events_created += 1

    conn.commit()

    # Show summary
    cur.execute("SELECT COUNT(*) FROM remediation_events")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM remediation_events WHERE status = 'success'")
    successes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM remediation_events WHERE status = 'error'")
    failures = cur.fetchone()[0]

    print(f"\n[OK] Created {events_created} test events")
    print("\nDatabase Summary:")
    print(f"  Total events: {total}")
    print(f"  Successes: {successes} ({successes/total*100:.1f}%)")
    print(f"  Failures: {failures} ({failures/total*100:.1f}%)")

    # Show recent events
    print("\nLast 5 events:")
    print("  " + "-" * 80)
    cur.execute("""
        SELECT ts, alertname, tenant, action, status
        FROM remediation_events
        ORDER BY id DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0][:19]} | {row[1]:20} | {row[2]:15} | {row[3]:12} | {row[4]}")

    # Show stats by action
    print("\nEvents by action type:")
    cur.execute("""
        SELECT action, COUNT(*) as count
        FROM remediation_events
        GROUP BY action
        ORDER BY count DESC
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:15} {row[1]:4} events")

    # Show stats by tenant
    print("\nEvents by tenant:")
    cur.execute("""
        SELECT tenant, COUNT(*) as count
        FROM remediation_events
        GROUP BY tenant
        ORDER BY count DESC
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:15} {row[1]:4} events")

    conn.close()
    print(f"\n[OK] Database ready at: {DB_PATH}")
    print("\nNext steps:")
    print(f"  1. Configure Grafana SQLite datasource pointing to: {DB_PATH.absolute()}")
    print("  2. Import dashboard from: monitoring/grafana/dashboards/recovery-timeline.json")
    print("  3. Enjoy your Recovery Timeline dashboard!")


if __name__ == "__main__":
    import sys

    count = 100
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [count]")
            print("  count: number of test events to generate (default: 100)")
            sys.exit(1)

    generate_test_events(count)
