"""
Test PII redaction in conversation memory.
"""
import json
import re

import pytest

from api.memory import redact_pii


def test_email_redaction_basic():
    txt = "Contact me at jane.doe@example.com about the quote."
    red, meta = redact_pii(txt)
    assert "[EMAIL:" in red
    assert "example.com" not in red
    assert meta and len(meta) == 1


def test_phone_redaction_variants():
    for v in ["612-555-1212", "(612) 555-1212", "+1 612 555 1212"]:
        red, _ = redact_pii(f"Call {v} asap")
        assert "[PHONE:" in red


def test_ssn_and_card_redaction():
    red1, _ = redact_pii("ssn 123-45-6789")
    assert "[SSN:" in red1
    red2, _ = redact_pii("card 4242 4242 4242 4242 please")
    assert "[CARD:" in red2


def test_extra_patterns_csv():
    # redact 8-digit job ids as extra
    red, _ = redact_pii("job 12345678 reference", extra_csv=r"\b\d{8}\b")
    assert "[EXTRA_0:" in red


@pytest.mark.parametrize(
    "text",
    [
        "email a@b.co",
        "p: 763.555.0000",
    ],
)
def test_mapping_present(text):
    red, meta = redact_pii(text)
    # every token in text must exist in meta mapping
    tokens = re.findall(r"\[[A-Z]+_?[0-9]*:[0-9a-f]{10}\]", red)
    for t in tokens:
        assert t in meta


def test_no_pii_passthrough():
    """Text with no PII should pass through unchanged."""
    txt = "Just a normal message about booking."
    red, meta = redact_pii(txt)
    assert red == txt
    assert meta == {}


def test_multiple_pii_types():
    """Multiple PII types in one message."""
    txt = "Call 612-555-1212 or email test@example.com with card 4242424242424242"
    red, meta = redact_pii(txt)
    assert "[PHONE:" in red
    assert "[EMAIL:" in red
    assert "[CARD:" in red
    assert len(meta) == 3
    # Verify original values are not in redacted text
    assert "612-555-1212" not in red
    assert "test@example.com" not in red
    assert "4242424242424242" not in red


def test_overlapping_patterns():
    """Overlapping patterns should not double-redact."""
    # Some edge cases where patterns might overlap
    txt = "email: admin@123-45-6789.com"  # email contains SSN-like pattern
    red, meta = redact_pii(txt)
    # Should only redact as email, not both email and SSN
    assert red.count("[") == 1  # Only one redaction token


def test_hash_consistency():
    """Same PII value should produce same hash."""
    txt1 = "Call 612-555-1212"
    txt2 = "Phone: 612-555-1212"
    red1, meta1 = redact_pii(txt1)
    red2, meta2 = redact_pii(txt2)
    
    # Extract the hash from both redactions
    hash1 = re.search(r"\[PHONE:([0-9a-f]{10})\]", red1).group(1)
    hash2 = re.search(r"\[PHONE:([0-9a-f]{10})\]", red2).group(1)
    
    assert hash1 == hash2  # Same phone number should produce same hash
