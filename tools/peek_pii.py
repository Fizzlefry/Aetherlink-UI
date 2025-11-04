"""
Peek PII - Verify PII redaction in stored chunks
Fetches raw chunk snippets via /admin/doc endpoint and checks for placeholders.
"""
import os
import sys
import json
import urllib.parse
import urllib.request


API_BASE = os.getenv("AETHER_API", "http://localhost:8000")
ADMIN_KEY = os.getenv("API_ADMIN_KEY", "admin-secret-123")


def get_json(url):
    """Fetch JSON from URL with admin key authentication"""
    req = urllib.request.Request(url, headers={"x-admin-key": ADMIN_KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def show_pii(source="pii-test", limit=5):
    """Fetch and display chunks with PII placeholder verification"""
    qs = urllib.parse.urlencode({"source": source, "limit": str(limit)})
    url = f"{API_BASE}/admin/doc?{qs}"
    
    try:
        data = get_json(url)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        if e.code == 401:
            print("   Check your API_ADMIN_KEY environment variable")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print(f"\n{'='*60}")
    print(f"📄 Document Source: {source}")
    print(f"{'='*60}")
    print(f"Chunks found: {data.get('count', 0)}\n")
    
    if data.get('count', 0) == 0:
        print("⚠️  No chunks found for this source")
        return
    
    for i, item in enumerate(data.get("items", []), 1):
        snippet = item.get("snippet", "") or ""
        metadata = item.get("metadata", {})
        
        print(f"{'─'*60}")
        print(f"Chunk #{i}")
        print(f"{'─'*60}")
        print(f"\n{snippet}\n")
        
        # Check for PII placeholders
        flags = {
            "[EMAIL]": "[EMAIL]" in snippet,
            "[PHONE]": "[PHONE]" in snippet,
            "[SSN]": "[SSN]" in snippet,
            "[CARD]": "[CARD]" in snippet,
        }
        
        found_placeholders = [k for k, v in flags.items() if v]
        
        if found_placeholders:
            print("✅ PII Placeholders found:", ", ".join(found_placeholders))
        else:
            print("ℹ️  No PII placeholders detected in this chunk")
        
        # Show metadata
        if metadata:
            pii_redaction = metadata.get("pii_redaction", {})
            if pii_redaction:
                enabled = pii_redaction.get("enabled", False)
                types = pii_redaction.get("types", [])
                if enabled:
                    print(f"🔒 PII Redaction: ENABLED (types: {', '.join(types)})")
        print()
    
    # Summary
    print(f"{'='*60}")
    total_with_placeholders = sum(
        1 for item in data.get("items", [])
        if any(ph in (item.get("snippet", "") or "") 
               for ph in ["[EMAIL]", "[PHONE]", "[SSN]", "[CARD]"])
    )
    print(f"Summary: {total_with_placeholders}/{data.get('count', 0)} chunks contain PII placeholders")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "pii-test"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    show_pii(source=source, limit=limit)
