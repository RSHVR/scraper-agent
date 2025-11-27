"""Sitemap discovery service for finding and parsing sitemaps."""
import xml.etree.ElementTree as ET
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from ..config import settings
from ..utils.logger import logger
from .http_client import HTTPClient


class SitemapDiscovery:
    """Service for discovering and parsing website sitemaps."""

    def __init__(self):
        """Initialize the sitemap discovery service."""
        self.http_timeout = settings.default_timeout

    async def discover_urls(self, domain: str, max_urls: Optional[int] = None) -> List[str]:
        """Discover URLs from sitemap or by crawling.

        Args:
            domain: Domain to discover URLs from (e.g., "example.com" or "https://example.com")
            max_urls: Maximum number of URLs to return. Defaults to settings.max_pages_per_site

        Returns:
            List of discovered URLs
        """
        max_urls = max_urls or settings.max_pages_per_site

        # Normalize domain to full URL
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'

        logger.info(f"Discovering URLs for {domain} (max: {max_urls})")

        # Try sitemap discovery first
        urls = await self._discover_from_sitemap(domain)

        # If no sitemap found or enabled, crawl from homepage
        if not urls and settings.enable_sitemap_crawl:
            logger.info(f"No sitemap found for {domain}, falling back to crawling")
            urls = await self._crawl_from_homepage(domain, max_urls)

        # Limit to max URLs
        urls = urls[:max_urls]

        logger.info(f"Discovered {len(urls)} URLs for {domain}")
        return urls

    async def discover_from_robots(self, domain: str) -> List[str]:
        """Discover URLs by checking robots.txt for sitemap directives.

        This is the FIRST priority method - always check robots.txt first.
        Parses robots.txt for all Sitemap: directives and fetches those sitemaps.

        Args:
            domain: Base domain URL (e.g., "https://example.com")

        Returns:
            List of URLs discovered from sitemaps listed in robots.txt
        """
        # Normalize domain to full URL
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'

        robots_url = urljoin(domain, '/robots.txt')
        logger.info(f"Checking robots.txt at {robots_url}")

        try:
            async with HTTPClient() as client:
                robots_content, error = await client.fetch_url(robots_url)

                if error or not robots_content:
                    logger.debug(f"No robots.txt found at {robots_url}")
                    return []

                # Extract ALL sitemap URLs from robots.txt
                sitemap_urls = self._extract_all_sitemaps_from_robots(robots_content)

                if not sitemap_urls:
                    logger.debug("No Sitemap: directives found in robots.txt")
                    return []

                logger.info(f"Found {len(sitemap_urls)} sitemap(s) in robots.txt: {sitemap_urls}")

                # Fetch and parse all sitemaps using the recursive fetcher
                all_urls = []
                for sitemap_url in sitemap_urls:
                    try:
                        # Use the new recursive fetcher (handles sitemap indexes)
                        urls = await self._fetch_and_parse_sitemaps_recursive(sitemap_url)
                        if urls:
                            logger.info(f"Extracted {len(urls)} URLs from {sitemap_url}")
                            all_urls.extend(urls)

                    except Exception as e:
                        logger.warning(f"Failed to parse sitemap {sitemap_url}: {e}")
                        continue

                # Remove duplicates while preserving order
                unique_urls = list(dict.fromkeys(all_urls))
                logger.info(f"Total URLs from robots.txt sitemaps: {len(unique_urls)}")
                return unique_urls

        except Exception as e:
            logger.error(f"Failed to check robots.txt: {e}")
            return []

    async def discover_from_html(
        self, domain: str, max_urls: Optional[int] = None, crawl_depth: int = 1
    ) -> List[str]:
        """Discover URLs by extracting links from HTML (FALLBACK method).

        Only use this if robots.txt and sitemap.xml don't exist.
        Fetches homepage and extracts all internal links.

        Args:
            domain: Base domain URL (e.g., "https://example.com")
            max_urls: Maximum number of URLs to return
            crawl_depth: How many levels deep to crawl (1 = homepage only, 2 = homepage + linked pages)

        Returns:
            List of URLs discovered from HTML links
        """
        # Normalize domain to full URL
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'

        max_urls = max_urls or settings.max_pages_per_site

        logger.info(f"Discovering URLs from HTML for {domain} (depth: {crawl_depth}, max: {max_urls})")

        try:
            # Fetch homepage
            async with HTTPClient() as client:
                html, error = await client.fetch_url(domain)

                if error or not html:
                    logger.warning(f"Failed to fetch homepage for HTML discovery: {error}")
                    return [domain]  # Return at least the homepage

                # Extract links from homepage
                urls = self._extract_links(html, domain)

                # Add homepage if not present
                if domain not in urls:
                    urls.insert(0, domain)

                logger.info(f"Extracted {len(urls)} URLs from homepage HTML")

                # If crawl_depth > 1, fetch linked pages and extract their links too
                if crawl_depth > 1 and len(urls) > 1:
                    logger.info(f"Crawling depth {crawl_depth}, fetching linked pages...")
                    second_level_urls = set(urls)

                    # Crawl a subset of first-level pages
                    pages_to_crawl = urls[1:min(10, len(urls))]  # Crawl up to 10 pages from homepage

                    for page_url in pages_to_crawl:
                        try:
                            async with HTTPClient() as client:
                                page_html, page_error = await client.fetch_url(page_url)

                                if page_error or not page_html:
                                    continue

                                # Extract links from this page
                                page_links = self._extract_links(page_html, domain)
                                second_level_urls.update(page_links)

                        except Exception as e:
                            logger.debug(f"Failed to crawl linked page {page_url}: {e}")
                            continue

                    urls = list(second_level_urls)
                    logger.info(f"After depth-{crawl_depth} crawl: {len(urls)} total URLs")

                # Limit to max URLs
                urls = urls[:max_urls]

                return urls

        except Exception as e:
            logger.error(f"Failed to discover URLs from HTML: {e}")
            return [domain]  # Return at least the homepage

    async def _discover_from_sitemap(self, domain: str) -> List[str]:
        """Try to find and parse sitemap from common locations.

        NOTE: This is a fallback method. robots.txt is checked first by discover_from_robots().
        This method ONLY tries common sitemap locations like /sitemap.xml, /sitemap_index.xml, etc.

        Args:
            domain: Base domain URL

        Returns:
            List of URLs from sitemap(s)
        """
        sitemap_urls = self._get_sitemap_candidates(domain)

        for sitemap_url in sitemap_urls:
            try:
                logger.debug(f"Trying sitemap: {sitemap_url}")

                # Use the new recursive fetcher (handles sitemap indexes)
                urls = await self._fetch_and_parse_sitemaps_recursive(sitemap_url)

                if urls:
                    logger.info(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
                    return urls

            except Exception as e:
                logger.debug(f"Failed to fetch sitemap {sitemap_url}: {e}")
                continue

        return []

    def _get_sitemap_candidates(self, domain: str) -> List[str]:
        """Get list of common sitemap locations to try.

        Args:
            domain: Base domain URL

        Returns:
            List of sitemap URLs to try
        """
        return [
            urljoin(domain, '/sitemap.xml'),
            urljoin(domain, '/sitemap_index.xml'),
            urljoin(domain, '/sitemap-index.xml'),
            urljoin(domain, '/sitemap1.xml'),
            urljoin(domain, '/post-sitemap.xml'),
            urljoin(domain, '/page-sitemap.xml'),
        ]

    def _parse_sitemap(self, xml_content: str) -> tuple[List[str], List[str]]:
        """Parse sitemap XML and extract URLs (pure XML parsing, no HTTP fetching).

        Args:
            xml_content: Sitemap XML content

        Returns:
            Tuple of (content_urls, sitemap_index_urls)
            - content_urls: List of content page URLs (non-XML)
            - sitemap_index_urls: List of nested sitemap URLs (if this is a sitemap index)
        """
        try:
            root = ET.fromstring(xml_content)

            # Handle different sitemap namespaces
            namespaces = {
                'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                'news': 'http://www.google.com/schemas/sitemap-news/0.9',
                'image': 'http://www.google.com/schemas/sitemap-image/1.1',
            }

            urls = []

            # Try with namespace
            for loc in root.findall('.//sm:loc', namespaces):
                if loc.text:
                    urls.append(loc.text)

            # Try without namespace
            if not urls:
                for loc in root.findall('.//loc'):
                    if loc.text:
                        urls.append(loc.text)

            # Check if this is a sitemap index (pointing to other sitemaps)
            # Handle both namespaced and non-namespaced tags
            # e.g., "{http://www.sitemaps.org/schemas/sitemap/0.9}sitemapindex" or "sitemapindex"
            tag_name = root.tag.split('}')[-1]  # Strip namespace if present
            if tag_name == 'sitemapindex':
                logger.info(f"Detected sitemap index with {len(urls)} nested sitemaps")
                # Return empty content URLs and all URLs as sitemap indexes
                sitemap_urls = [url for url in urls if url.lower().endswith('.xml')]
                return [], sitemap_urls

            # This is a regular sitemap - filter out XML files (only return content pages)
            content_urls = [url for url in urls if not url.lower().endswith('.xml')]
            logger.debug(f"Parsed sitemap: {len(content_urls)} content URLs (filtered {len(urls) - len(content_urls)} XML files)")

            return content_urls, []

        except ET.ParseError as e:
            logger.debug(f"Failed to parse sitemap XML: {e}")
            return [], []

    async def _fetch_and_parse_sitemaps_recursive(
        self, sitemap_url: str, depth: int = 0, max_depth: int = 3
    ) -> List[str]:
        """Fetch and parse sitemaps recursively, handling sitemap indexes.

        This method separates HTTP fetching from XML parsing:
        1. Fetch sitemap XML with HTTPClient
        2. Parse XML with _parse_sitemap()
        3. If sitemap index found, recursively fetch nested sitemaps
        4. Return all accumulated content URLs

        Args:
            sitemap_url: URL of sitemap to fetch
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            List of content page URLs found in sitemap(s)
        """
        if depth >= max_depth:
            logger.warning(f"Max sitemap recursion depth ({max_depth}) reached at {sitemap_url}")
            return []

        try:
            # STEP 1: Fetch sitemap XML with HTTPClient
            async with HTTPClient() as client:
                xml_content, error = await client.fetch_url(sitemap_url)

                if error or not xml_content:
                    logger.warning(f"Failed to fetch sitemap {sitemap_url}: {error}")
                    return []

            # STEP 2: Parse XML with pure XML parser
            content_urls, nested_sitemap_urls = self._parse_sitemap(xml_content)

            # STEP 3: If this is a sitemap index, recursively fetch nested sitemaps
            if nested_sitemap_urls:
                logger.info(
                    f"Sitemap index at {sitemap_url} contains {len(nested_sitemap_urls)} "
                    f"nested sitemaps, fetching recursively (depth {depth + 1}/{max_depth})"
                )

                all_content_urls = []
                for nested_url in nested_sitemap_urls:
                    logger.debug(f"Fetching nested sitemap: {nested_url}")
                    nested_content = await self._fetch_and_parse_sitemaps_recursive(
                        nested_url, depth + 1, max_depth
                    )
                    all_content_urls.extend(nested_content)
                    logger.info(f"Extracted {len(nested_content)} content URLs from {nested_url}")

                logger.info(f"Total {len(all_content_urls)} content URLs from sitemap index {sitemap_url}")
                return all_content_urls

            # STEP 4: Return content URLs from regular sitemap
            if content_urls:
                logger.debug(f"Extracted {len(content_urls)} content URLs from {sitemap_url}")

            return content_urls

        except Exception as e:
            logger.warning(f"Error fetching/parsing sitemap {sitemap_url}: {e}")
            return []

    def _extract_all_sitemaps_from_robots(self, robots_content: str) -> List[str]:
        """Extract ALL sitemap URLs from robots.txt.

        Args:
            robots_content: Contents of robots.txt

        Returns:
            List of sitemap URLs found in robots.txt
        """
        sitemap_urls = []
        for line in robots_content.split('\n'):
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                # Split on first colon only, in case URL contains colons
                sitemap_url = line.split(':', 1)[1].strip()
                if sitemap_url:
                    sitemap_urls.append(sitemap_url)
        return sitemap_urls

    def _extract_sitemap_from_robots(self, robots_content: str) -> Optional[str]:
        """Extract first sitemap URL from robots.txt (legacy method).

        Args:
            robots_content: Contents of robots.txt

        Returns:
            Sitemap URL if found, None otherwise
        """
        sitemaps = self._extract_all_sitemaps_from_robots(robots_content)
        return sitemaps[0] if sitemaps else None

    async def _crawl_from_homepage(self, domain: str, max_urls: int) -> List[str]:
        """Crawl from homepage to discover URLs.

        Args:
            domain: Base domain URL
            max_urls: Maximum number of URLs to discover

        Returns:
            List of discovered URLs
        """
        try:
            async with HTTPClient() as client:
                html, error = await client.fetch_url(domain)

                if error or not html:
                    logger.warning(f"Failed to fetch homepage for crawling: {error}")
                    return [domain]  # Return at least the homepage

                # Extract links
                urls = self._extract_links(html, domain)

                # Add homepage
                if domain not in urls:
                    urls.insert(0, domain)

                logger.info(f"Crawled {len(urls)} URLs from homepage")
                return urls[:max_urls]

        except Exception as e:
            logger.error(f"Failed to crawl from homepage: {e}")
            return [domain]  # Return at least the homepage

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract internal links from HTML.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            links: Set[str] = set()
            base_domain = urlparse(base_url).netloc

            for anchor in soup.find_all('a', href=True):
                href = anchor['href']

                # Skip empty, anchor, and javascript links
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue

                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)

                # Only include same-domain links
                if urlparse(absolute_url).netloc == base_domain:
                    # Remove fragments and query params for uniqueness
                    url_without_fragment = absolute_url.split('#')[0]

                    # Filter out common non-HTML resources
                    if not self._is_resource_file(url_without_fragment):
                        links.add(url_without_fragment)

            return list(links)

        except Exception as e:
            logger.warning(f"Failed to extract links from HTML: {e}")
            return []

    def _is_resource_file(self, url: str) -> bool:
        """Check if URL points to a non-HTML resource.

        Args:
            url: URL to check

        Returns:
            True if URL is a resource file, False otherwise
        """
        resource_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',  # Images
            '.css', '.js', '.json',  # Stylesheets and scripts
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',  # Documents
            '.zip', '.tar', '.gz',  # Archives
            '.mp4', '.avi', '.mov',  # Videos
            '.mp3', '.wav',  # Audio
            '.xml',  # XML files (sitemaps, feeds, etc.)
        ]

        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in resource_extensions)


# Convenience function
async def discover_urls(domain: str, max_urls: Optional[int] = None) -> List[str]:
    """Convenience function to discover URLs from a domain.

    Args:
        domain: Domain to discover URLs from
        max_urls: Maximum number of URLs to return

    Returns:
        List of discovered URLs
    """
    discovery = SitemapDiscovery()
    return await discovery.discover_urls(domain, max_urls)
