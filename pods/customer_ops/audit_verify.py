#!/usr/bin/env python3
"""
Audit log verifier: checks integrity of hash chain in ops.jsonl.

Usage:
    python audit_verify.py [path/to/ops.jsonl]

Returns exit code 0 if valid, 1 if tampered/invalid.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pods.customer_ops.audit import verify_chain


def main():
    # Get file path from args or use default
    if len(sys.argv) > 1:
        audit_file = sys.argv[1]
    else:
        audit_file = "data/audit/ops.jsonl"

    print("=" * 70)
    print("🔒 Audit Log Integrity Verifier")
    print("=" * 70)
    print(f"\nFile: {audit_file}\n")

    # Verify chain
    result = verify_chain(audit_file)

    # Print results
    print(f"Total Entries: {result.get('total_entries', 0)}")

    if result["valid"]:
        print("✅ Status: VALID")
        if result.get("message"):
            print(f"   {result['message']}")
    else:
        print("❌ Status: INVALID (TAMPERED)")
        print(f"   First error at entry: {result.get('first_error_index')}")
        print(f"   Error: {result.get('error_message')}")

    print("\n" + "=" * 70)

    # Exit with appropriate code
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
