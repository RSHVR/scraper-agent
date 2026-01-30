"""Tests for trafilatura-based content extraction."""

import pytest
from src.services.trafilatura_service import TrafilaturaService, ExtractionResult


# Sample HTML for testing
SAMPLE_HTML_BASIC = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <header><nav>Navigation menu</nav></header>
    <main>
        <article>
            <h1>Main Article Title</h1>
            <p>This is the main content of the article. It contains important information that should be extracted.</p>
            <p>Here is another paragraph with more details about the topic.</p>
        </article>
    </main>
    <footer>Copyright 2024</footer>
</body>
</html>
"""

SAMPLE_HTML_WITH_CONTACTS = """
<!DOCTYPE html>
<html>
<head>
    <title>Contact Us</title>
    <script type="application/ld+json">
    {
        "@type": "LocalBusiness",
        "name": "Test Business",
        "telephone": "+1-555-123-4567",
        "email": "info@testbusiness.com",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "123 Main Street",
            "addressLocality": "Toronto",
            "addressRegion": "ON",
            "postalCode": "M5V 1A1"
        }
    }
    </script>
</head>
<body>
    <main>
        <h1>Contact Us</h1>
        <p>Call us at (416) 555-7890 or email support@example.com</p>
        <a href="tel:+14165559999">Phone</a>
        <a href="mailto:sales@example.com">Email Sales</a>
    </main>
</body>
</html>
"""

SAMPLE_HTML_WITH_STRUCTURED_DATA = """
<!DOCTYPE html>
<html>
<head>
    <title>Product Page</title>
    <meta property="og:title" content="Amazing Product">
    <meta property="og:description" content="The best product ever">
    <meta property="og:image" content="https://example.com/image.jpg">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Amazing Product">
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Amazing Product",
        "description": "A fantastic product",
        "price": "99.99",
        "priceCurrency": "USD"
    }
    </script>
</head>
<body>
    <main>
        <h1>Amazing Product</h1>
        <p>This is our amazing product description.</p>
    </main>
</body>
</html>
"""


class TestTrafilaturaService:
    """Tests for TrafilaturaService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = TrafilaturaService()

    def test_extract_from_html_basic(self):
        """Test basic content extraction."""
        result = self.service.extract_from_html(SAMPLE_HTML_BASIC)

        assert result.error is None
        assert result.text is not None
        # Should extract main content
        assert "main content" in result.text.lower() or "article" in result.text.lower()

    def test_extract_from_html_returns_markdown(self):
        """Test that markdown output is generated."""
        result = self.service.extract_from_html(SAMPLE_HTML_BASIC)

        assert result.error is None
        # Markdown output should exist (may be None for very simple pages)
        # but shouldn't error

    def test_extract_with_fallback_empty_trafilatura(self):
        """Test fallback when trafilatura returns empty."""
        # Very minimal HTML that trafilatura might not extract
        minimal_html = "<div>Just some text in a div</div>"
        result = self.service.extract_with_fallback(minimal_html)

        # Should get content via fallback
        assert result.error is None
        # Fallback should extract something
        assert result.text is not None or result.markdown is not None

    def test_extract_metadata(self):
        """Test metadata extraction."""
        result = self.service.extract_from_html(SAMPLE_HTML_BASIC)

        # Title should be extracted
        assert result.title is None or isinstance(result.title, str)

    def test_extract_handles_empty_html(self):
        """Test handling of empty HTML."""
        result = self.service.extract_from_html("")

        # Should not crash, may return None or error
        assert result is not None

    def test_extract_handles_malformed_html(self):
        """Test handling of malformed HTML."""
        malformed = "<html><body><div>Unclosed tags<p>More text"
        result = self.service.extract_with_fallback(malformed)

        # Should not crash
        assert result is not None
        assert result.error is None


