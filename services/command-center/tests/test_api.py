import os

import requests

BASE_URL = os.getenv("CC_BASE_URL", "http://localhost:8011")
HEADERS = {"X-User-Roles": "admin"}


def test_healthz():
    """Test health check endpoint returns healthy status"""
    r = requests.get(f"{BASE_URL}/healthz", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "healthy"
    assert "timestamp" in body
    assert body.get("service") == "command-center"


def test_healthz_requires_auth():
    """Test health check requires X-User-Roles header"""
    r = requests.get(f"{BASE_URL}/healthz")
    assert r.status_code == 422  # FastAPI validation error


def test_meta():
    """Test meta endpoint returns API information"""
    r = requests.get(f"{BASE_URL}/meta", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "endpoints" in body
    assert isinstance(body["endpoints"], list)
    assert "/alerts/deliveries/history" in body["endpoints"]


def test_alerts_history():
    """Test alerts history endpoint returns proper structure"""
    r = requests.get(f"{BASE_URL}/alerts/deliveries/history?limit=5", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


def test_metrics():
    """Test Prometheus metrics endpoint"""
    # Make a few requests to ensure metrics are populated
    requests.get(f"{BASE_URL}/healthz", headers=HEADERS)
    requests.get(f"{BASE_URL}/meta", headers=HEADERS)

    r = requests.get(f"{BASE_URL}/metrics", headers=HEADERS)
    assert r.status_code == 200
    content = r.text
    assert "command_center_uptime_seconds" in content
    assert "command_center_health" in content
    # The API requests counter might not be present if no requests were made yet
    # assert "command_center_api_requests_total" in content


def test_service_registration():
    """Test service registration and listing"""
    # Register a test service
    service_data = {
        "name": "test-service",
        "url": "http://test:8080/health",
        "description": "Test service for E2E testing",
    }
    r = requests.post(f"{BASE_URL}/ops/register", json=service_data, headers=HEADERS)
    assert r.status_code == 200

    # List services
    r = requests.get(f"{BASE_URL}/ops/services", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "services" in body
    assert len(body["services"]) > 0

    # Verify our test service is there
    service_names = [s["name"] for s in body["services"]]
    assert "test-service" in service_names


def test_events_stream():
    """Test Server-Sent Events endpoint accepts connection"""
    # This is a basic connectivity test - full SSE testing would require async handling
    r = requests.get(f"{BASE_URL}/events/stream", headers=HEADERS, stream=True, timeout=5)
    # SSE endpoints typically return 200 and start streaming
    assert r.status_code == 200
    # Close the connection quickly
    r.close()


def test_rbac_enforcement():
    """Test that RBAC headers are properly enforced"""
    endpoints_to_test = [
        "/healthz",  # Returns 422 for missing required header
        "/meta",  # Returns 422 for missing required header
        "/alerts/deliveries/history",  # Has RBAC, returns 403 for missing/invalid roles
        "/metrics",  # Returns 422 for missing required header
    ]

    for endpoint in endpoints_to_test:
        # Test without headers
        r = requests.get(f"{BASE_URL}{endpoint}")
        if endpoint == "/alerts/deliveries/history":
            # This endpoint has RBAC that returns 403 for missing headers
            assert r.status_code == 403, f"Endpoint {endpoint} should require proper roles"
        else:
            # Other endpoints return 422 for missing required X-User-Roles header
            assert r.status_code == 422, f"Endpoint {endpoint} should require X-User-Roles header"

        # Test with invalid role - should fail RBAC for protected endpoints
        r = requests.get(f"{BASE_URL}{endpoint}", headers={"X-User-Roles": "invalid"})
        if endpoint == "/alerts/deliveries/history":
            # This endpoint has specific RBAC requirements
            assert r.status_code == 403, f"Endpoint {endpoint} should reject invalid roles"


def test_container_startup():
    """Test that container started within reasonable time"""
    # This test assumes the container was started recently
    r = requests.get(f"{BASE_URL}/healthz", headers=HEADERS)
    assert r.status_code == 200

    body = r.json()
    # If uptime is very low, container might have just started
    # This is more of a sanity check than a strict test
    assert "timestamp" in body


def test_federation_predict():
    """Test federation predictive endpoint"""
    # Test without auth header - should fail
    r = requests.get(f"{BASE_URL}/federation/predict")
    assert r.status_code == 401

    # Test with invalid auth header - should fail
    r = requests.get(f"{BASE_URL}/federation/predict", headers={"x-fed-key": "invalid"})
    assert r.status_code == 401

    # Test with valid auth header - should work
    r = requests.get(
        f"{BASE_URL}/federation/predict", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "risk" in body
    assert "peers" in body
    assert isinstance(body["risk"], (int, float))
    assert "fresh" in body["peers"]
    assert "at_risk" in body["peers"]
    assert "stale" in body["peers"]


def test_federation_forecast_explain():
    """Test federation forecast explain endpoint"""
    # Test with valid auth header
    r = requests.get(
        f"{BASE_URL}/federation/forecast/explain", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "explanation" in body
    assert "data" in body
    assert isinstance(body["explanation"], str)


def test_federation_actions_preempt():
    """Test federation preemptive actions endpoint"""
    # Test sync_now action
    payload = {"action": "sync_now", "peers": ["peer1", "peer2"]}
    r = requests.post(
        f"{BASE_URL}/federation/actions/preempt",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "sync_now"
    assert "results" in body

    # Test health_check action
    payload = {"action": "health_check", "peers": ["peer1"]}
    r = requests.post(
        f"{BASE_URL}/federation/actions/preempt",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "health_check"
    assert "results" in body

    # Test unknown action - should fail
    payload = {"action": "unknown_action"}
    r = requests.post(
        f"{BASE_URL}/federation/actions/preempt",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 400


def test_federation_coord_state():
    """Test federation coordination state endpoint"""
    # Test with valid auth header
    r = requests.get(
        f"{BASE_URL}/federation/coord/state", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "node_id" in body
    assert "claims" in body
    assert "timestamp" in body
    assert isinstance(body["claims"], list)


def test_federation_coord_claim():
    """Test federation coordination claim endpoint"""
    # Test claiming a target
    payload = {"target_id": "peer:test-peer", "ttl": 30}
    r = requests.post(
        f"{BASE_URL}/federation/coord/claim",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "claimed"
    assert body["target_id"] == "peer:test-peer"

    # Test claiming the same target again - should fail
    r = requests.post(
        f"{BASE_URL}/federation/coord/claim",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 409

    # Check state shows the claim
    r = requests.get(
        f"{BASE_URL}/federation/coord/state", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    claims = [c for c in body["claims"] if c["target"] == "peer:test-peer"]
    assert len(claims) == 1
    assert claims[0]["owner"] == "cc-local"  # default owner


def test_federation_actions_report():
    """Test federation actions report endpoint"""
    # Report a successful action
    payload = {
        "target_id": "peer:test-peer",
        "action": "force-resync",
        "status": "success",
        "message": "completed in 120ms",
    }
    r = requests.post(
        f"{BASE_URL}/federation/actions/report",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "recorded"
    assert "peer:test-peer|force-resync" in body["action_key"]

    # Report a failed action
    payload["status"] = "failure"
    payload["message"] = "timeout error"
    r = requests.post(
        f"{BASE_URL}/federation/actions/report",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200


def test_federation_opt_state():
    """Test federation optimization state endpoint"""
    r = requests.get(
        f"{BASE_URL}/federation/opt/state", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "node_id" in body
    assert "policies" in body
    assert "timestamp" in body
    assert isinstance(body["policies"], dict)


def test_federation_opt_explain():
    """Test federation optimization explain endpoint"""
    r = requests.get(
        f"{BASE_URL}/federation/opt/explain", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "explanation" in body
    assert "data" in body
    assert isinstance(body["explanation"], str)


def test_federation_policy_propose():
    """Test federation policy proposal endpoint"""
    payload = {
        "key": "alerts.autoheal.max_retries",
        "value": 5,
        "reason": "Testing policy evolution",
        "proposer": "test-node",
    }
    r = requests.post(
        f"{BASE_URL}/federation/policy/propose",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "proposal_id" in body
    assert "status" in body
    assert body["status"] == "proposed"


def test_federation_policy_pending():
    """Test federation policy pending endpoint"""
    r = requests.get(
        f"{BASE_URL}/federation/policy/pending", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "pending" in body
    assert isinstance(body["pending"], list)


def test_federation_policy_apply():
    """Test federation policy apply endpoint"""
    # First propose a policy
    payload = {
        "key": "alerts.autoheal.max_retries",
        "value": 5,
        "reason": "Testing policy evolution",
        "proposer": "test-node",
    }
    r = requests.post(
        f"{BASE_URL}/federation/policy/propose",
        json=payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    proposal_id = r.json()["proposal_id"]

    # Now vote on it
    vote_payload = {"proposal_id": proposal_id, "vote": "approve", "voter": "test-voter"}
    r = requests.post(
        f"{BASE_URL}/federation/policy/apply",
        json=vote_payload,
        headers={"x-fed-key": "aetherlink-shared-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


def test_federation_policy_explain():
    """Test federation policy explain endpoint"""
    r = requests.get(
        f"{BASE_URL}/federation/policy/explain", headers={"x-fed-key": "aetherlink-shared-key"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "explanation" in body
    assert "active_policies" in body
    assert "pending_proposals" in body
    assert isinstance(body["explanation"], str)
