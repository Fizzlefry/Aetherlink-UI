from pathlib import Path

import pytest

from pods.customer_ops.knowledge.rag import RAG


def get_test_db_url():
    """Get test database URL - using same dev DB for simplicity"""
    return None  # will use default dev DB from docker-compose


@pytest.fixture
def rag():
    """Initialize RAG system with test database"""
    rag = RAG(database_url=get_test_db_url())
    rag.ensure_schema()
    return rag


def test_faq_retrieval(rag):
    """Test that seeded FAQ data returns relevant results"""
    # First seed some test data
    data_dir = Path(__file__).parent.parent / "data"
    faq_path = data_dir / "sample_faq.txt"

    with open(faq_path, encoding="utf-8") as f:
        from pods.customer_ops.knowledge.seed_faq import parse_qa_pairs

        qa_pairs = parse_qa_pairs(f.read())

    # Store test documents
    rag.upsert_docs(qa_pairs)

    # Test query about underlayment
    query = "What underlayment do you use?"
    results = rag.query(query, k=1)

    assert len(results) > 0, "Should return at least one result"
    doc_id, text, score = results[0]

    # Basic relevance checks - with hash-based embeddings, expect moderate cosine sim
    # The test embedding might return slightly lower similarity than TF-IDF,
    # but should still give meaningful results. Assert at least weak relevance.
    assert score >= 0.2, "Should have at least weak relevance"
    assert "underlayment" in text.lower(), "Response should mention underlayment"
    assert "30-pound" in text, "Should return the correct underlayment spec"
