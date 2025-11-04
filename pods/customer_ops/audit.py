"""
Tamper-evident audit log with hash chain.

Each event is appended to ops.jsonl with:
- Timestamp (ISO 8601)
- Event payload (type, job_id, actor, metadata)
- Previous hash (creates hash chain)
- Current hash (SHA-256 of line)

This creates a blockchain-like chain where tampering with any entry
breaks the hash chain, making it immediately detectable.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def ensure_audit_dir(path: str = "data/audit") -> None:
    """
    Ensure audit directory exists.

    Args:
        path: Directory path for audit logs
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def read_last_hash(file: str = "data/audit/ops.jsonl") -> str | None:
    """
    Read the hash of the last entry in the audit log.

    Args:
        file: Path to audit log file

    Returns:
        Hash string of last entry, or None if file empty/doesn't exist
    """
    if not os.path.exists(file):
        return None

    try:
        with open(file) as f:
            lines = f.readlines()
            if not lines:
                return None

            # Parse last line
            last_line = lines[-1].strip()
            if last_line:
                entry = json.loads(last_line)
                return entry.get("hash")
    except Exception:
        return None

    return None


def append_event(event: dict[str, Any], file: str = "data/audit/ops.jsonl") -> str:
    """
    Append an event to the audit log with hash chain.

    Args:
        event: Event data to log (type, job_id, actor, metadata, etc.)
        file: Path to audit log file

    Returns:
        Hash of the appended entry
    """
    # Ensure directory exists
    ensure_audit_dir(os.path.dirname(file))

    # Get last hash for chain
    prev_hash = read_last_hash(file)

    # Build payload
    payload = {"ts": datetime.now(UTC).isoformat(), "event": event, "prev_hash": prev_hash}

    # Serialize payload (deterministic - sorted keys, no spaces)
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    # Compute hash
    entry_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    # Add hash to payload
    payload["hash"] = entry_hash

    # Write to file (append mode)
    with open(file, "a") as f:
        f.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        f.flush()

    return entry_hash


def verify_chain(file: str = "data/audit/ops.jsonl") -> dict[str, Any]:
    """
    Verify integrity of the entire audit log hash chain.

    Args:
        file: Path to audit log file

    Returns:
        Dict with verification results:
        - valid: bool
        - total_entries: int
        - first_error_index: Optional[int]
        - error_message: Optional[str]
    """
    if not os.path.exists(file):
        return {"valid": True, "total_entries": 0, "message": "No audit log file exists yet"}

    with open(file) as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return {"valid": True, "total_entries": 0, "message": "Audit log is empty"}

    prev_hash_expected = None

    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)

            # Check prev_hash matches chain
            if entry.get("prev_hash") != prev_hash_expected:
                return {
                    "valid": False,
                    "total_entries": len(lines),
                    "first_error_index": i,
                    "error_message": f"Hash chain broken at entry {i}: expected prev_hash={prev_hash_expected}, got={entry.get('prev_hash')}",
                }

            # Verify entry hash
            stored_hash = entry.get("hash")
            if not stored_hash:
                return {
                    "valid": False,
                    "total_entries": len(lines),
                    "first_error_index": i,
                    "error_message": f"Entry {i} missing hash field",
                }

            # Recompute hash (without the hash field itself)
            payload_without_hash = {k: v for k, v in entry.items() if k != "hash"}
            payload_str = json.dumps(payload_without_hash, separators=(",", ":"), sort_keys=True)
            computed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            if computed_hash != stored_hash:
                return {
                    "valid": False,
                    "total_entries": len(lines),
                    "first_error_index": i,
                    "error_message": f"Entry {i} hash mismatch: computed={computed_hash[:16]}..., stored={stored_hash[:16]}...",
                }

            # Update expected prev_hash for next iteration
            prev_hash_expected = stored_hash

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "total_entries": len(lines),
                "first_error_index": i,
                "error_message": f"Entry {i} invalid JSON: {e}",
            }
        except Exception as e:
            return {
                "valid": False,
                "total_entries": len(lines),
                "first_error_index": i,
                "error_message": f"Entry {i} verification error: {e}",
            }

    return {
        "valid": True,
        "total_entries": len(lines),
        "message": f"All {len(lines)} entries verified successfully",
    }
