"""
Test hybrid search functionality.
Tests semantic, lexical, and hybrid search modes.
"""
import pytest
from fastapi.testclient import TestClient
from pods.customer_ops.api.main import app

# Use test client
client = TestClient(app)

# Test API key
TEST_KEY = "test-key"

def test_semantic_search():
    """Test semantic-only search mode"""
    response = client.get(
        "/search?q=roof%20installation&k=3&mode=semantic",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert data["mode"] == "semantic"
    assert "results" in data
    assert "count" in data
    assert isinstance(data["results"], list)
    
    # Verify result structure
    if data["results"]:
        result = data["results"][0]
        assert "id" in result
        assert "content" in result
        assert "score" in result
        assert "score_semantic" in result
        assert "score_lex" in result
        assert result["score_semantic"] > 0  # Semantic mode should have semantic score


def test_lexical_search():
    """Test lexical-only search mode"""
    response = client.get(
        "/search?q=storm%20collar&k=3&mode=lexical",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert data["mode"] == "lexical"
    assert "results" in data
    
    # If results exist, verify at least one token appears in content
    if data["results"]:
        result = data["results"][0]
        content_lower = result["content"].lower()
        assert ("storm" in content_lower or "collar" in content_lower), \
            f"Expected 'storm' or 'collar' in result content: {content_lower[:100]}"
        assert result["score_lex"] > 0  # Lexical mode should have lexical score


def test_hybrid_search_default():
    """Test hybrid search (default mode)"""
    response = client.get(
        "/search?q=installation%20guide&k=3",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Default mode should be hybrid
    assert data["mode"] == "hybrid"
    assert "results" in data
    
    # Results should have both score types
    if data["results"]:
        result = data["results"][0]
        assert "score_semantic" in result
        assert "score_lex" in result
        # At least one score should be non-zero
        assert result["score_semantic"] > 0 or result["score_lex"] > 0


def test_hybrid_search_explicit():
    """Test hybrid search with explicit mode parameter"""
    response = client.get(
        "/search?q=metal%20roof&k=5&mode=hybrid",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["mode"] == "hybrid"
    assert data["count"] <= 5  # Respects k parameter
    
    # Verify results are sorted by score descending
    if len(data["results"]) > 1:
        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score"


def test_invalid_mode():
    """Test that invalid mode parameter returns 400"""
    response = client.get(
        "/search?q=test&mode=invalid",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 400
    assert "Invalid mode" in response.json()["detail"]


def test_hybrid_finds_keyword_matches():
    """Test that hybrid search surfaces keyword matches even if semantically different"""
    # First ingest a test document with specific keywords
    ingest_response = client.post(
        "/knowledge/ingest-text-async",
        headers={"x-api-key": TEST_KEY},
        json={
            "text": "The underlayment we use is synthetic felt with 50-year warranty.",
            "source": "test-hybrid-keyword"
        }
    )
    assert ingest_response.status_code == 200
    
    # Wait briefly for indexing (async job)
    import time
    time.sleep(0.5)
    
    # Search for exact keyword
    response = client.get(
        "/search?q=underlayment%20warranty&k=5&mode=hybrid",
        headers={"x-api-key": TEST_KEY}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should find the document with keyword match
    if data["results"]:
        # At least one result should have lexical score > 0
        lexical_scores = [r["score_lex"] for r in data["results"]]
        assert any(s > 0 for s in lexical_scores), "Hybrid should find keyword matches"


def test_rate_limiting():
    """Test that rate limiting is applied to search endpoint"""
    # Make many requests rapidly (should hit rate limit)
    responses = []
    for _ in range(65):  # Over the 60/min limit
        response = client.get(
            "/search?q=test&k=1",
            headers={"x-api-key": TEST_KEY}
        )
        responses.append(response.status_code)
    
    # At least one should be 429 (rate limited)
    assert 429 in responses, "Should hit rate limit with 65 requests"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
