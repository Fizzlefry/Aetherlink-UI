#!/usr/bin/env python3
"""Debug PII query matching"""

import duckdb

conn = duckdb.connect("/app/data/knowledge.duckdb")

# Test the exact query used in _count_pii_hits
doc_key = "pii-test"
key = doc_key.replace('"', '""')

print(f"Testing query for doc_key: {doc_key}")
print(f"Escaped key: {key}")

# Test pattern matching
result = conn.execute(f"""
    SELECT COUNT(*)
    FROM chunks
    WHERE metadata LIKE '%"url":"{key}%' OR metadata LIKE '%"source":"{key}%'
""").fetchone()

print(f"\nChunks matched: {result[0]}")

# Show what metadata actually looks like
result2 = conn.execute("""
    SELECT metadata FROM chunks WHERE metadata LIKE '%pii-test%' LIMIT 1
""").fetchone()

print(f"\nActual metadata: {result2[0][:200]}")

# Try the PII count query
result3 = conn.execute(f"""
    SELECT
        SUM(CAST(instr(content,'[EMAIL]')>0 AS INTEGER)) AS email,
        SUM(CAST(instr(content,'[PHONE]')>0 AS INTEGER)) AS phone,
        SUM(CAST(instr(content,'[SSN]')>0 AS INTEGER))   AS ssn,
        SUM(CAST(instr(content,'[CARD]')>0 AS INTEGER))  AS card
    FROM chunks
    WHERE metadata LIKE '%"source":"{key}%'
""").fetchone()

print(f"\nPII hits: EMAIL={result3[0]}, PHONE={result3[1]}, SSN={result3[2]}, CARD={result3[3]}")
