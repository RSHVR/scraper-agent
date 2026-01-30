"""Tests for agents."""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.tools import tool

from src.agents.schema_generator import SchemaGenerator
from src.agents.content_extractor import ContentExtractor
from src.agents.xml_tool_format import (
    tools_to_xml,
    parse_tool_call,
    format_tool_response,
    extract_text_before_tool_call
)
from src.agents.xml_tool_models import ToolCall
from src.models import ScrapeRequest, ScrapeMode


# ============================================================================
# XML Tool Format Tests
# ============================================================================

# Sample tools for testing
@tool
def sample_tool(url: str, timeout: int = 30) -> str:
    """Fetch a URL with optional timeout."""
    return f"Fetched {url}"


@tool
def another_tool(query: str) -> str:
    """Search for something."""
    return f"Results for {query}"


class TestToolsToXml:
    """Tests for converting tools to XML format."""

    def test_single_tool(self):
        """Should convert a single tool to XML format."""
        xml = tools_to_xml([sample_tool])

        assert "<tools>" in xml
        assert "</tools>" in xml
        assert '"name": "sample_tool"' in xml
        assert '"description": "Fetch a URL with optional timeout."' in xml
        assert "parameters" in xml

    def test_multiple_tools(self):
        """Should convert multiple tools to XML format."""
        xml = tools_to_xml([sample_tool, another_tool])

        assert '"name": "sample_tool"' in xml
        assert '"name": "another_tool"' in xml

    def test_empty_tools(self):
        """Should handle empty tool list."""
        xml = tools_to_xml([])

        assert "<tools>" in xml
        assert "[]" in xml


class TestParseToolCall:
    """Tests for parsing tool calls from model responses."""

    def test_parse_valid_tool_call(self):
        """Should parse a valid tool call."""
        response = '''I need to fetch the page.
<tool_call>
{"name": "fetch_page", "arguments": {"url": "https://example.com"}}
</tool_call>'''

        result = parse_tool_call(response)

        assert result is not None
        assert result.name == "fetch_page"
        assert result.arguments == {"url": "https://example.com"}

    def test_parse_tool_call_with_id(self):
        """Should parse tool call with ID."""
        response = '''<tool_call>
{"name": "analyze_url", "arguments": {"url": "https://test.com"}, "id": "call_123"}
</tool_call>'''

        result = parse_tool_call(response)

        assert result is not None
        assert result.name == "analyze_url"
        assert result.id == "call_123"

    def test_parse_tool_call_multiline_arguments(self):
        """Should parse tool calls with multiline JSON arguments."""
        response = '''<tool_call>
{
  "name": "save_result",
  "arguments": {
    "content": "Some extracted content",
    "url": "https://example.com",
    "title": "My Results"
  }
}
</tool_call>'''

        result = parse_tool_call(response)

        assert result is not None
        assert result.name == "save_result"
        assert result.arguments["content"] == "Some extracted content"
        assert result.arguments["url"] == "https://example.com"

    def test_parse_no_tool_call(self):
        """Should return None when no tool call present."""
        response = "I will help you scrape the website. Let me analyze it first."

        result = parse_tool_call(response)

        assert result is None

    def test_parse_invalid_json(self):
        """Should return None for invalid JSON in tool call."""
        response = '''<tool_call>
{invalid json here}
</tool_call>'''

        result = parse_tool_call(response)

        assert result is None

    def test_parse_tool_call_complex_arguments(self):
        """Should handle complex nested arguments."""
        response = '''<tool_call>
{"name": "extract_content", "arguments": {"target": "main_content", "options": {"include_links": true}}}
</tool_call>'''

        result = parse_tool_call(response)

        assert result is not None
        assert result.name == "extract_content"
        assert result.arguments["options"]["include_links"] is True


class TestFormatToolResponse:
    """Tests for formatting tool responses."""

    def test_format_simple_response(self):
        """Should format a simple result."""
        result = {"success": True, "data": "test"}

        formatted = format_tool_response(result)

        assert "<tool_response>" in formatted
        assert "</tool_response>" in formatted
        assert '"result"' in formatted

    def test_format_response_with_id(self):
        """Should include ID when provided."""
        result = {"success": True}

        formatted = format_tool_response(result, call_id="call_456")

        assert '"id": "call_456"' in formatted

    def test_format_string_result(self):
        """Should handle string results."""
        formatted = format_tool_response("Simple string result")

        assert '"result": "Simple string result"' in formatted


