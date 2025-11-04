"""
Test suite for DuckDB + VSS vector search.

Tests:
- Semantic search accuracy (query matching)
- INSERT OR REPLACE (upsert behavior)
- Tenant filtering
"""
import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pods.customer_ops.db_duck import get_conn, upsert_chunks, query_embeddings

# Test embeddings (simplified 3-dimensional for testing)
# In production, these would be 1536-dimensional OpenAI embeddings
# For testing, we use 3D vectors to visualize semantic similarity

def create_test_embedding(values):
    """
    Create a test embedding vector.
    In production this would be 1536 dims, but for testing we use smaller vectors.
    DuckDB VSS will pad/truncate to match schema.
    """
    # Pad to 1536 dimensions (DuckDB expects FLOAT[1536])
    padded = values + [0.0] * (1536 - len(values))
    return padded

def test_semantic_search():
    """Test that semantically similar queries return correct chunks."""
    print("\n🧪 Test 1: Semantic search accuracy")
    
    # Clean test database
    test_db = "data/test_knowledge.duckdb"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Seed test data with distinctive embeddings
    chunks = [
        {
            "id": "chunk-1",
            "content": "Python is a programming language",
            "embedding": create_test_embedding([1.0, 0.0, 0.0]),  # Programming vector
            "metadata": {"topic": "programming"}
        },
        {
            "id": "chunk-2",
            "content": "The weather today is sunny",
            "embedding": create_test_embedding([0.0, 1.0, 0.0]),  # Weather vector
            "metadata": {"topic": "weather"}
        },
        {
            "id": "chunk-3",
            "content": "JavaScript is also a programming language",
            "embedding": create_test_embedding([0.9, 0.1, 0.0]),  # Similar to programming
            "metadata": {"topic": "programming"}
        },
    ]
    
    # Upsert chunks
    metadata = {"source": "test", "ingested_at": time.time()}
    os.environ["DUCKDB_PATH"] = test_db
    count = upsert_chunks(chunks, metadata=metadata, tenant_id="test-tenant")
    assert count == 3, f"Expected 3 chunks upserted, got {count}"
    
    # Query with programming-related embedding
    query_vec = create_test_embedding([0.95, 0.05, 0.0])  # Very close to chunk-1
    results = query_embeddings(query_vec, tenant_id="test-tenant", top_k=2)
    
    # Verify results
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert results[0]["id"] == "chunk-1", f"Expected chunk-1 first, got {results[0]['id']}"
    assert results[0]["content"] == "Python is a programming language"
    assert results[0]["distance"] < 0.1, f"Expected low distance, got {results[0]['distance']}"
    
    print("✅ PASS  Semantic search ranks correct chunks by similarity")
    print(f"         Top result: {results[0]['id']} (distance: {results[0]['distance']:.4f})")

def test_upsert_replace():
    """Test that INSERT OR REPLACE updates existing chunks."""
    print("\n🧪 Test 2: INSERT OR REPLACE (upsert behavior)")
    
    test_db = "data/test_knowledge.duckdb"
    os.environ["DUCKDB_PATH"] = test_db
    
    # Insert initial chunk
    chunks_v1 = [
        {
            "id": "chunk-update-test",
            "content": "Original content v1",
            "embedding": create_test_embedding([0.5, 0.5, 0.0]),
            "metadata": {"version": "v1"}
        }
    ]
    
    metadata_v1 = {"source": "test-v1"}
    count1 = upsert_chunks(chunks_v1, metadata=metadata_v1, tenant_id="test-tenant")
    assert count1 == 1
    
    # Update same chunk (same ID, different content)
    chunks_v2 = [
        {
            "id": "chunk-update-test",  # Same ID
            "content": "Updated content v2",
            "embedding": create_test_embedding([0.6, 0.4, 0.0]),
            "metadata": {"version": "v2"}
        }
    ]
    
    metadata_v2 = {"source": "test-v2"}
    count2 = upsert_chunks(chunks_v2, metadata=metadata_v2, tenant_id="test-tenant")
    assert count2 == 1
    
    # Query to verify update
    query_vec = create_test_embedding([0.6, 0.4, 0.0])
    results = query_embeddings(query_vec, tenant_id="test-tenant", top_k=10)
    
    # Should only have one chunk with this ID (replaced, not duplicated)
    matching = [r for r in results if r["id"] == "chunk-update-test"]
    assert len(matching) == 1, f"Expected 1 chunk, got {len(matching)} (duplicate not replaced)"
    assert matching[0]["content"] == "Updated content v2", "Content not updated"
    assert matching[0]["metadata"]["source"] == "test-v2", "Metadata not updated"
    
    print("✅ PASS  INSERT OR REPLACE updates existing chunks (no duplicates)")
    print(f"         Updated content: {matching[0]['content']}")