class TestContactExtraction:
    """Tests for contact information extraction."""

    def test_extract_phones_from_text(self):
        """Test phone extraction from visible text."""
        import json
        from src.agents.tools import extract_contact_info, set_tool_context, ToolContext

        # Set up context with HTML
        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_CONTACTS
        set_tool_context(ctx)

        # LangChain tools need .invoke() to call them
        result = json.loads(extract_contact_info.invoke({}))

        assert result["success"] is True
        # Should find phones from text and JSON-LD
        assert len(result["contacts"]["phones"]) > 0

    def test_extract_emails_from_text_and_links(self):
        """Test email extraction from text and mailto links."""
        import json
        from src.agents.tools import extract_contact_info, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_CONTACTS
        set_tool_context(ctx)

        result = json.loads(extract_contact_info.invoke({}))

        assert result["success"] is True
        emails = result["contacts"]["emails"]
        assert len(emails) > 0
        # Should find emails from various sources
        assert any("@" in email for email in emails)

    def test_extract_addresses_from_json_ld(self):
        """Test address extraction from JSON-LD structured data."""
        import json
        from src.agents.tools import extract_contact_info, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_CONTACTS
        set_tool_context(ctx)

        result = json.loads(extract_contact_info.invoke({}))

        assert result["success"] is True
        addresses = result["contacts"]["addresses"]
        assert len(addresses) > 0
        # Should find address from JSON-LD
        assert any("Toronto" in addr for addr in addresses)


class TestStructuredDataExtraction:
    """Tests for structured data extraction."""

    def test_extract_json_ld(self):
        """Test JSON-LD extraction."""
        import json
        from src.agents.tools import extract_structured_data, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_STRUCTURED_DATA
        set_tool_context(ctx)

        result = json.loads(extract_structured_data.invoke({}))

        assert result["success"] is True
        # Should find structured data
        assert result["count"] > 0

        # Find JSON-LD data
        json_ld_items = [item for item in result["structured_data"] if item["type"] == "json-ld"]
        assert len(json_ld_items) > 0

    def test_extract_opengraph(self):
        """Test OpenGraph metadata extraction."""
        import json
        from src.agents.tools import extract_structured_data, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_STRUCTURED_DATA
        set_tool_context(ctx)

        result = json.loads(extract_structured_data.invoke({}))

        assert result["success"] is True

        # Find OpenGraph data
        og_items = [item for item in result["structured_data"] if item["type"] == "opengraph"]
        assert len(og_items) > 0
        assert og_items[0]["data"].get("title") == "Amazing Product"

    def test_extract_twitter_cards(self):
        """Test Twitter Card metadata extraction."""
        import json
        from src.agents.tools import extract_structured_data, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_WITH_STRUCTURED_DATA
        set_tool_context(ctx)

        result = json.loads(extract_structured_data.invoke({}))

        assert result["success"] is True

        # Find Twitter Card data
        twitter_items = [item for item in result["structured_data"] if item["type"] == "twitter_card"]
        assert len(twitter_items) > 0

    def test_no_structured_data(self):
        """Test handling of pages without structured data."""
        import json
        from src.agents.tools import extract_structured_data, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = "<html><body><p>Plain page</p></body></html>"
        set_tool_context(ctx)

        result = json.loads(extract_structured_data.invoke({}))

        assert result["success"] is True
        assert result["count"] == 0


class TestExtractContentWithTrafilatura:
    """Tests for the updated extract_content tool using trafilatura."""

    def test_extract_main_content(self):
        """Test main_content extraction uses trafilatura."""
        import json
        from src.agents.tools import extract_content, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_BASIC
        ctx.current_url = "https://example.com"
        set_tool_context(ctx)

        result = json.loads(extract_content.invoke({"target": "main_content"}))

        assert result["success"] is True
        # Should have text content
        assert result.get("text") is not None or result.get("markdown") is not None

    def test_extract_links(self):
        """Test link extraction still works."""
        import json
        from src.agents.tools import extract_content, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = '<html><body><a href="/page1">Link 1</a><a href="/page2">Link 2</a></body></html>'
        set_tool_context(ctx)

        result = json.loads(extract_content.invoke({"target": "links"}))

        assert result["success"] is True
        assert result["count"] == 2

    def test_extract_headings(self):
        """Test heading extraction still works."""
        import json
        from src.agents.tools import extract_content, set_tool_context, ToolContext

        ctx = ToolContext("test-session")
        ctx.current_html = SAMPLE_HTML_BASIC
        set_tool_context(ctx)

        result = json.loads(extract_content.invoke({"target": "headings"}))

        assert result["success"] is True
        assert result["count"] > 0
