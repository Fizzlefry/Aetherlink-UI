# RAG Reranker Implementation - Summary

## Overview
Added comprehensive reranking support to `/search` and `/answer` endpoints with confidence scoring, PII guards, and metrics.

## ✅ Features Implemented

### 1. Reranking Support
- **Embed Strategy**: Uses existing embedder to compute cosine similarity between query embedding and passage embeddings
- **Token Fallback**: Deterministic token hit counting when embedder unavailable (max 8 tokens)
- **Configurable**: `rerank=true` parameter and `rerank_topk` (3-50, default 10)
- **Graceful Degradation**: Automatically falls back to token strategy on embed failures

### 2. Confidence Scoring
- **Formula**: `0.6 * token_coverage + 0.4 * retrieval_strength`
- **Token Coverage**: Hits / (num_tokens * num_sentences)
- **Retrieval Strength**: Average of top-3 fused scores
- **Threshold**: Abstains from answers when confidence < 0.25

### 3. PII Guards
- **Detection**: Checks for `[SSN]`, `[CARD]`, `[EMAIL]`, `[PHONE]` placeholders
- **Refusal**: Returns helpful message instead of exposing PII
- **Safety**: Prevents accidental leakage of sensitive redacted content

### 4. Answer Metrics
- **`aether_rag_answers_total{mode, rerank}`**: Counter for all answers generated
- **`aether_rag_lowconfidence_total`**: Counter for low-confidence answers
- **Prometheus Export**: Available at `/metrics` endpoint

### 5. Citation Deduplication
- **URL Dedup**: Uses `_uniq_by()` to prevent duplicate sources
- **Snippet Length**: 220 characters (up from 180)
- **Max Citations**: 3 per answer

### 6. Answer Synthesis Enhancement
- **Return Type**: Now returns `Tuple[str, List[str]]` with answer text and used sentences
- **Confidence Input**: Used sentences feed into confidence calculation
- **Token Matching**: 1+ hits required for sentence inclusion

## 📝 Code Changes

### Helper Functions Added (main.py lines 1011-1042)
```python
_confidence(query, topk, used)  # Confidence scoring
_pii_guard(answer)              # PII detection and refusal
```

### Helper Functions Enhanced (main.py lines 936-1076)
```python
_cosine(a, b)                   # Vector similarity
_rerank_embed(query, candidates, topk)   # Embedder-based rerank
_rerank_token(query, candidates, topk)   # Token hit fallback
_uniq_by(results, key)          # Deduplicate by metadata key
_make_citations(results, max_cites)      # Enhanced with dedup
_synthetic_answer(query, chunks, max_chars)  # Returns (answer, sentences)
```

### Metrics Added (main.py lines 308-309)
```python
ANSWERS_TOTAL = Counter("aether_rag_answers_total", "RAG answers generated", ["mode", "rerank"])
LOWCONF_TOTAL = Counter("aether_rag_lowconfidence_total", "Low confidence answers")
```

### Endpoints Updated

#### `/search` Endpoint (main.py lines 812-932)
- Added `rerank: bool = Query(False)`
- Added `rerank_topk: int = Query(10, ge=3, le=50)`
- Retrieval adjusts to `rerank_topk*2` when rerank=true
- Applies `_rerank_embed()` with fallback to `_rerank_token()`
- Returns `reranked` and `rerank_used` fields

#### `/answer` Endpoint (main.py lines 1091-1233)
- Added `rerank` and `rerank_topk` parameters
- Applies reranking after retrieval
- Deduplicates citations by URL
- Checks PII with `_pii_guard()`
- Calculates confidence with `_confidence()`
- Abstains if confidence < 0.25
- Increments metrics counters
- Returns `confidence`, `rerank_used`, and optional `pii_blocked` fields

## 🧪 Testing

