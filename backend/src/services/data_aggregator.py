"""Data aggregation service for merging extractions from multiple pages."""
from typing import Dict, Any, List
from ..utils.logger import logger


class DataAggregator:
    """Aggregates data extracted from multiple pages."""

    def __init__(self):
        """Initialize the data aggregator."""
        pass

    def aggregate(
        self, extractions: List[Dict[str, Any]], track_sources: bool = True
    ) -> Dict[str, Any]:
        """Aggregate data from multiple page extractions.

        Rules:
        - Merge all data from all pages
        - If a field appears multiple times with different values, convert to array
        - Track source URLs for each field if track_sources=True

        Args:
            extractions: List of extraction dictionaries with 'data' and 'source' keys
                        Format: [{"data": {...}, "source": "url1"}, ...]
            track_sources: Whether to track which page each field came from

        Returns:
            Aggregated data dictionary with optional source tracking
        """
        if not extractions:
            return {}

        aggregated = {}
        sources_map = {}  # field_name -> list of source URLs

        for extraction in extractions:
            data = extraction.get('data', {})
            source = extraction.get('source', 'unknown')

            if not data:
                continue

            for key, value in data.items():
                if value is None or value == "":
                    continue  # Skip empty values

                # First occurrence of this field
                if key not in aggregated:
                    aggregated[key] = value
                    if track_sources:
                        sources_map[key] = [source]

                # Field already exists
                else:
                    existing = aggregated[key]

                    # If values are the same, just track source
                    if existing == value:
                        if track_sources and source not in sources_map.get(key, []):
                            sources_map.setdefault(key, []).append(source)
                        continue

                    # Values are different - convert to array
                    if isinstance(existing, list):
                        # Already an array, append if not duplicate
                        if value not in existing:
                            aggregated[key].append(value)
                            if track_sources:
                                sources_map.setdefault(key, []).append(source)
                    else:
                        # Convert to array
                        aggregated[key] = [existing, value]
                        if track_sources:
                            # Preserve original source and add new one
                            original_sources = sources_map.get(key, [])
                            sources_map[key] = original_sources + [source]

        # Add sources to result if tracking
        if track_sources and sources_map:
            aggregated['_sources'] = sources_map

        logger.info(f"Aggregated data from {len(extractions)} pages into {len(aggregated)} fields")
        return aggregated

    def merge_nested(self, obj1: Any, obj2: Any) -> Any:
        """Recursively merge two objects (for nested structures).

        Args:
            obj1: First object
            obj2: Second object

        Returns:
            Merged object
        """
        # If both are dicts, merge recursively
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            result = obj1.copy()
            for key, value in obj2.items():
                if key in result:
                    result[key] = self.merge_nested(result[key], value)
                else:
                    result[key] = value
            return result

        # If both are lists, combine them
        elif isinstance(obj1, list) and isinstance(obj2, list):
            combined = obj1 + obj2
            # Remove duplicates while preserving order
            seen = set()
            result = []
            for item in combined:
                # For unhashable types, just append
                try:
                    if item not in seen:
                        seen.add(item)
                        result.append(item)
                except TypeError:
                    result.append(item)
            return result

        # If one is list and other isn't, convert to list
        elif isinstance(obj1, list):
            if obj2 not in obj1:
                return obj1 + [obj2]
            return obj1
        elif isinstance(obj2, list):
            if obj1 not in obj2:
                return [obj1] + obj2
            return obj2

        # Different primitive values, convert to list
        elif obj1 != obj2:
            return [obj1, obj2]

        # Same values
        else:
            return obj1


# Convenience function
def aggregate_extractions(
    extractions: List[Dict[str, Any]], track_sources: bool = True
) -> Dict[str, Any]:
    """Convenience function to aggregate extractions.

    Args:
        extractions: List of extraction dictionaries
        track_sources: Whether to track source URLs

    Returns:
        Aggregated data
    """
    aggregator = DataAggregator()
    return aggregator.aggregate(extractions, track_sources)
