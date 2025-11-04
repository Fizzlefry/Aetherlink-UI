"""
Test /answer endpoint with citations.
"""

from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app

# Test client
client = TestClient(app)

# Test API key
TEST_KEY = "test-key"
ADMIN_KEY = "admin-secret-123"


def test_answer_returns_citations_and_text():
    """Test that /answer returns answer text and citations"""
    response = client.get(
        "/answer",
        params={"q": "storm collar installation", "k": 5, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()

    # Check answer text
    assert isinstance(data.get("answer", ""), str)
    assert len(data["answer"]) > 20, "Answer should be substantial"

    # Check citations
    cites = data.get("citations", [])
    assert isinstance(cites, list)
    assert len(cites) >= 1, "Should have at least one citation"

    # Verify citation structure
    assert "url" in cites[0]
    assert "snippet" in cites[0]
    assert isinstance(cites[0]["url"], str)
    assert isinstance(cites[0]["snippet"], str)

    # Check mode
    assert data["used_mode"] == "hybrid"


def test_answer_semantic_mode():
    """Test /answer with semantic-only mode"""
    response = client.get(
        "/answer",
        params={"q": "roof warranty", "k": 3, "mode": "semantic"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["used_mode"] == "semantic"
    assert "answer" in data
    assert "citations" in data


def test_answer_lexical_mode():
    """Test /answer with lexical-only mode"""
    response = client.get(
        "/answer",
        params={"q": "audit test", "k": 3, "mode": "lexical"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["used_mode"] == "lexical"
    assert "answer" in data


def test_answer_no_results():
    """Test /answer when no results found"""
    response = client.get(
        "/answer",
        params={"q": "xyzabc123nonexistent", "k": 5, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()

    # Should return helpful message
    assert "couldn't find" in data["answer"].lower() or len(data["citations"]) == 0


def test_answer_validates_k_parameter():
    """Test that k parameter is bounded 1-10"""
    # k too high should be capped
    response = client.get(
        "/answer",
        params={"q": "test", "k": 20, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )
    assert response.status_code in [200, 422]  # May validate or cap

    # k=0 should fail validation
    response = client.get(
        "/answer",
        params={"q": "test", "k": 0, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )
    assert response.status_code == 422


def test_answer_citations_have_snippets():
    """Test that citations include content snippets"""
    response = client.get(
        "/answer",
        params={"q": "test document", "k": 5, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()

    if data["citations"]:
        for cite in data["citations"]:
            assert "snippet" in cite
            assert len(cite["snippet"]) > 0, "Snippet should not be empty"
            assert len(cite["snippet"]) <= 180, "Snippet should be trimmed"


def test_answer_uses_query_tokens():
    """Test that answer contains relevant query tokens"""
    response = client.get(
        "/answer",
        params={"q": "audit log test", "k": 5, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()

    # Answer should mention at least one query token
    answer_lower = data["answer"].lower()
    assert any(token in answer_lower for token in ["audit", "log", "test"])


def test_answer_max_3_citations():
    """Test that citations are capped at 3"""
    response = client.get(
        "/answer",
        params={"q": "test", "k": 10, "mode": "hybrid"},
        headers={"x-admin-key": ADMIN_KEY},
    )

    assert response.status_code == 200
    data = response.json()

    # Should have max 3 citations
    assert len(data["citations"]) <= 3


def test_answer_rate_limiting():
    """Test that rate limiting applies to /answer"""
    # Make many requests rapidly
    responses = []
    for _ in range(65):
        response = client.get(
            "/answer",
            params={"q": "test", "k": 1, "mode": "semantic"},
            headers={"x-admin-key": ADMIN_KEY},
        )
        responses.append(response.status_code)

    # Should hit rate limit
    assert 429 in responses


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
