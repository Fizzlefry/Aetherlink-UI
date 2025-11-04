import os

os.environ["DUCKDB_PATH"] = "/app/data/knowledge.duckdb"
from pods.customer_ops.db_duck import get_conn

conn = get_conn("/app/data/knowledge.duckdb")
result = conn.execute(
    "SELECT id, tenant_id, LEFT(content, 50) as content_preview FROM chunks LIMIT 5;"
).fetchall()
print("Rows in database:")
for r in result:
    print(f"  ID: {r[0]}, Tenant: {r[1]}, Content: {r[2]}...")

total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
print(f"\nTotal chunks: {total}")
conn.close()
