"""
Test suite for tamper-evident audit log.
"""

import json
import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pods.customer_ops.audit import append_event, read_last_hash, verify_chain


def test_hash_chain():
    """Test that hash chain links events correctly."""
    print("\n🧪 Test 1: Hash chain integrity")

    # Use temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        test_file = f.name

    try:
        # Append first event
        hash1 = append_event({"type": "test", "action": "first_event"}, file=test_file)

        # Read last hash
        last = read_last_hash(test_file)
        assert last == hash1, f"Last hash mismatch: {last} != {hash1}"

        # Append second event
        hash2 = append_event({"type": "test", "action": "second_event"}, file=test_file)

        # Verify chain
        result = verify_chain(test_file)
        assert result["valid"], f"Chain should be valid: {result}"
        assert result["total_entries"] == 2

        # Read file and check prev_hash linkage
        with open(test_file) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        # First event should have null prev_hash
        assert lines[0]["prev_hash"] is None
        assert lines[0]["hash"] == hash1

        # Second event should link to first
        assert lines[1]["prev_hash"] == hash1
        assert lines[1]["hash"] == hash2

        print("   ✅ PASS - Hash chain verified (2 events)")
        print(f"   🔗 First:  {hash1[:16]}...")
        print(f"   🔗 Second: {hash2[:16]}... (links to first)")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_tamper_detection():
    """Test that tampering is detected."""
    print("\n🧪 Test 2: Tamper detection")

    # Use temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        test_file = f.name

    try:
        # Append two events
        append_event({"type": "test", "value": 100}, file=test_file)
        append_event({"type": "test", "value": 200}, file=test_file)

        # Verify it's valid first
        result = verify_chain(test_file)
        assert result["valid"]

        # Tamper with second line (change value)
        with open(test_file) as f:
            lines = f.readlines()

        # Modify second event
        event2 = json.loads(lines[1])
        event2["event"]["value"] = 999  # TAMPER!
        lines[1] = json.dumps(event2) + "\n"

        with open(test_file, "w") as f:
            f.writelines(lines)

        # Verify should now fail
        result = verify_chain(test_file)
        assert not result["valid"], "Should detect tampering"
        assert result["first_error_index"] == 1
        assert "hash mismatch" in result["error_message"].lower()

        print("   ✅ PASS - Tampering detected at entry 1")
        print(f"   🚨 Error: {result['error_message'][:80]}...")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_empty_log():
    """Test verification of empty/non-existent log."""
    print("\n🧪 Test 3: Empty log handling")

    # Non-existent file
    result = verify_chain("nonexistent.jsonl")
    assert result["valid"]
    assert result["total_entries"] == 0

    # Empty file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        test_file = f.name

    try:
        result = verify_chain(test_file)
        assert result["valid"]
        assert result["total_entries"] == 0

        print("   ✅ PASS - Empty logs handled correctly")

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


if __name__ == "__main__":
    print("=" * 70)
    print("🔒 Audit Log Test Suite")
    print("=" * 70)

    try:
        test_hash_chain()
        test_tamper_detection()
        test_empty_log()

        print("\n" + "=" * 70)
        print("🎉 ALL AUDIT LOG TESTS PASSED!")
        print("=" * 70)
        print("\nScore: 3/3 tests passed")

    except AssertionError as e:
        print(f"\n❌ FAIL  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR  {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
