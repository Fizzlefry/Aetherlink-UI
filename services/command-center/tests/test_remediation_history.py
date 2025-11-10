"""
Tests for the /ops/remediate/history endpoint.
Verifies the REST API returns correct data from SQLite.
"""

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from main import RECOVERY_DB, app, record_remediation_event

client = TestClient(app)


def ensure_test_row():
    """Ensure DB exists and has at least one test row."""
    RECOVERY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RECOVERY_DB)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()

    # Use the real writer to mimic production
    record_remediation_event(
        alertname="PytestAlert",
        tenant="test-tenant",
        action="auto_ack",
        status="success",
        details="pytest inserted row",
    )


def test_history_endpoint_basic():
    """Test basic endpoint functionality."""
    ensure_test_row()

    resp = client.get("/ops/remediate/history?limit=10")
    assert resp.status_code == 200

    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1

    # Verify structure of first item
    first = data["items"][0]
    assert "id" in first
    assert "ts" in first
    assert "alertname" in first
    assert "tenant" in first
    assert "action" in first
    assert "status" in first
    assert "details" in first


def test_history_filter_by_tenant():
    """Test filtering by tenant."""
    ensure_test_row()

    resp = client.get("/ops/remediate/history?tenant=test-tenant&limit=10")
    assert resp.status_code == 200
    data = resp.json()

    # All returned rows should match the filter
    for item in data["items"]:
        assert item["tenant"] == "test-tenant"


def test_history_filter_by_alertname():
    """Test filtering by alertname."""
    ensure_test_row()

    resp = client.get("/ops/remediate/history?alertname=PytestAlert&limit=10")
    assert resp.status_code == 200
    data = resp.json()

    # All returned rows should match the filter
    for item in data["items"]:
        assert item["alertname"] == "PytestAlert"


def test_history_limit_parameter():
    """Test limit parameter works correctly."""
    ensure_test_row()

    # Request only 2 items
    resp = client.get("/ops/remediate/history?limit=2")
    assert resp.status_code == 200
    data = resp.json()

    # Should return at most 2 items
    assert len(data["items"]) <= 2


def test_history_with_no_database():
    """Test endpoint handles missing database gracefully."""
    # Move DB temporarily
    backup_path = Path("monitoring/recovery_events.sqlite.testbackup")
    if RECOVERY_DB.exists():
        RECOVERY_DB.rename(backup_path)

    try:
        resp = client.get("/ops/remediate/history?limit=10")
        assert resp.status_code == 200
        data = resp.json()

        # Should return empty list, not error
        assert data["items"] == []
        assert data["total"] == 0
    finally:
        # Restore DB
        if backup_path.exists():
            backup_path.rename(RECOVERY_DB)


def test_history_returns_newest_first():
    """Test that results are ordered by ID descending (newest first)."""
    ensure_test_row()

    # Add another event
    record_remediation_event(
        alertname="NewerAlert",
        tenant="test-tenant",
        action="auto_ack",
        status="success",
        details="newer event",
    )

    resp = client.get("/ops/remediate/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()

    if len(data["items"]) >= 2:
        # IDs should be descending
        first_id = data["items"][0]["id"]
        second_id = data["items"][1]["id"]
        assert first_id > second_id
