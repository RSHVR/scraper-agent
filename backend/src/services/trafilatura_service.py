"""Trafilatura-based content extraction service.

Trafilatura is specifically designed for web content extraction and handles
modern JavaScript-heavy sites better than simple BeautifulSoup approaches.
It uses machine learning and heuristics to identify main content while
filtering out boilerplate (navigation, ads, footers, etc.).
"""

import trafilatura
from trafilatura.settings import use_config
from typing import Optional
from dataclasses import dataclass

from ..utils.logger import logger


@dataclass
class ExtractionResult:
    """Result from content extraction."""
    text: Optional[str] = None
    markdown: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    error: Optional[str] = None


class TrafilaturaService:
    """Content extraction using trafilatura.

    This service provides robust extraction of main content from web pages,
    handling modern layouts that rely on divs/spans rather than semantic HTML.
    """

    def __init__(self):
        """Initialize the trafilatura service with optimized config."""
        self.config = use_config()
        # Increase timeout for complex pages
        self.config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

    def extract_from_html(
        self,
        html: str,
        url: Optional[str] = None
    ) -> ExtractionResult:
        """Extract content from HTML using trafilatura.

        Args:
            html: Raw HTML string
            url: Optional URL for context (helps with link resolution)

        Returns:
            ExtractionResult with text, markdown, and metadata
        """
        try:
            # Extract plain text with links and tables
            text = trafilatura.extract(
                html,
                url=url,
                include_links=True,
                include_tables=True,
                deduplicate=True,
                config=self.config
            )

            # Extract as markdown format
            markdown = trafilatura.extract(
                html,
                url=url,
                output_format='markdown',
                include_links=True,
                include_tables=True,
                config=self.config
            )

            # Extract metadata (title, author, date, etc.)
            metadata = trafilatura.extract_metadata(html, default_url=url)

            return ExtractionResult(
                text=text,
                markdown=markdown,
                title=metadata.title if metadata else None,
                author=metadata.author if metadata else None,
                date=metadata.date if metadata else None
            )

        except Exception as e:
            logger.error(f"Trafilatura extraction failed: {e}")
            return ExtractionResult(error=str(e))

    def extract_with_fallback(
        self,
        html: str,
        url: Optional[str] = None
    ) -> ExtractionResult:
        """Extract content with BeautifulSoup fallback if trafilatura returns nothing.

        Some pages may have unusual structures that trafilatura can't parse.
        In those cases, we fall back to a simple BeautifulSoup text extraction.

        Args:
            html: Raw HTML string
            url: Optional URL for context

        Returns:
            ExtractionResult with content from trafilatura or fallback
        """
        result = self.extract_from_html(html, url)

        # If trafilatura found content, return it
        if result.text or result.error:
            return result

        # Fallback to BeautifulSoup for edge cases
        logger.info("Trafilatura returned empty, using BeautifulSoup fallback")
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'lxml')

            # Remove script, style, nav, footer, header tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            # Get all text
            text = soup.get_text(separator='\n', strip=True)

            # Limit to reasonable size
            result.text = text[:50000] if text else None
            result.markdown = text[:50000] if text else None

            return result

        except Exception as e:
            logger.error(f"BeautifulSoup fallback failed: {e}")
            return ExtractionResult(error=f"Both extractions failed: {str(e)}")


# Global instance for reuse
trafilatura_service = TrafilaturaService()
