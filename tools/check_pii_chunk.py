#!/usr/bin/env python3
"""Check what's actually stored in DuckDB for pii-test"""

import json

import duckdb

conn = duckdb.connect("/app/data/knowledge.duckdb")

# Find all chunks mentioning pii-test
rows = conn.execute("""
    SELECT id, substr(content,1,200) as snippet, metadata
    FROM chunks
    WHERE metadata LIKE '%pii-test%'
    LIMIT 1
""").fetchall()

if rows:
    for row in rows:
        print("=" * 60)
        print(f"ID: {row[0]}")
        print(f"\nSnippet:\n{row[1]}")
        print(f"\nMetadata:\n{json.dumps(json.loads(row[2]), indent=2)}")
        print("=" * 60)
else:
    print("No chunks found with pii-test in metadata")

    # List all sources
    print("\nAll sources in DB:")
    all_sources = conn.execute("""
        SELECT DISTINCT json_extract(metadata, '$.source') as src
        FROM chunks
        ORDER BY src
    """).fetchall()
    for s in all_sources:
        print(f"  - {s[0]}")

conn.close()