### REST Client Examples (.vscode/aether_admin.http)
```http
### Search with Reranking (Hybrid + Embed)
GET {{base}}/search?q=storm%20collar%20installation&k=3&mode=hybrid&rerank=true&rerank_topk=10
x-api-key: {{apiKey}}

### Answer with Reranking (Hybrid + Embed)
GET {{base}}/answer?q=roof%20warranty%20coverage&k=5&mode=hybrid&rerank=true&rerank_topk=15
x-admin-key: {{adminKey}}

### Answer with Confidence Check
GET {{base}}/answer?q=how%20to%20install%20gutters&k=5&mode=hybrid&rerank=true
x-admin-key: {{adminKey}}
```

### Evaluation Harness (tools/eval_answers.py)
```bash
python tools/eval_answers.py --api-key test-key
```

**Test Cases** (tools/eval_answers.jsonl):
- Storm collar installation (must: storm, collar)
- Account number format (must: account, avoid: [SSN], [CARD])
- Emergency repair pricing (must: repair, price, emergency)
- Roofing warranty details (must: warranty)

**Checks**:
- ✅ Required tokens present
- ✅ PII markers avoided
- ⚠️  Confidence >= 0.25 (warns but doesn't fail)

## 📊 Response Schema

### `/search` Response
```json
{
  "ok": true,
  "mode": "hybrid",
  "query": "storm collar installation",
  "results": [...],
  "count": 3,
  "reranked": true,
  "rerank_used": "embed"
}
```

### `/answer` Response (Success)
```json
{
  "answer": "Storm collar installation requires...",
  "citations": [
    {"url": "...", "snippet": "..."},
    {"url": "...", "snippet": "..."}
  ],
  "used_mode": "hybrid",
  "rerank_used": "embed",
  "confidence": 0.742
}
```

### `/answer` Response (Low Confidence)
```json
{
  "answer": "I found some related information but cannot confidently answer this question (confidence: 0.18). Please review the citations below.",
  "citations": [...],
  "used_mode": "hybrid",
  "rerank_used": "token",
  "confidence": 0.18
}
```

### `/answer` Response (PII Blocked)
```json
{
  "answer": "This answer contains sensitive PII. Please open the cited source with proper permissions.",
  "citations": [...],
  "used_mode": "semantic",
  "rerank_used": "none",
  "confidence": 0.0,
  "pii_blocked": true
}
```

## 🎯 Production Readiness

### Observability
- ✅ Prometheus metrics for answers and low confidence
- ✅ Rerank strategy tracking (embed vs token)
- ✅ Mode tracking (semantic, lexical, hybrid)

### Safety
- ✅ PII guard prevents exposure of redacted data
- ✅ Confidence threshold prevents low-quality answers
- ✅ Fallback strategies (embed → token → none)

### Performance
- ✅ Efficient cosine computation with null checks
- ✅ Token counting limited to 8 tokens max
- ✅ Configurable rerank_topk (3-50) for tuning

### Testing
- ✅ REST Client examples for manual testing
- ✅ Automated eval harness with pass/fail checks
- ✅ CI-ready (exit code 1 on failures)

## 🚀 Next Steps

1. **Run Eval Harness**: `python tools/eval_answers.py --api-key test-key`
2. **Test Rerank**: Use REST Client examples in `.vscode/aether_admin.http`
3. **Monitor Metrics**: Check Grafana for `aether_rag_answers_total` and `aether_rag_lowconfidence_total`
4. **Tune Thresholds**: Adjust confidence threshold (currently 0.25) based on eval results
5. **Add More Test Cases**: Expand `eval_answers.jsonl` with domain-specific queries

## 📦 Files Modified

- ✅ `pods/customer_ops/api/main.py` - Core rerank implementation
- ✅ `.vscode/aether_admin.http` - REST Client examples
- ✅ `tools/eval_answers.py` - Evaluation harness
- ✅ `tools/eval_answers.jsonl` - Test cases

**Total Lines Added**: ~200 lines of production code + ~120 lines of testing infrastructure
