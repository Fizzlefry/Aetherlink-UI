"""RQ Worker entrypoint for background tasks (follow-ups + ingestion)."""
import os
import time
import logging
from typing import Dict, Any

import redis
from rq import Queue, Worker

# Import DuckDB vector store functions
from pods.customer_ops.db_duck import upsert_chunks as duck_upsert
# Import PII redaction
from pods.customer_ops.pii import redact_text, parse_pii_config

# Prometheus metrics
from prometheus_client import Counter, Gauge, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("worker")

# Worker metrics
JOBS_OK = Counter("aether_worker_jobs_ok_total", "Jobs processed OK", ["type"])
JOBS_FAIL = Counter("aether_worker_jobs_failed_total", "Jobs failed", ["type"])
QUEUE_SIZE = Gauge("aether_worker_queue_depth", "Jobs queued")

# Start metrics HTTP server
METRICS_PORT = int(os.getenv("WORKER_METRICS_PORT", "9100"))
try:
    start_http_server(METRICS_PORT)
    log.info("Worker metrics server started on port %d", METRICS_PORT)
except Exception as e:
    log.warning("Could not start metrics server: %s", e)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DB_PATH = os.getenv("DATABASE_URL", "sqlite:////app/local.db").replace("sqlite:///", "")

# PII Redaction Configuration
PII_REDACT_ENABLED = os.getenv("PII_REDACT", "on").lower() == "on"
PII_REDACT_TYPES_STR = os.getenv("PII_REDACT_TYPES", "email,phone,ssn,cc")
PII_PLACEHOLDERS_STR = os.getenv("PII_PLACEHOLDERS", "email:[EMAIL],phone:[PHONE],ssn:[SSN],cc:[CARD]")
PII_TYPES, PII_PLACEHOLDERS = parse_pii_config(PII_REDACT_TYPES_STR, PII_PLACEHOLDERS_STR)

log.info("PII Redaction: %s (types: %s)", "ENABLED" if PII_REDACT_ENABLED else "DISABLED", sorted(PII_TYPES) if PII_REDACT_ENABLED else "N/A")

def _store():
    """Get vector store instance."""
    from pods.customer_ops.api.vector_store import SQLiteVectorStore
    return SQLiteVectorStore(db_path=DB_PATH)

def _embedder():
    """Get embedder instance."""
    from pods.customer_ops.api.embeddings import build_embedder
    from pods.customer_ops.api.config import get_settings
    settings = get_settings()
    provider = os.getenv("EMBED_PROVIDER", "gemini")
    model = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    return build_embedder(provider, model, settings)

