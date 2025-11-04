"""
Test suite for PII redaction functionality.
Tests pattern matching, URL protection, and integration with ingestion pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pods.customer_ops.pii import redact_text, parse_pii_config


def test_email_redaction():
    """Test email address redaction"""
    text = "Contact me at john.doe+tag@example.com or ADMIN@SITE.ORG"
    types = {'email'}
    placeholders = {'email': '[EMAIL]'}
    
    result = redact_text(text, types, placeholders)
    
    assert '[EMAIL]' in result
    assert 'john.doe+tag@example.com' not in result
    assert 'ADMIN@SITE.ORG' not in result.upper()
    print("✓ Email redaction test passed")


def test_phone_redaction():
    """Test phone number redaction"""
    text = "Call me at (612) 555-1212 or 763-555-0101 or +1 651-555-9999"
    types = {'phone'}
    placeholders = {'phone': '[PHONE]'}
    
    result = redact_text(text, types, placeholders)
    
    assert '[PHONE]' in result
    assert '612' not in result
    assert '555-1212' not in result
    print("✓ Phone redaction test passed")


def test_ssn_redaction():
    """Test SSN redaction"""
    text = "My SSN is 123-45-6789 and my friend's is 987-65-4321"
    types = {'ssn'}
    placeholders = {'ssn': '[SSN]'}
    
    result = redact_text(text, types, placeholders)
    
    assert '[SSN]' in result
    assert '123-45-6789' not in result
    assert '987-65-4321' not in result
    print("✓ SSN redaction test passed")


def test_credit_card_redaction():
    """Test credit card number redaction"""
    text = "Card: 4242 4242 4242 4242 and 5555-5555-5555-4444"
    types = {'cc'}
    placeholders = {'cc': '[CARD]'}
    
    result = redact_text(text, types, placeholders)
    
    assert '[CARD]' in result
    assert '4242 4242 4242 4242' not in result
    assert '5555-5555-5555-4444' not in result
    print("✓ Credit card redaction test passed")


def test_multi_type_redaction():
    """Test multiple PII types at once"""
    text = "Email: a.b+tag@site.io, Phone: (612) 555-1212, SSN: 123-45-6789, Card: 4242 4242 4242 4242"
    types = {'email', 'phone', 'ssn', 'cc'}
    placeholders = {
        'email': '[EMAIL]',
        'phone': '[PHONE]',
        'ssn': '[SSN]',
        'cc': '[CARD]'
    }
    
    result = redact_text(text, types, placeholders)
    
    assert '[EMAIL]' in result
    assert '[PHONE]' in result
    assert '[SSN]' in result
    assert '[CARD]' in result
    assert 'a.b+tag@site.io' not in result
    assert '612' not in result
    assert '123-45-6789' not in result
    assert '4242 4242 4242 4242' not in result
    print("✓ Multi-type redaction test passed")


def test_url_protection():
    """Test that URLs are not redacted"""
    text = "Visit https://contact@example.com:8080/path?email=test@test.com for info"
    types = {'email'}
    placeholders = {'email': '[EMAIL]'}
    
    result = redact_text(text, types, placeholders)
    
    # URL should be preserved
    assert 'https://contact@example.com:8080/path?email=test@test.com' in result
    print("✓ URL protection test passed")


def test_parse_pii_config():
    """Test configuration parsing"""
    types_str = "email,phone,ssn,cc"
    placeholders_str = "email:[EMAIL],phone:[PHONE],ssn:[SSN],cc:[CARD]"
    
    types, placeholders = parse_pii_config(types_str, placeholders_str)
    
    assert types == {'email', 'phone', 'ssn', 'cc'}
    assert placeholders['email'] == '[EMAIL]'
    assert placeholders['phone'] == '[PHONE]'
    assert placeholders['ssn'] == '[SSN]'
    assert placeholders['cc'] == '[CARD]'
    print("✓ Config parsing test passed")


def test_empty_input():
    """Test handling of empty input"""
    result = redact_text("", {'email'}, {'email': '[EMAIL]'})
    assert result == ""
    
    result = redact_text("Some text", set(), {})
    assert result == "Some text"
    print("✓ Empty input test passed")


def test_no_pii_present():
    """Test text without PII"""
    text = "This is a normal sentence without any sensitive data."
    types = {'email', 'phone', 'ssn', 'cc'}
    placeholders = {
        'email': '[EMAIL]',
        'phone': '[PHONE]',
        'ssn': '[SSN]',
        'cc': '[CARD]'
    }
    
    result = redact_text(text, types, placeholders)
    
    # Text should remain unchanged
    assert result == text
    print("✓ No PII present test passed")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running PII Redaction Tests")
    print("="*60 + "\n")
    
    try:
        test_email_redaction()
        test_phone_redaction()
        test_ssn_redaction()
        test_credit_card_redaction()
        test_multi_type_redaction()
        test_url_protection()
        test_parse_pii_config()
        test_empty_input()
        test_no_pii_present()
        
        print("\n" + "="*60)
        print("✅ All PII redaction tests passed!")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
