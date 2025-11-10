"""
Tests for the record_remediation_event() writer function.
Verifies events are correctly written to SQLite with proper data.
"""

import sqlite3
from datetime import datetime

from main import RECOVERY_DB, record_remediation_event


def test_record_remediation_event_writes_to_sqlite():
    """Test that writer function successfully writes to SQLite."""
    # Act
    record_remediation_event(
        alertname="WriterTest",
        tenant="unit-test",
        action="auto_ack",
        status="success",
        details="unit test write",
    )

    # Assert
    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT alertname, tenant, action, status, details FROM remediation_events ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "WriterTest"
    assert row[1] == "unit-test"
    assert row[2] == "auto_ack"
    assert row[3] == "success"
    assert row[4] == "unit test write"


def test_record_remediation_event_creates_table():
    """Test that writer creates table if it doesn't exist."""
    # This test is implicit in the writer function
    # If table doesn't exist, it should create it
    record_remediation_event(
        alertname="TableCreationTest",
        tenant="test",
        action="auto_ack",
        status="success",
        details="testing table creation",
    )

    # Verify table exists
    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='remediation_events'")
    table_exists = cur.fetchone() is not None
    conn.close()

    assert table_exists


def test_record_remediation_event_timestamp_format():
    """Test that timestamps are in ISO format with Z suffix."""
    record_remediation_event(
        alertname="TimestampTest",
        tenant="test",
        action="auto_ack",
        status="success",
        details="testing timestamp format",
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT ts FROM remediation_events ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    timestamp = row[0]

    # Should end with 'Z'
    assert timestamp.endswith("Z")

    # Should be valid ISO format (will raise if not)
    datetime.fromisoformat(timestamp.rstrip("Z"))


def test_record_remediation_event_truncates_long_details():
    """Test that details longer than 500 chars are truncated."""
    long_details = "x" * 1000  # 1000 character string

    record_remediation_event(
        alertname="TruncationTest",
        tenant="test",
        action="auto_ack",
        status="success",
        details=long_details,
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT details FROM remediation_events ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    stored_details = row[0]

    # Should be truncated to 500 chars
    assert len(stored_details) == 500
    assert stored_details == "x" * 500


def test_record_remediation_event_handles_empty_details():
    """Test that empty details string works correctly."""
    record_remediation_event(
        alertname="EmptyDetailsTest",
        tenant="test",
        action="auto_ack",
        status="success",
        details="",
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT details FROM remediation_events ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == ""


def test_record_remediation_event_handles_special_characters():
    """Test that special characters in fields are handled correctly."""
    record_remediation_event(
        alertname="Alert'With\"Quotes",
        tenant="tenant-with-dashes",
        action="auto_ack",
        status="success",
        details="Details with 'quotes' and \"double quotes\" and <tags>",
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT alertname, tenant, details FROM remediation_events ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "Alert'With\"Quotes"
    assert row[1] == "tenant-with-dashes"
    assert "quotes" in row[2]


def test_record_remediation_event_success_status():
    """Test recording a successful remediation."""
    record_remediation_event(
        alertname="SuccessTest",
        tenant="test-tenant",
        action="auto_ack",
        status="success",
        details="Successfully auto-acknowledged alert",
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT status FROM remediation_events WHERE alertname = 'SuccessTest'")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "success"


def test_record_remediation_event_error_status():
    """Test recording a failed remediation."""
    record_remediation_event(
        alertname="ErrorTest",
        tenant="test-tenant",
        action="auto_ack",
        status="error",
        details="Failed to acknowledge: Connection timeout",
    )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT status, details FROM remediation_events WHERE alertname = 'ErrorTest'")
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "error"
    assert "timeout" in row[1].lower()


def test_record_remediation_event_different_actions():
    """Test recording different action types."""
    actions = ["auto_ack", "replay", "escalate", "defer"]

    for action in actions:
        record_remediation_event(
            alertname=f"Action{action.title()}Test",
            tenant="test-tenant",
            action=action,
            status="success",
            details=f"Testing {action} action",
        )

    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT action FROM remediation_events WHERE alertname LIKE 'Action%Test'")
    rows = cur.fetchall()
    conn.close()

    recorded_actions = {row[0] for row in rows}
    assert set(actions).issubset(recorded_actions)
