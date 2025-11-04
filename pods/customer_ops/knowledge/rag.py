from __future__ import annotations

import logging
import os
from typing import cast

"""Lightweight RAG helper.

This module avoids importing heavy ML libraries at module import time so
the API can start in environments without numpy/scikit-learn/pgvector.
The real ML dependencies are imported lazily inside methods; when they're
missing we fall back to a safe, deterministic stub embedding so the app
still starts and health checks work.
"""

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import select

# Try to import optional heavy dependencies; if unavailable, we set flags
HAS_NUMPY = False
HAS_SKLEARN = False
HAS_PGVECTOR = False

try:
    import numpy as np

    HAS_NUMPY = True
except Exception:
    np = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer

    HAS_SKLEARN = True
except Exception:
    TfidfVectorizer = None

try:
    from pgvector.sqlalchemy import Vector

    HAS_PGVECTOR = True
except Exception:
    Vector = None


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TF-IDF embedding dimension
VECTOR_DIM = 384


def get_database_url() -> str:
    """Get database URL from environment variables with defaults matching docker-compose"""
    # Allow explicit DATABASE_URL override (useful for tests)
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    DB_USER = os.getenv("POSTGRES_USER", "aether")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "devpass")
    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "aetherlink")
    return f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Initialize MetaData instance
metadata = MetaData()

# Choose embedding column type depending on availability of pgvector
if HAS_PGVECTOR and Vector is not None:
    embedding_type = Vector(VECTOR_DIM)
else:
    # Store embeddings as JSON-like strings when pgvector isn't available
    embedding_type = String

documents = Table(
    "rag_documents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("text", String, nullable=False),
    Column("embedding", embedding_type),
)

import json


class RAG:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or get_database_url()
        self.engine = create_engine(self.database_url)
        # Lazy initialize TF-IDF vectorizer if sklearn is available
        if HAS_SKLEARN and TfidfVectorizer is not None:
            self.tfidf = TfidfVectorizer()
        else:
            self.tfidf = None

    def ensure_schema(self) -> None:
        """Create tables and vector extension if they don't exist"""
        with self.engine.connect() as conn:
            # Enable vector extension only on Postgres
            try:
                if conn.dialect.name == "postgresql" and HAS_PGVECTOR and Vector is not None:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
            except Exception:
                logger.info("vector extension not created or not supported on this dialect")

        metadata.create_all(self.engine)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts. If ML libs are missing,
        falls back to deterministic but simple term frequency hashes that
        will still yield meaningful similarity in test cases.
        """
        if not (HAS_SKLEARN and HAS_NUMPY and self.tfidf is not None):
            # Term frequency stub: Replace zeros with a simple deterministic
            # hash mapping each word to different vector elements; this
            # ensures similar texts map to similar vectors in tests.
            def quick_hash(text: str) -> list[float]:
                out = [0.0] * VECTOR_DIM
                words = [w.lower() for w in text.replace("?", "").replace("\n", " ").split()]
                # TF + rough word proximity: give higher weight to words near start
                # since questions have the key terms early.
                for i, w in enumerate(words):
                    # hash word to deterministic vector element
                    pos = sum(ord(c) for c in w) % VECTOR_DIM
                    # decay weight by position (1.0 -> 0.5)
                    weight = 1.0 / (1.0 + i / len(words))
                    out[pos] = out[pos] + weight
                # normalize
                total = sum(x * x for x in out) ** 0.5  # length
                if total > 0:
                    out = [x / total for x in out]
                return out

            return [quick_hash(t) for t in texts]

        # If ML libs are available, use proper TF-IDF
        if not hasattr(self.tfidf, "vocabulary_") or self.tfidf.vocabulary_ is None:
            self.tfidf.fit(texts)

        vectors = self.tfidf.transform(texts)
        normalized = vectors / np.sqrt((vectors.multiply(vectors)).sum(1))
        padded = np.zeros((len(texts), VECTOR_DIM))
        n_features = min(vectors.shape[1], VECTOR_DIM)
        padded[:, :n_features] = normalized[:, :n_features].toarray()
        return padded.tolist()

    def upsert_docs(self, pairs: list[tuple[str, str]]) -> list[tuple[int, str]]:
        texts = [f"Q: {q}\nA: {a}" for q, a in pairs]
        embeddings = self.embed(texts)

        result_ids = []
        with self.engine.connect() as conn:
            for text, embedding in zip(texts, embeddings, strict=False):
                embed_val = (
                    embedding if HAS_PGVECTOR and Vector is not None else json.dumps(embedding)
                )
                # SQLite doesn't support ON CONFLICT on arbitrary columns unless
                # they are declared UNIQUE; to keep tests hermetic using in-memory
                # SQLite, we do a simple update-if-exists else insert logic.
                if conn.dialect.name == "sqlite":
                    # try update first
                    res = conn.execute(
                        documents.update()
                        .where(documents.c.text == text)
                        .values(embedding=embed_val)
                    )
                    if res.rowcount:
                        # fetch the id of the updated row
                        row = conn.execute(
                            select(documents.c.id).where(documents.c.text == text)
                        ).fetchone()
                        doc_id = row[0] if row else None
                    else:
                        r = conn.execute(documents.insert().values(text=text, embedding=embed_val))
                        # SQLite + SQLAlchemy may not return inserted PK via execute; fetch it
                        doc_id = r.lastrowid
                    result_ids.append(doc_id)
                else:
                    stmt = (
                        insert(documents)
                        .values(
                            text=text,
                            embedding=embed_val,
                        )
                        .on_conflict_do_update(
                            index_elements=["text"], set_=dict(embedding=embed_val)
                        )
                        .returning(documents.c.id)
                    )
                    result = conn.execute(stmt)
                    doc_id = result.scalar_one()
                    result_ids.append(doc_id)
            conn.commit()

        return [(id_, text) for id_, text in zip(result_ids, texts, strict=False)]

    def query(self, question: str, k: int = 3) -> list[tuple[int, str, float]]:
        query_embedding = self.embed([question])[0]

        results = []
        with self.engine.connect() as conn:
            if HAS_PGVECTOR and Vector is not None:
                stmt = (
                    select(
                        documents.c.id,
                        documents.c.text,
                        documents.c.embedding.cosine_distance(query_embedding).label("distance"),
                    )
                    .order_by("distance")
                    .limit(k)
                )
                for row in conn.execute(stmt):
                    score = 1 - cast(float, row.distance)
                    results.append((row.id, row.text, score))
            else:
                # Fallback: compute cosine similarity against stored JSON/text embeddings.
                # This works for tests since we have simple deterministic embeddings.
                scores = []
                stmt = select(documents.c.id, documents.c.text, documents.c.embedding).limit(50)
                for row in conn.execute(stmt):
                    doc_embedding = (
                        json.loads(row.embedding)
                        if isinstance(row.embedding, str)
                        else row.embedding
                    )
                    # cosine similarity: dot product of normalized vectors
                    dot = sum(a * b for a, b in zip(query_embedding, doc_embedding, strict=False))
                    scores.append((row.id, row.text, max(0.0, min(1.0, dot))))  # clip to [0,1]
                # sort by score descending and take top k
                scores.sort(key=lambda x: -x[2])  # minus for descending
                results = scores[:k]

        return results
