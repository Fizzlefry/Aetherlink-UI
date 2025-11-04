"""
PII Redaction Module
Removes sensitive personal information during ingestion for compliance and privacy.
Supports: emails, phone numbers, SSNs, credit cards (basic pattern matching).
"""
import re
from typing import Dict, Set


def redact_text(text: str, types: Set[str], placeholders: Dict[str, str]) -> str:
    """
    Redact PII from text based on specified types.
    
    Args:
        text: Input text to redact
        types: Set of PII types to redact (email, phone, ssn, cc)
        placeholders: Mapping of type -> replacement string (e.g., {'email': '[EMAIL]'})
    
    Returns:
        Redacted text with PII replaced by placeholders
    """
    if not text or not types:
        return text
    
    # Extract URLs to protect them from redaction
    url_pattern = re.compile(r'https?://\S+', re.IGNORECASE)
    urls = url_pattern.findall(text)
    url_placeholders = {}
    
    # Replace URLs with temporary placeholders
    for i, url in enumerate(urls):
        placeholder = f"__URL_{i}__"
        url_placeholders[placeholder] = url
        text = text.replace(url, placeholder)
    
    # Define PII patterns (case-insensitive)
    patterns = {
        'email': (
            r'\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b',
            placeholders.get('email', '[EMAIL]')
        ),
        'phone': (
            r'(?:(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?|\d{3})[\s.-]?\d{3}[\s.-]?\d{4})',
            placeholders.get('phone', '[PHONE]')
        ),
        'ssn': (
            r'\b\d{3}-\d{2}-\d{4}\b',
            placeholders.get('ssn', '[SSN]')
        ),
        'cc': (
            # Basic credit card pattern (13-19 digits with optional spaces/dashes)
            # Note: This is a simple pattern, not validating Luhn algorithm
            r'\b(?:\d[ -]*?){13,19}\b',
            placeholders.get('cc', '[CARD]')
        )
    }
    
    # Apply redactions for requested types
    for pii_type in types:
        if pii_type in patterns:
            pattern, replacement = patterns[pii_type]
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Restore URLs
    for placeholder, original_url in url_placeholders.items():
        text = text.replace(placeholder, original_url)
    
    return text


def parse_pii_config(
    redact_types_str: str,
    placeholders_str: str
) -> tuple[Set[str], Dict[str, str]]:
    """
    Parse PII configuration from environment variables.
    
    Args:
        redact_types_str: Comma-separated list of types (e.g., "email,phone,ssn")
        placeholders_str: Comma-separated key:value pairs (e.g., "email:[EMAIL],phone:[PHONE]")
    
    Returns:
        Tuple of (types_set, placeholders_dict)
    """
    # Parse types
    types = {t.strip().lower() for t in redact_types_str.split(',') if t.strip()}
    
    # Parse placeholders
    placeholders = {}
    for pair in placeholders_str.split(','):
        if ':' in pair:
            key, value = pair.split(':', 1)
            placeholders[key.strip().lower()] = value.strip()
    
    return types, placeholders