def test_tenant_filtering():
    """Test that tenant filtering works correctly."""
    print("\n🧪 Test 3: Tenant filtering")
    
    test_db = "data/test_knowledge.duckdb"
    os.environ["DUCKDB_PATH"] = test_db
    
    # Insert chunks for different tenants
    tenant_a_chunks = [
        {
            "id": "tenant-a-chunk-1",
            "content": "Tenant A data",
            "embedding": create_test_embedding([0.1, 0.1, 0.1]),
            "metadata": {"owner": "tenant-a"}
        }
    ]
    
    tenant_b_chunks = [
        {
            "id": "tenant-b-chunk-1",
            "content": "Tenant B data",
            "embedding": create_test_embedding([0.1, 0.1, 0.1]),  # Same embedding
            "metadata": {"owner": "tenant-b"}
        }
    ]
    
    upsert_chunks(tenant_a_chunks, metadata={"source": "a"}, tenant_id="tenant-a")
    upsert_chunks(tenant_b_chunks, metadata={"source": "b"}, tenant_id="tenant-b")
    
    # Query tenant A
    query_vec = create_test_embedding([0.1, 0.1, 0.1])
    results_a = query_embeddings(query_vec, tenant_id="tenant-a", top_k=10)
    
    # Verify only tenant A data returned
    assert len(results_a) == 1, f"Expected 1 result for tenant-a, got {len(results_a)}"
    assert results_a[0]["id"] == "tenant-a-chunk-1"
    assert results_a[0]["metadata"]["owner"] == "tenant-a"
    
    # Query tenant B
    results_b = query_embeddings(query_vec, tenant_id="tenant-b", top_k=10)
    
    # Verify only tenant B data returned
    assert len(results_b) == 1, f"Expected 1 result for tenant-b, got {len(results_b)}"
    assert results_b[0]["id"] == "tenant-b-chunk-1"
    assert results_b[0]["metadata"]["owner"] == "tenant-b"
    
    print("✅ PASS  Tenant filtering isolates data correctly")
    print(f"         Tenant A: {results_a[0]['id']}, Tenant B: {results_b[0]['id']}")

def test_null_tenant():
    """Test querying with NULL tenant filter."""
    print("\n🧪 Test 4: NULL tenant filtering")
    
    test_db = "data/test_knowledge.duckdb"
    os.environ["DUCKDB_PATH"] = test_db
    
    # Insert chunk with NULL tenant
    null_tenant_chunks = [
        {
            "id": "null-tenant-chunk",
            "content": "No tenant assigned",
            "embedding": create_test_embedding([0.2, 0.2, 0.2]),
            "metadata": {"public": True}
        }
    ]
    
    upsert_chunks(null_tenant_chunks, metadata={"source": "public"}, tenant_id=None)
    
    # Query with NULL tenant
    query_vec = create_test_embedding([0.2, 0.2, 0.2])
    results_null = query_embeddings(query_vec, tenant_id=None, top_k=10)
    
    # Should return NULL tenant chunks
    null_chunks = [r for r in results_null if r["id"] == "null-tenant-chunk"]
    assert len(null_chunks) == 1, f"Expected 1 NULL tenant chunk, got {len(null_chunks)}"
    
    print("✅ PASS  NULL tenant filtering works")
    print(f"         Found chunk: {null_chunks[0]['id']}")

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 DuckDB + VSS Vector Search Test Suite")
    print("=" * 70)
    
    try:
        test_semantic_search()
        test_upsert_replace()
        test_tenant_filtering()
        test_null_tenant()
        
        print("\n" + "=" * 70)
        print("🎉 ALL DUCKDB VECTOR TESTS PASSED!")
        print("=" * 70)
        print("\nScore: 4/4 tests passed")
        
    except AssertionError as e:
        print(f"\n❌ FAIL  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR  {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
