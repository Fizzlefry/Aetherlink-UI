#!/bin/bash
# Quick test for the remediation history endpoint
# Usage: ./test_remediation_endpoint.sh

BASE_URL="${1:-http://localhost:8010}"

echo "=========================================="
echo "Testing Remediation History Endpoint"
echo "=========================================="
echo ""

# Test 1: Get all events
echo "1. Fetching all events (limit 10)..."
curl -s "$BASE_URL/ops/remediate/history?limit=10" | python -m json.tool
echo ""

# Test 2: Filter by tenant
echo "2. Testing tenant filter..."
curl -s "$BASE_URL/ops/remediate/history?tenant=test-tenant&limit=5" | python -m json.tool
echo ""

# Test 3: Test with high limit
echo "3. Testing with limit=20..."
curl -s "$BASE_URL/ops/remediate/history?limit=20" | python -m json.tool
echo ""

echo "=========================================="
echo "Test complete!"
echo "=========================================="
