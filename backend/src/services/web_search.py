"""Web search service for finding missing gym information."""
import json
from typing import Dict, Any, List, Optional
from anthropic import Anthropic

from ..config import settings
from ..utils.logger import logger


class WebSearchService:
    """Service for using Claude's web search to find missing gym data."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the web search service.

        Args:
            api_key: Anthropic API key. Defaults to settings.anthropic_api_key
        """
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def search_gym_info(
        self,
        gym_name: str,
        city: str,
        state: str,
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """Search for missing gym information using web search.

        Args:
            gym_name: Name of the gym
            city: City where gym is located
            state: State/province where gym is located
            missing_fields: List of field names that are missing

        Returns:
            Dict with found data for missing fields (only google_maps_link and hours_of_operation)
        """
        # Only search for fields we can find via web search
        searchable_fields = []
        if "google_maps_link" in missing_fields:
            searchable_fields.append("google_maps_link")
        if "hours_of_operation" in missing_fields:
            searchable_fields.append("hours_of_operation")

        if not searchable_fields:
            logger.info("No searchable fields missing, skipping web search")
            return {}

        logger.info(
            f"Searching web for {gym_name} in {city}, {state} - fields: {searchable_fields}"
        )

        # Build search prompt
        prompt = self._build_search_prompt(gym_name, city, state, searchable_fields)

        try:
            # Call Claude API with web search tool
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
                ],
            )

            # Extract the response text
            response_text = ""
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    response_text += block.text

            # Parse JSON from response
            found_data = self._extract_data(response_text)

            logger.info(f"Web search found: {list(found_data.keys())}")
            return found_data

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return {}

    def _build_search_prompt(
        self, gym_name: str, city: str, state: str, fields: List[str]
    ) -> str:
        """Build the search prompt.

        Args:
            gym_name: Gym name
            city: City
            state: State
            fields: List of fields to search for

        Returns:
            Formatted prompt string
        """
        field_instructions = []
        if "google_maps_link" in fields:
            field_instructions.append(
                '- "google_maps_link": The Google Maps URL for this gym location'
            )
        if "hours_of_operation" in fields:
            field_instructions.append(
                """- "hours_of_operation": An object with days of the week (monday, tuesday, wednesday, thursday, friday, saturday, sunday) and their hours in format "HH:MM AM/PM - HH:MM AM/PM" or "Closed" """
            )

        fields_str = "\n".join(field_instructions)

        return f"""Search the web to find the following information for "{gym_name}" located in {city}, {state}:

{fields_str}

Search Google to find:
1. The gym's Google Maps page or listing to get the Maps link and hours of operation
2. The gym's official website or business listings that show hours

Return ONLY a JSON object with the information you find. Use these exact field names:
- google_maps_link (string): Full Google Maps URL
- hours_of_operation (object): Days as keys, hours as values

Example format:
{{
  "google_maps_link": "https://www.google.com/maps/place/...",
  "hours_of_operation": {{
    "monday": "5:00 AM - 10:00 PM",
    "tuesday": "5:00 AM - 10:00 PM",
    "wednesday": "5:00 AM - 10:00 PM",
    "thursday": "5:00 AM - 10:00 PM",
    "friday": "5:00 AM - 9:00 PM",
    "saturday": "7:00 AM - 7:00 PM",
    "sunday": "7:00 AM - 7:00 PM"
  }}
}}

If you can't find certain information, omit those fields from the JSON. Return ONLY the JSON object, no other text."""

    def _extract_data(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON data from Claude's response.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed data dict or empty dict if invalid
        """
        try:
            # Try to find JSON in the response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON found in web search response")
                return {}

            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)

            # Validate that we only have allowed fields
            allowed_fields = {"google_maps_link", "hours_of_operation"}
            filtered_data = {
                k: v for k, v in data.items() if k in allowed_fields
            }

            return filtered_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from web search: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error extracting data from web search: {e}")
            return {}


# Global web search service instance
web_search_service = WebSearchService()
