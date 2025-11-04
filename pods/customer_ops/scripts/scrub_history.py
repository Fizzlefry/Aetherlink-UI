"""
Backfill PII redaction for legacy conversation history in Redis.
Scans all mem:* keys and redacts PII in-place.

Usage:
    cd pods/customer_ops
    PYTHONPATH='../..' REDIS_URL=redis://localhost:6379/0 python scripts/scrub_history.py
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pods.customer_ops.api.memory import redact_pii
from pods.customer_ops.api.config import get_settings


def _get_redis():
    """Get Redis client."""
    try:
        import redis
        
        # Try config first, then env
        s = get_settings()
        url = os.environ.get("REDIS_URL") or str(getattr(s, "REDIS_URL", None) or "")
        
        if not url:
            print("❌ No REDIS_URL found. Set via environment or config.")
            sys.exit(1)
        
        r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
        r.ping()  # Test connection
        return r
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        sys.exit(1)


def main(prefix: str = "mem:*", dry_run: bool = False):
    """
    Scan and redact PII in conversation history.
    
    Args:
        prefix: Redis key pattern to scan (default: mem:*)
        dry_run: If True, show what would be changed without writing
    """
    r = _get_redis()
    
    print(f"🔍 Scanning Redis keys matching: {prefix}")
    keys = list(r.scan_iter(prefix))
    print(f"   Found {len(keys)} conversation history keys")
    
    if not keys:
        print("✅ No keys to process")
        return
    
    changed_keys = 0
    total_redactions = 0
    
    for idx, key in enumerate(keys, 1):
        print(f"   [{idx}/{len(keys)}] Processing {key}...", end=" ")
        
        try:
            items = r.lrange(key, 0, -1)
            new_items = []
            dirty = False
            key_redactions = 0
            
            for raw in items:
                try:
                    obj = json.loads(raw)
                    txt = obj.get("text", "")
                    
                    # Skip if already redacted (has "pii" field)
                    if "pii" in obj:
                        new_items.append(raw)
                        continue
                    
                    # Redact PII
                    red, pii_meta = redact_pii(txt)
                    
                    if red != txt:
                        obj["text"] = red
                        obj["pii"] = pii_meta
                        dirty = True
                        key_redactions += len(pii_meta)
                    
                    new_items.append(json.dumps(obj, ensure_ascii=False))
                    
                except json.JSONDecodeError:
                    # Keep malformed items as-is
                    new_items.append(raw)
            
            if dirty:
                if not dry_run:
                    # Atomic replacement
                    pipe = r.pipeline()
                    pipe.delete(key)
                    for item in reversed(new_items):
                        pipe.lpush(key, item)
                    pipe.execute()
                
                changed_keys += 1
                total_redactions += key_redactions
                print(f"✅ {key_redactions} redactions {'(would be) ' if dry_run else ''}applied")
            else:
                print("⏭️  Already clean")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n{'🔍 DRY RUN SUMMARY' if dry_run else '✅ SCRUB COMPLETE'}")
    print(f"   Keys scanned: {len(keys)}")
    print(f"   Keys updated: {changed_keys}")
    print(f"   Total PII redactions: {total_redactions}")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN MODE - No changes written")
        print(f"   Run without --dry-run to apply changes")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill PII redaction in Redis conversation history")
    parser.add_argument("--prefix", default="mem:*", help="Redis key pattern (default: mem:*)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()
    
    main(prefix=args.prefix, dry_run=args.dry_run)
