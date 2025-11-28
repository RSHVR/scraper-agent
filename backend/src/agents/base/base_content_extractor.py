"""Base content extractor class for extracting data from HTML."""
import json
from typing import Dict, Any, Optional
from anthropic import Anthropic

from ...config import settings


class BaseContentExtractor:
    """Base class for extracting structured data from HTML using a schema."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """Initialize the content extractor.

        Args:
            api_key: Anthropic API key. Defaults to settings.anthropic_api_key
            model: Claude model to use
        """
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model

    async def extract_content_from_url(
        self, url: str, schema: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """Extract structured data from a URL based on schema.

        Args:
            url: URL to fetch and extract from
            schema: Schema defining what data to extract

        Returns:
            Tuple of (extracted_data, error_message)
            If successful, returns (data, None)
            If failed, returns ({}, error_message)
        """
        # Format schema for the prompt
        schema_str = json.dumps(schema, indent=2)

        prompt = self._build_url_extraction_prompt(url, schema_str)

        try:
            # Call Claude API with web fetch tool
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 3
                }],
                extra_headers={"anthropic-beta": "web-fetch-2025-09-10"}
            )

            # Extract the response text from all text content blocks
            response_text = ""
            for block in message.content:
                if hasattr(block, 'text') and block.text:
                    response_text += block.text

            # Parse the extracted data from the response
            extracted_data = self._extract_data(response_text)

            if extracted_data is None:
                return (
                    {},
                    "Failed to extract valid JSON data from Claude's response",
                )

            return extracted_data, None

        except Exception as e:
            return {}, f"Error extracting content: {str(e)}"

    async def extract_content(
        self, html: str, schema: Dict[str, Any], max_length: int = 10000
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """Extract structured data from HTML based on schema.

        Args:
            html: HTML content to extract from
            schema: Schema defining what data to extract
            max_length: Maximum length of HTML to send to Claude

        Returns:
            Tuple of (extracted_data, error_message)
            If successful, returns (data, None)
            If failed, returns ({}, error_message)
        """
        # Truncate HTML if too long
        if len(html) > max_length:
            html = html[:max_length] + "\n... (truncated)"

        # Build the prompt
        prompt = self._build_html_extraction_prompt(html, schema)

        try:
            # Call Claude API with web fetch tool
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 3
                }],
                extra_headers={"anthropic-beta": "web-fetch-2025-09-10"}
            )

            # Extract the response text
            response_text = message.content[0].text

            # Parse the extracted data from the response
            extracted_data = self._extract_data(response_text)

            if extracted_data is None:
                return (
                    {},
                    "Failed to extract valid JSON data from Claude's response",
                )

            return extracted_data, None

        except Exception as e:
            return {}, f"Error extracting content: {str(e)}"

    def _build_url_extraction_prompt(self, url: str, schema_str: str) -> str:
        """Build the prompt for content extraction from URL.

        Args:
            url: URL to fetch
            schema_str: JSON string of the schema

        Returns:
            Formatted prompt string
        """
        return f"""Please fetch the webpage at {url} and extract data according to the provided schema.

Schema (defines what to extract):
```json
{schema_str}
```

Instructions:
1. Fetch the URL and analyze its content THOROUGHLY
2. Scan the ENTIRE webpage including:
   - Navigation menus and headers
   - Feature lists and service descriptions
   - Amenities/facilities sections
   - Class schedules and program listings
   - Footer sections and all page content
3. For each field in the schema:
   - Find ALL relevant information on the page (be exhaustive, not just prominent items)
   - For array fields with "Select from" in the description:
     * Cross-reference EACH option in the predefined list against the webpage content
     * Include ALL matching options you find anywhere on the page
     * Check for synonyms and related terms (e.g., "resistance training" = "Strength training")
   - Extract the data in the correct type (string, number, array, etc.)
   - If the information is not found, use null for required fields or omit optional fields
4. Be thorough and complete - find ALL matching items, not just a few examples
5. Return ONLY a valid JSON object with the extracted data
6. Do not include any explanatory text, only the JSON

Example output format:
{{
  "field_name_1": "extracted value",
  "field_name_2": 123,
  "field_name_3": ["item1", "item2", "item3"]
}}

Extract the data now. Be comprehensive and thorough. Return ONLY the JSON object, no other text."""

    def _build_html_extraction_prompt(self, html: str, schema: Dict[str, Any]) -> str:
        """Build the prompt for content extraction from HTML.

        Args:
            html: HTML content
            schema: Schema defining what to extract

        Returns:
            Formatted prompt string
        """
        # Format schema for the prompt
        schema_str = json.dumps(schema, indent=2)

        return f"""You are a data extraction expert. Your task is to extract specific information from HTML content based on a provided schema.

Schema (defines what to extract):
```json
{schema_str}
```

HTML Content:
```html
{html}
```

Instructions:
1. Extract data according to the schema fields
2. For each field in the schema:
   - Find the relevant information in the HTML
   - Extract the data in the correct type (string, number, array, etc.)
   - If the information is not found, use null for required fields or omit optional fields
3. Return ONLY a valid JSON object with the extracted data
4. Do not include any explanatory text, only the JSON

Example output format:
{{
  "field_name_1": "extracted value",
  "field_name_2": 123,
  "field_name_3": ["item1", "item2"]
}}

Extract the data now. Return ONLY the JSON object, no other text."""

    def _extract_data(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract and validate JSON data from Claude's response.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed data dict or None if invalid
        """
        try:
            # Log the raw response for debugging
            import logging
            logger = logging.getLogger("scraper-agent")
            logger.debug(f"Raw Claude response (first 500 chars): {response_text[:500]}")
            logger.debug(f"Raw Claude response (last 500 chars): {response_text[-500:]}")

            # Try to find JSON in the response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                # Try array format
                start_idx = response_text.find("[")
                end_idx = response_text.rfind("]") + 1

                if start_idx == -1 or end_idx == 0:
                    logger.error(f"No JSON found in response. Full response: {response_text}")
                    return None

            json_str = response_text[start_idx:end_idx]
            logger.debug(f"Extracted JSON string (first 500 chars): {json_str[:500]}")
            data = json.loads(json_str)

            return data

        except json.JSONDecodeError as e:
            import logging
            logger = logging.getLogger("scraper-agent")
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed JSON string: {response_text}")
            return None
        except Exception as e:
            import logging
            logger = logging.getLogger("scraper-agent")
            logger.error(f"Unexpected error in _extract_data: {e}")
            return None