class TestExtractTextBeforeToolCall:
    """Tests for extracting reasoning text before tool calls."""

    def test_extract_reasoning(self):
        """Should extract text before tool call."""
        response = '''I need to analyze this URL first to understand what type of site it is.
<tool_call>
{"name": "analyze_url", "arguments": {"url": "https://example.com"}}
</tool_call>'''

        text = extract_text_before_tool_call(response)

        assert text is not None
        assert "analyze this URL" in text
        assert "<tool_call>" not in text

    def test_no_text_before_tool_call(self):
        """Should return None if no text before tool call."""
        response = '''<tool_call>
{"name": "fetch_page", "arguments": {"url": "https://example.com"}}
</tool_call>'''

        text = extract_text_before_tool_call(response)

        assert text is None

    def test_no_tool_call(self):
        """Should return None if no tool call present."""
        response = "Just some text without any tool call."

        text = extract_text_before_tool_call(response)

        assert text is None


# ============================================================================
# Existing Tests
# ============================================================================


class TestSchemaGenerator:
    """Tests for SchemaGenerator."""

    def test_extract_schema_valid_json(self):
        """Test extracting valid JSON schema from response."""
        generator = SchemaGenerator()

        response_text = """
        Here is the schema:
        {
            "fields": {
                "title": {
                    "type": "string",
                    "required": true,
                    "description": "Page title"
                }
            }
        }
        """

        schema = generator._extract_schema(response_text)
        assert schema is not None
        assert "fields" in schema
        assert "title" in schema["fields"]

    def test_extract_schema_invalid_json(self):
        """Test extracting invalid JSON returns None."""
        generator = SchemaGenerator()

        response_text = "This is not valid JSON"
        schema = generator._extract_schema(response_text)
        assert schema is None

    def test_build_html_prompt(self):
        """Test building the schema generation prompt from HTML."""
        generator = SchemaGenerator()

        purpose = "Extract contact info"
        html = "<html><body><p>Contact: test@example.com</p></body></html>"

        prompt = generator._build_html_prompt(purpose, html)
        assert "contact info" in prompt.lower()
        assert html in prompt
        assert "json" in prompt.lower()


class TestContentExtractor:
    """Tests for ContentExtractor."""

    def test_extract_data_valid_json(self):
        """Test extracting valid JSON data from response."""
        extractor = ContentExtractor()

        response_text = """
        {
            "title": "Test Page",
            "email": "test@example.com"
        }
        """

        data = extractor._extract_data(response_text)
        assert data is not None
        assert "title" in data
        assert data["title"] == "Test Page"

    def test_extract_data_invalid_json(self):
        """Test extracting invalid JSON returns None."""
        extractor = ContentExtractor()

        response_text = "Not valid JSON"
        data = extractor._extract_data(response_text)
        assert data is None

    def test_build_html_extraction_prompt(self):
        """Test building the extraction prompt from HTML."""
        extractor = ContentExtractor()

        html = "<html><body><h1>Test</h1></body></html>"
        schema = {
            "fields": {"title": {"type": "string", "required": True}}
        }

        prompt = extractor._build_html_extraction_prompt(html, schema)
        assert html in prompt
        assert "title" in prompt.lower()
        assert "json" in prompt.lower()


class TestOrchestratorIntegration:
    """Integration tests for OrchestratorAgent."""

    @pytest.mark.anyio
    async def test_orchestrator_workflow_mocked(self):
        """Test orchestrator workflow with mocked dependencies."""
        from src.agents.orchestrator import OrchestratorAgent
        from src.services import SessionManager, StorageService
        from src.services.sitemap_discovery import SitemapDiscovery
        from pathlib import Path
        import tempfile

        # Create temp storage
        temp_dir = Path(tempfile.mkdtemp())
        storage = StorageService(base_path=temp_dir)
        session_mgr = SessionManager(storage=storage)

        # Mock sitemap discovery
        mock_sitemap = Mock(spec=SitemapDiscovery)
        mock_sitemap.discover_from_robots = AsyncMock(return_value=[])

        orchestrator = OrchestratorAgent(
            session_mgr=session_mgr,
            sitemap_disco=mock_sitemap,
        )

        # Mock HTTP client
        with patch("src.agents.orchestrator.HTTPClient") as mock_http:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.fetch_url = AsyncMock(
                return_value=("<html><body>Test</body></html>", None)
            )
            mock_http.return_value = mock_client

            # Create request
            request = ScrapeRequest(
                url="https://example.com",
                purpose="Test extraction",
                mode=ScrapeMode.SINGLE_PAGE,
            )

            # Execute
            session_id, success = await orchestrator.execute_scrape(request)

            # Verify
            assert success
            assert session_id is not None

            # Check session was created
            session = await session_mgr.get_session(session_id)
            assert session is not None
            assert session.metadata.status.value == "completed"

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
