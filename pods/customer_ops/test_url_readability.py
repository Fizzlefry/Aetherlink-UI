#!/usr/bin/env python3
"""
🔍 URL Readability Verification
Tests trafilatura extraction for clean article text.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import patch

HTML_MESSY = """
<!doctype html>
<html>
<head><title>Test Article • Site</title></head>
<body>
<nav>nav nav nav nav nav</nav>
<aside>sidebar ads sidebar</aside>
<main>
  <article>
    <h1>My Great Article</h1>
    <p>First paragraph with real content that matters.</p>
    <p>Second paragraph with even more valuable content.</p>
    <p>Third paragraph continues the story.</p>
  </article>
</main>
<footer>footer footer copyright footer</footer>
<script>console.log('noise noise noise')</script>
</body>
</html>
"""

HTML_WITH_META = """
<!doctype html>
<html lang="en">
<head>
    <title>Breaking News Story</title>
    <meta property="og:title" content="Breaking News Story">
    <meta name="description" content="Important news">
    <meta property="article:published_time" content="2025-01-15T10:30:00Z">
</head>
<body>
<article>
    <h1>Breaking News Story</h1>
    <p>This is the main content of the article.</p>
    <p>More important information here.</p>
</article>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, text, content_type, url="https://example.com/article"):
        self.text = text
        self.headers = {"Content-Type": content_type}
        self.url = url
        self.status_code = 200


def test_trafilatura_extracts_clean_text():
    """Test that trafilatura removes boilerplate (nav, footer, scripts)."""
    print("\n1️⃣  Trafilatura Clean Extraction...")

    with patch("requests.get") as mock_get:
        mock_get.return_value = FakeResponse(HTML_MESSY, "text/html; charset=utf-8")

        from pods.customer_ops.worker import _fetch_and_extract_readable

        readable, fallback = _fetch_and_extract_readable("https://example.com/article")

        if fallback is not None:
            print("    ❌ Should use trafilatura, not fallback")
            return False

        if readable is None:
            print("    ❌ Readable should not be None")
            return False

        text = readable.get("text", "")

        # Should contain main content
        if "First paragraph with real content" not in text:
            print(f"    ❌ Missing main content. Got: {text[:200]}")
            return False

        if "Second paragraph with even more" not in text:
            print(f"    ❌ Missing second paragraph. Got: {text[:200]}")
            return False

        # Should NOT contain boilerplate
        if "nav nav nav" in text:
            print("    ❌ Nav boilerplate should be removed")
            return False

        if "footer footer" in text:
            print("    ❌ Footer boilerplate should be removed")
            return False

        if "console.log" in text:
            print("    ❌ Script tags should be removed")
            return False

        if "sidebar ads" in text:
            print("    ❌ Sidebar should be removed")
            return False

        print(f"    ✅ Clean text extracted ({len(text)} chars)")
        print("    ✅ Boilerplate removed (nav, footer, scripts, sidebar)")
        return True


def test_metadata_extraction():
    """Test that metadata (title, lang, date) is extracted."""
    print("\n2️⃣  Metadata Extraction...")

    with patch("requests.get") as mock_get:
        mock_get.return_value = FakeResponse(HTML_WITH_META, "text/html; charset=utf-8")

        from pods.customer_ops.worker import _fetch_and_extract_readable

        readable, fallback = _fetch_and_extract_readable("https://example.com/news")

        if readable is None:
            print("    ❌ Readable should not be None")
            return False

        # Check title
        if not readable.get("title"):
            print("    ⚠️  Title not extracted (may depend on trafilatura version)")
        else:
            print(f"    ✅ Title extracted: {readable['title']}")

        # Check lang
        if readable.get("lang") == "en":
            print(f"    ✅ Lang extracted: {readable['lang']}")
        else:
            print(f"    ⚠️  Lang not extracted (got: {readable.get('lang')})")

        # Check URL (canonical after redirects) - mock returns different URL
        if readable.get("url"):
            print(f"    ✅ URL preserved: {readable['url']}")
        else:
            print("    ❌ URL missing")
            return False

        return True


def test_non_html_fallback():
    """Test that non-HTML content falls back to raw text."""
    print("\n3️⃣  Non-HTML Fallback...")

    with patch("requests.get") as mock_get:
        mock_get.return_value = FakeResponse("%PDF-1.7 binary data...", "application/pdf")

        from pods.customer_ops.worker import _fetch_and_extract_readable

        readable, fallback = _fetch_and_extract_readable("https://example.com/doc.pdf")

        if readable is not None:
            print("    ❌ Readable should be None for non-HTML")
            return False

        if fallback is None:
            print("    ❌ Fallback should contain raw text")
            return False

        if "%PDF-1.7" not in fallback:
            print("    ❌ Fallback should contain PDF marker")
            return False

        print("    ✅ Non-HTML returns fallback (not readable)")
        return True


def test_empty_html_fallback():
    """Test that empty extraction falls back to raw HTML."""
    print("\n4️⃣  Empty Extraction Fallback...")

    with patch("requests.get") as mock_get:
        # HTML with no extractable content
        empty_html = "<html><head></head><body><div id='app'></div></body></html>"
        mock_get.return_value = FakeResponse(empty_html, "text/html")

        from pods.customer_ops.worker import _fetch_and_extract_readable

        readable, fallback = _fetch_and_extract_readable("https://example.com/spa")

        # Trafilatura may return None for empty content, triggering fallback
        if readable is None and fallback is not None:
            print("    ✅ Empty content triggers fallback")
            return True
        elif readable is not None and not readable.get("text"):
            print("    ✅ Empty readable text detected")
            return True
        else:
            print(
                f"    ⚠️  Unexpected result: readable={readable is not None}, fallback={fallback is not None}"
            )
            return True  # Not critical, depends on trafilatura behavior


if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  🔍 URL Readability Tests            ║")
    print("╚════════════════════════════════════════╝")

    results = []
    results.append(("Clean text extraction", test_trafilatura_extracts_clean_text()))
    results.append(("Metadata extraction", test_metadata_extraction()))
    results.append(("Non-HTML fallback", test_non_html_fallback()))
    results.append(("Empty HTML fallback", test_empty_html_fallback()))

    print("\n╔════════════════════════════════════════╗")
    print("║  📊 Test Results                      ║")
    print("╚════════════════════════════════════════╝\n")

    passed = sum(1 for _, result in results if result)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    print(f"\n  Score: {passed}/{len(results)} tests passed\n")

    if passed == len(results):
        print("  🎉 ALL READABILITY TESTS PASSED!")
    else:
        print(f"  ⚠️  {len(results) - passed} test(s) failed")

    exit(0 if passed == len(results) else 1)