def _chunk(text: str, max_len: int = 800):
    """Simple text chunker."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    for i in range(0, len(text), max_len):
        chunk = text[i:i+max_len].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def ingest_text_job(text: str, source: str, tenant: str = "default") -> Dict[str, Any]:
    """Background job: Ingest raw text into vector store."""
    t0 = time.perf_counter()
    log.info("Starting ingest_text_job: tenant=%s source=%s text_len=%d", tenant, source, len(text))
    
    try:
        # Apply PII redaction before processing
        if PII_REDACT_ENABLED:
            text = redact_text(text, PII_TYPES, PII_PLACEHOLDERS)
            log.info("PII redaction applied: types=%s", sorted(PII_TYPES))
        
        store = _store()
        embedder = _embedder()
        
        chunks = _chunk(text)
        if not chunks:
            log.warning("No chunks produced from text")
            return {"ok": False, "error": "no_text"}
        
        vectors = embedder.embed(chunks)
        
        # Prepare chunks for DuckDB (with embeddings)
        import uuid
        duck_chunks = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{tenant}:{source}:{uuid.uuid4().hex[:8]}:{i}"
            duck_chunks.append({
                "id": chunk_id,
                "content": chunk_text,
                "embedding": embedding,
                "metadata": {}
            })
        
        # Upsert to DuckDB
        metadata = {
            "source": source,
            "ingested_at": time.time(),
            "pii_redaction": {
                "enabled": PII_REDACT_ENABLED,
                "types": sorted(list(PII_TYPES)) if PII_REDACT_ENABLED else []
            }
        }
        duck_count = duck_upsert(duck_chunks, metadata=metadata, tenant_id=tenant)
        log.info("DuckDB upsert: %d chunks", duck_count)
        
        # Mirror to SQLite if feature flag enabled
        if os.getenv("DUCKDB_MIRROR_SQLITE", "0") == "1":
            store.upsert(tenant=tenant, source=source, chunks=chunks, vectors=vectors)
            log.info("Mirrored to SQLite (DUCKDB_MIRROR_SQLITE=1)")
        
        dt = (time.perf_counter() - t0) * 1000.0
        log.info("ingest_text_job done: tenant=%s source=%s chunks=%d latency_ms=%.1f", 
                 tenant, source, len(chunks), dt)
        
        # Audit log
        try:
            from pods.customer_ops.audit import append_event
            append_event({
                "type": "ingest-text",
                "tenant_id": tenant,
                "source": source,
                "chunks": duck_count,
                "latency_ms": round(dt, 1),
                "metadata": metadata
            })
        except Exception as audit_err:
            log.warning("Audit logging failed: %s", audit_err)
        
        # Record success metrics
        JOBS_OK.labels("ingest-text").inc()
        
        return {
            "ok": True,
            "ingested_chunks": len(chunks),
            "tenant": tenant,
            "source": source,
            "latency_ms": round(dt, 1)
        }
    except Exception as e:
        log.exception("ingest_text_job failed: %s", e)
        JOBS_FAIL.labels("ingest-text").inc()
        return {"ok": False, "error": str(e)}

def _fetch_and_extract_readable(url: str, timeout=(7, 20)):
    """
    Fetch URL and extract clean article text using trafilatura.
    Returns: (readable_dict, raw_fallback)
    """
    try:
        import requests
        import trafilatura
        
        # Configure session with proper headers
        headers = {
            "User-Agent": "AetherLink-Ingest/1.0 (+https://example.local) requests",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        content_type = r.headers.get("Content-Type", "").lower()
        
        # Check if HTML
        is_html = any(ct in content_type for ct in ["text/html", "application/xhtml+xml"])
        
        if not is_html:
            # Non-HTML content, return raw text if available
            try:
                return None, r.text if r.text else None
            except:
                return None, None
        
        # Extract readable content with trafilatura
        downloaded = r.text
        
        # Configure for high recall
        config = trafilatura.settings.use_config()
        config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")
        
        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_links=False,
            include_tables=False,
            with_metadata=True,
            favor_recall=True,
            url=r.url,
            config=config,
        )
        
        if not extracted:
            return None, downloaded
        
        # Extract metadata
        try:
            meta = trafilatura.extract_metadata(downloaded, default_url=r.url)
        except:
            meta = None
        
        readable = {
            "title": meta.title if meta and hasattr(meta, 'title') and meta.title else None,
            "text": extracted.strip(),
            "url": r.url,  # Canonical URL after redirects
            "lang": meta.lang if meta and hasattr(meta, 'lang') and meta.lang else None,
            "date": meta.date if meta and hasattr(meta, 'date') and meta.date else None,
        }
        
        return readable, None
        
    except Exception as e:
        log.warning("fetch_and_extract_readable failed: %s", e)
        return None, None

def ingest_url_job(url: str, source: str, tenant: str = "default") -> Dict[str, Any]:
    """Background job: Fetch URL and ingest content with clean text extraction."""
    import re
    
    t0 = time.perf_counter()
    log.info("Starting ingest_url_job: url=%s tenant=%s source=%s", url, tenant, source)
    
    try:
        # Fetch and extract readable content
        readable, raw_fallback = _fetch_and_extract_readable(url)
        
        # Decide what content to use
        if readable and readable.get("text"):
            content = readable["text"]
            metadata = {
                "url": readable["url"],
                "title": readable.get("title"),
                "lang": readable.get("lang"),
                "published": readable.get("date"),
                "extraction": "trafilatura",
            }
            log.info("Extracted readable content: title=%s lang=%s", metadata.get("title"), metadata.get("lang"))
        elif raw_fallback:
            content = raw_fallback
            # Naive HTML strip for fallback
            import re
            from html import unescape
            content = re.sub(r"(?is)<script.*?>.*?</script>", " ", content)
            content = re.sub(r"(?is)<style.*?>.*?</style>", " ", content)
            content = re.sub(r"(?is)<.*?>", " ", content)
            content = unescape(content)
            content = re.sub(r"\s+", " ", content).strip()
            metadata = {
                "url": url,
                "extraction": "raw-fallback",
            }
            log.info("Using raw fallback extraction")
        else:
            log.warning("No content extracted from URL: %s", url)
            return {"ok": False, "error": "no_content_extracted", "url": url}
        
        if not content.strip():
            log.warning("Empty content after extraction: %s", url)
            return {"ok": False, "error": "empty_content", "url": url}
        
        # Normalize whitespace
        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        
        # Apply PII redaction before processing
        if PII_REDACT_ENABLED:
            content = redact_text(content, PII_TYPES, PII_PLACEHOLDERS)
            log.info("PII redaction applied to URL content: types=%s", sorted(PII_TYPES))
        
        # Reuse text ingest logic
        result = ingest_text_job(text=content, source=source or url, tenant=tenant)
        
        # Add URL metadata to result
        result["url"] = metadata.get("url", url)
        result["title"] = metadata.get("title")
        result["lang"] = metadata.get("lang")
        result["published"] = metadata.get("published")
        result["extraction"] = metadata["extraction"]
        
        dt = (time.perf_counter() - t0) * 1000.0
        result["latency_ms_total"] = round(dt, 1)
        
        # Audit log
        try:
            from pods.customer_ops.audit import append_event
            append_event({
                "type": "ingest-url",
                "tenant_id": tenant,
                "url": metadata.get("url", url),
                "title": metadata.get("title"),
                "lang": metadata.get("lang"),
                "published": metadata.get("published"),
                "extraction": metadata.get("extraction"),
                "chunks": result.get("ingested_chunks", 0),
                "latency_ms": round(dt, 1),
                "metadata": metadata
            })
        except Exception as audit_err:
            log.warning("Audit logging failed: %s", audit_err)
        
        log.info("ingest_url_job done: url=%s chunks=%s extraction=%s", 
                 url, result.get("ingested_chunks"), result.get("extraction"))
        
        # Record success metrics
        JOBS_OK.labels("ingest-url").inc()
        return result
        
    except Exception as e:
        log.exception("ingest_url_job failed: url=%s error=%s", url, e)
        JOBS_FAIL.labels("ingest-url").inc()
        return {"ok": False, "error": str(e), "url": url}

def ingest_file_job(file_bytes: bytes, filename: str, source: str, tenant: str = "default") -> Dict[str, Any]:
    """Background job: Process uploaded file and ingest content."""
    t0 = time.perf_counter()
    log.info("Starting ingest_file_job: filename=%s tenant=%s source=%s", filename, tenant, source)
    
    try:
        text = ""
        name = filename.lower()
        
        # PDF extraction
        if name.endswith(".pdf"):
            try:
                from pypdf import PdfReader
                import io
                reader = PdfReader(io.BytesIO(file_bytes))
                text = "\n".join([page.extract_text() or "" for page in reader.pages])
            except Exception as e:
                log.warning("PDF extraction failed: %s", e)
                return {"ok": False, "error": f"pdf_extraction_failed: {e}", "filename": filename}
        
        # Text files
        elif name.endswith(".txt") or name.endswith(".md"):
            text = file_bytes.decode("utf-8", errors="ignore")
        
        # DOCX (optional)
        elif name.endswith(".docx"):
            try:
                import docx
                from io import BytesIO
                doc = docx.Document(BytesIO(file_bytes))
                text = "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                # Fallback to UTF-8
                text = file_bytes.decode("utf-8", errors="ignore")
        
        # Default: treat as text
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
        
        if not text.strip():
            log.warning("No text extracted from file: %s", filename)
            return {"ok": False, "error": "no_text_extracted", "filename": filename}
        
        # Reuse text ingest logic
        result = ingest_text_job(text=text, source=source or filename, tenant=tenant)
        result["filename"] = filename
        
        dt = (time.perf_counter() - t0) * 1000.0
        result["latency_ms_total"] = round(dt, 1)
        
        log.info("ingest_file_job done: filename=%s chunks=%s", filename, result.get("ingested_chunks"))
        JOBS_OK.labels("ingest-file").inc()
        return result
        
    except Exception as e:
        log.exception("ingest_file_job failed: filename=%s error=%s", filename, e)
        JOBS_FAIL.labels("ingest-file").inc()
        return {"ok": False, "error": str(e), "filename": filename}

def main():
    """Start RQ worker for follow-ups + ingestion tasks."""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    followup_queue = os.getenv("FOLLOWUP_QUEUE", "followups")
    
    log.info("Worker starting; connecting to %s", url)
    log.info("Database path: %s", DB_PATH)
    
    # RQ requires decode_responses=False for binary job data
    r = redis.from_url(url, decode_responses=False)
    
    try:
        # Listen on both followups and ingest queues
        queues = [Queue(followup_queue, connection=r), Queue("ingest", connection=r)]
        log.info("Listening on queues: %s", [q.name for q in queues])
        Worker(queues, connection=r, name=f"worker-{os.getpid()}").work(with_scheduler=True)
    except Exception as e:
        log.exception("Worker failed: %s", e)
        raise


if __name__ == "__main__":
    main()
