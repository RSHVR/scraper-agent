"""URL queue manager for tracking and deduplicating URLs during crawling."""
from typing import Set, List
from urllib.parse import urlparse, urlunparse


class URLQueue:
    """Manages URL queue with deduplication and filtering."""

    def __init__(self):
        """Initialize the URL queue."""
        self.visited: Set[str] = set()
        self.pending: List[str] = []

    def add_urls(self, urls: List[str]) -> None:
        """Add multiple URLs to the queue.

        Args:
            urls: List of URLs to add
        """
        for url in urls:
            self.add_url(url)

    def add_url(self, url: str) -> bool:
        """Add a URL to the queue if not already visited.

        Args:
            url: URL to add

        Returns:
            True if URL was added, False if already visited
        """
        normalized = self.normalize_url(url)

        if normalized in self.visited:
            return False

        if normalized not in self.pending:
            self.pending.append(normalized)
            return True

        return False

    def get_next(self) -> str | None:
        """Get the next URL from the queue.

        Returns:
            Next URL or None if queue is empty
        """
        if not self.pending:
            return None

        url = self.pending.pop(0)
        self.visited.add(url)
        return url

    def mark_visited(self, url: str) -> None:
        """Mark a URL as visited.

        Args:
            url: URL to mark as visited
        """
        normalized = self.normalize_url(url)
        self.visited.add(normalized)

    def is_visited(self, url: str) -> bool:
        """Check if URL has been visited.

        Args:
            url: URL to check

        Returns:
            True if URL has been visited
        """
        normalized = self.normalize_url(url)
        return normalized in self.visited

    def pending_count(self) -> int:
        """Get count of pending URLs.

        Returns:
            Number of pending URLs
        """
        return len(self.pending)

    def visited_count(self) -> int:
        """Get count of visited URLs.

        Returns:
            Number of visited URLs
        """
        return len(self.visited)

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for comparison.

        - Remove trailing slashes
        - Remove fragments
        - Lowercase domain
        - Keep query params (they might be significant)

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        if not url:
            return ""

        # Parse URL
        parsed = urlparse(url)

        # Normalize components
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip('/')

        # Keep path as "/" if it was empty
        if not path:
            path = '/'

        # Reconstruct without fragment
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))

        return normalized

    def clear(self) -> None:
        """Clear all URLs from queue and visited set."""
        self.pending.clear()
        self.visited.clear()
