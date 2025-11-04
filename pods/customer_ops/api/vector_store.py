from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(x * x for x in b))
    return 0.0 if (da == 0 or db == 0) else num / (da * db)


class SQLiteVectorStore:
    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant TEXT NOT NULL,
            source TEXT,
            chunk TEXT NOT NULL,
            vector TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """)
        self.conn.commit()

    def upsert(
        self, tenant: str, source: str | None, chunks: list[str], vectors: list[list[float]]
    ):
        now = time.time()
        with self.conn:
            for c, v in zip(chunks, vectors, strict=False):
                self.conn.execute(
                    "INSERT INTO knowledge (tenant, source, chunk, vector, created_at) VALUES (?, ?, ?, ?, ?)",
                    (tenant, source, c, json.dumps(v), now),
                )

    def search(
        self, tenant: str, query_vec: list[float], top_k: int = 4, min_score: float = 0.15
    ) -> list[tuple[float, str, str | None]]:
        rows = self.conn.execute(
            "SELECT chunk, vector, source FROM knowledge WHERE tenant = ?", (tenant,)
        ).fetchall()
        scored: list[tuple[float, str, str | None]] = []
        for chunk, v_json, src in rows:
            vec = json.loads(v_json)
            s = _cosine(query_vec, vec)
            if s >= min_score:
                scored.append((s, chunk, src))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def list(self, tenant: str, limit: int = 50, q: str | None = None):
        """List knowledge entries for a tenant with optional text search."""
        cur = self.conn.cursor()
        if q:
            cur.execute(
                "SELECT id, source, chunk, created_at FROM knowledge WHERE tenant = ? AND chunk LIKE ? ORDER BY created_at DESC LIMIT ?",
                (tenant, f"%{q}%", limit),
            )
        else:
            cur.execute(
                "SELECT id, source, chunk, created_at FROM knowledge WHERE tenant = ? ORDER BY created_at DESC LIMIT ?",
                (tenant, limit),
            )
        rows = cur.fetchall()
        return [{"id": r[0], "source": r[1], "text": r[2], "created_at": r[3]} for r in rows]

    def delete(self, tenant: str, ids: list[str]):
        """Delete knowledge entries by IDs for a tenant."""
        cur = self.conn.cursor()
        qmarks = ",".join("?" for _ in ids)
        cur.execute(f"DELETE FROM knowledge WHERE tenant = ? AND id IN ({qmarks})", [tenant, *ids])
        self.conn.commit()
        return cur.rowcount

    def export_csv(self, tenant: str) -> str:
        """Export knowledge entries as CSV."""
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "source", "text", "created_at"])
        for row in self.list(tenant=tenant, limit=10_000):
            w.writerow([row["id"], row["source"], row["text"], row["created_at"]])
        return buf.getvalue()

    def project_umap(self, tenant: str, k: int = 200):
        """Project embeddings to 2D using UMAP or PCA fallback."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, source, chunk, vector FROM knowledge WHERE tenant = ? ORDER BY created_at DESC LIMIT ?",
            (tenant, k),
        )
        rows = cur.fetchall()
        if not rows:
            return []

        try:
            import numpy as np
        except ImportError:
            return []

        try:
            import umap

            has_umap = True
        except ImportError:
            has_umap = False

        embs = []
        meta = []
        for rid, source, text, emb_json in rows:
            e = json.loads(emb_json) if emb_json else None
            if e is not None:
                embs.append(np.array(e, dtype=float))
                meta.append((rid, source, text))

        if not embs:
            return []

        X = np.stack(embs)
        if has_umap:
            reducer = umap.UMAP(
                n_neighbors=min(10, len(embs) - 1), min_dist=0.15, metric="cosine", n_components=2
            )
            Y = reducer.fit_transform(X)
        else:
            # PCA fallback
            Xc = X - X.mean(0, keepdims=True)
            U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
            Y = Xc @ Vt[:2].T

        pts = []
        for (rid, source, text), (x, y) in zip(meta, Y, strict=False):
            pts.append(
                {"id": rid, "source": source, "text": text[:160], "x": float(x), "y": float(y)}
            )
        return pts

    def project_umap_csv(self, tenant: str, k: int = 200) -> str:
        """Export 2D projection as CSV."""
        import csv
        import io

        pts = self.project_umap(tenant=tenant, k=k)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "source", "x", "y", "text"])
        for p in pts:
            w.writerow([p["id"], p["source"], p["x"], p["y"], p["text"]])
        return buf.getvalue()
