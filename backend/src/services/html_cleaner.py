"""HTML cleaning service for extracting clean text from raw HTML."""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, NavigableString, Tag

from ..utils.logger import logger


class HTMLCleaner:
    """Service for cleaning and extracting meaningful content from HTML."""

    # Tags to completely remove (navigation, scripts, styles, etc.)
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'iframe', 'object', 'embed',
        'nav', 'header', 'footer', 'aside', 'menu',
        'form', 'input', 'button', 'select', 'textarea',
        'svg', 'path', 'canvas'
    ]

    # Tags that indicate navigation/UI elements
    NAV_CLASSES = [
        'nav', 'navigation', 'menu', 'header', 'footer', 'sidebar',
        'breadcrumb', 'pagination', 'cookie', 'banner', 'modal',
        'popup', 'overlay', 'share', 'social', 'ad', 'advertisement'
    ]

    # Minimum meaningful text length
    MIN_TEXT_LENGTH = 10

    def __init__(self):
        """Initialize the HTML cleaner."""
        pass

    def clean_html(self, html: str) -> str:
        """Clean HTML and extract meaningful text content.

        Args:
            html: Raw HTML string

        Returns:
            Cleaned text content
        """
        if not html or not html.strip():
            return ""

        try:
            soup = BeautifulSoup(html, 'lxml')

            # Step 1: Remove unwanted tags
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Step 2: Remove navigation/UI elements by class/id
            for element in soup.find_all(True):
                if self._is_navigation_element(element):
                    element.decompose()

            # Step 3: Extract text from main content areas
            main_content = self._extract_main_content(soup)

            # Step 4: Clean the extracted text
            cleaned_text = self._clean_text(main_content)

            return cleaned_text

        except Exception as e:
            logger.error(f"Error cleaning HTML: {e}")
            return ""

    def extract_sections(self, html: str) -> List[Dict[str, str]]:
        """Extract content from HTML as markdown-formatted text.

        Args:
            html: Raw HTML string

        Returns:
            List with single section containing markdown content
        """
        if not html or not html.strip():
            return []

        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove unwanted tags only (keep structure intact)
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Find main content container
            # Prioritize semantic HTML5 tags, then body, to avoid matching wrong divs
            main = soup.find('main') or soup.find('article') or soup.body or soup

            # Ensure main is not None
            if not main:
                logger.warning("No main content container found")
                return []

            # Convert HTML to markdown-like structure
            markdown_lines = []
            seen_content = set()  # Track content to avoid duplicates
            all_elements = main.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'dd', 'dt'])

            for element in all_elements:
                try:
                    text = element.get_text(separator=' ', strip=True)
                    if not text:
                        continue

                    # Skip if we've already seen this exact content (deduplication)
                    if text in seen_content:
                        continue
                    seen_content.add(text)

                    # Format based on element type
                    if element.name == 'h1':
                        markdown_lines.append(f"\n# {text}\n")
                    elif element.name == 'h2':
                        markdown_lines.append(f"\n## {text}\n")
                    elif element.name == 'h3':
                        markdown_lines.append(f"\n### {text}\n")
                    elif element.name == 'h4':
                        markdown_lines.append(f"\n#### {text}\n")
                    elif element.name == 'h5':
                        markdown_lines.append(f"\n##### {text}\n")
                    elif element.name == 'h6':
                        markdown_lines.append(f"\n###### {text}\n")
                    elif element.name == 'li':
                        markdown_lines.append(f"- {text}")
                    else:
                        # Paragraphs and other content - keep all text
                        markdown_lines.append(text)

                except Exception as elem_error:
                    logger.debug(f"Skipping element due to error: {elem_error}")
                    continue

            # Join all markdown lines
            markdown_content = '\n'.join(markdown_lines)

            # Clean the text
            cleaned = self._clean_text(markdown_content)

            if len(cleaned) >= self.MIN_TEXT_LENGTH:
                logger.debug(f"Extracted markdown content ({len(cleaned)} chars)")
                return [{
                    'heading': 'Content',
                    'content': cleaned
                }]

            logger.warning("No meaningful content extracted")
            return []

        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            return []

    def _is_navigation_element(self, element: Tag) -> bool:
        """Check if element is a navigation/UI element.

        Args:
            element: BeautifulSoup Tag

        Returns:
            True if element should be removed
        """
        if not isinstance(element, Tag):
            return False

        # Never remove structural elements
        if element.name in ['html', 'body', 'main', 'article']:
            return False

        # Check tag name
        if element.name in ['nav', 'header', 'footer', 'aside']:
            return True

        # Check class and id attributes
        attrs = ' '.join([
            str(element.get('class', [])),
            str(element.get('id', ''))
        ]).lower()

        for nav_keyword in self.NAV_CLASSES:
            if nav_keyword in attrs:
                return True

        # Check for common navigation patterns
        if element.name == 'ul' and any(kw in attrs for kw in ['menu', 'nav']):
            return True

        return False

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from cleaned soup.

        Args:
            soup: BeautifulSoup object

        Returns:
            Main content text
        """
        # Priority order for main content
        content_candidates = [
            soup.find('main'),
            soup.find('article'),
            soup.find('div', class_=re.compile(r'content|main|body|post')),
            soup.find('div', id=re.compile(r'content|main|body|post')),
        ]

        # Use first valid candidate
        for candidate in content_candidates:
            if candidate:
                return candidate.get_text(separator=' ', strip=True)

        # Fallback to body
        if soup.body:
            return soup.body.get_text(separator=' ', strip=True)

        # Last resort: all text
        return soup.get_text(separator=' ', strip=True)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove repeated punctuation
        text = re.sub(r'([.!?,])\1+', r'\1', text)

        # Remove standalone special characters
        text = re.sub(r'\s+[^\w\s]\s+', ' ', text)

        # Remove very short repeated words (often UI noise)
        text = re.sub(r'\b(\w{1,2})\s+\1\s+\1+\b', '', text)

        # Strip
        text = text.strip()

        return text

    def clean_and_chunk(
        self,
        html: str,
        page_name: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[Dict[str, str]]:
        """Clean HTML and create overlapping chunks.

        Args:
            html: Raw HTML
            page_name: Page identifier
            chunk_size: Target characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of chunks with metadata
        """
        # Extract sections first
        sections = self.extract_sections(html)

        if not sections:
            logger.warning(f"No sections extracted from {page_name}")
            return []

        chunks = []

        for section in sections:
            heading = section['heading']
            content = section['content']

            # If content is small enough, keep as single chunk
            if len(content) <= chunk_size:
                chunks.append({
                    'text': f"{heading}\n\n{content}",
                    'heading': heading,
                    'page_name': page_name,
                    'char_count': len(content)
                })
            else:
                # Split into overlapping chunks
                words = content.split()
                current_chunk = []
                current_length = 0

                for i, word in enumerate(words):
                    current_chunk.append(word)
                    current_length += len(word) + 1  # +1 for space

                    # Check if chunk is large enough
                    if current_length >= chunk_size:
                        chunk_text = ' '.join(current_chunk)
                        chunks.append({
                            'text': f"{heading}\n\n{chunk_text}",
                            'heading': heading,
                            'page_name': page_name,
                            'char_count': len(chunk_text)
                        })

                        # Start next chunk with overlap
                        overlap_words = int(len(current_chunk) * (overlap / chunk_size))
                        current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
                        current_length = sum(len(w) + 1 for w in current_chunk)

                # Add remaining chunk
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text) >= self.MIN_TEXT_LENGTH:
                        chunks.append({
                            'text': f"{heading}\n\n{chunk_text}",
                            'heading': heading,
                            'page_name': page_name,
                            'char_count': len(chunk_text)
                        })

        logger.info(f"Created {len(chunks)} clean chunks from {page_name}")
        return chunks


# Global instance
html_cleaner = HTMLCleaner()
