"""Main orchestrator agent for coordinating the scraping workflow."""
from typing import Optional, Callable, Any
from urllib.parse import urlparse

from ..models import ScrapeRequest, SessionStatus
from ..services import SessionManager, session_manager, HTTPClient
from ..services.sitemap_discovery import SitemapDiscovery
from ..services.html_cleaner import html_cleaner


class OrchestratorAgent:
    """Main agent that orchestrates Phase 1: sitemap-based raw HTML scraping."""

    def __init__(
        self,
        session_mgr: Optional[SessionManager] = None,
        sitemap_disco: Optional[SitemapDiscovery] = None,
    ):
        """Initialize the orchestrator agent.

        Args:
            session_mgr: Session manager instance
            sitemap_disco: Sitemap discovery instance
        """
        self.session_manager = session_mgr or session_manager
        self.sitemap_discovery = sitemap_disco or SitemapDiscovery()

    async def execute_scrape(
        self,
        request: ScrapeRequest,
        session_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, Any], None]] = None,
    ) -> tuple[str, bool]:
        """Execute Phase 1: Sitemap-based scraping with markdown conversion.

        This method:
        1. Discovers URLs from robots.txt → sitemaps
        2. Scrapes raw HTML from all discovered URLs
        3. Converts HTML to markdown (NO Claude - using BeautifulSoup)
        4. Saves both raw HTML and markdown

        Phase 2 (chunking + embedding) and Phase 3 (query) are separate services.

        Args:
            request: The scraping request
            session_id: Optional pre-created session ID. If None, creates new session.
            progress_callback: Optional callback for progress updates
                              callback(event_type: str, data: Any)

        Returns:
            Tuple of (session_id, success: bool)
        """
        print("=== NEW ORCHESTRATOR CODE EXECUTING ===")
        # Initialize session (use provided session_id or create new one)
        if session_id:
            # Use pre-created session_id, just load metadata
            metadata = self.session_manager.storage.load_metadata(session_id)
            if not metadata:
                # Session doesn't exist, create it
                session_id, metadata = await self.session_manager.initialize_session(request)
        else:
            # Create new session
            session_id, metadata = await self.session_manager.initialize_session(request)

        try:
            # Send progress update
            self._send_progress(
                progress_callback,
                "session_created",
                {"session_id": session_id, "status": "pending"},
            )

            # Update status to in_progress
            await self.session_manager.update_status(
                session_id, SessionStatus.IN_PROGRESS
            )
            self._send_progress(
                progress_callback, "status_update", {"status": "in_progress"}
            )

            # Step 1: Discover URLs from robots.txt → sitemaps
            domain = self._extract_domain(str(request.url))
            self._send_progress(
                progress_callback, "discovering_urls", {"domain": domain}
            )

            urls = await self.sitemap_discovery.discover_from_robots(domain)

            if not urls:
                await self._handle_error(
                    session_id, "No URLs discovered from sitemaps"
                )
                self._send_progress(
                    progress_callback, "error", {"message": "No URLs found in sitemaps"}
                )
                return session_id, False

            self._send_progress(
                progress_callback, "urls_discovered", {"count": len(urls), "urls": urls[:5]}
            )

            # Step 2: Scrape raw HTML from all URLs
            pages_data = []
            async with HTTPClient() as client:
                for idx, url in enumerate(urls):
                    self._send_progress(
                        progress_callback,
                        "scraping_page",
                        {"url": url, "progress": f"{idx + 1}/{len(urls)}"},
                    )

                    html, error = await client.fetch_url(url)

                    if error:
                        self._send_progress(
                            progress_callback,
                            "page_error",
                            {"url": url, "error": error},
                        )
                        continue

                    pages_data.append({"page_url": url, "raw_html": html})

                    self._send_progress(
                        progress_callback,
                        "page_scraped",
                        {"url": url, "html_length": len(html)},
                    )

            if not pages_data:
                await self._handle_error(
                    session_id, "Failed to scrape any pages"
                )
                self._send_progress(
                    progress_callback, "error", {"message": "No pages successfully scraped"}
                )
                return session_id, False

            # Step 3: Convert HTML to markdown
            self._send_progress(
                progress_callback, "converting_to_markdown", {"total_pages": len(pages_data)}
            )

            markdown_data = []
            for idx, page in enumerate(pages_data):
                self._send_progress(
                    progress_callback,
                    "converting_page",
                    {"url": page["page_url"], "progress": f"{idx + 1}/{len(pages_data)}"},
                )

                # Extract markdown sections from HTML
                sections = html_cleaner.extract_sections(page["raw_html"], page["page_url"])

                # Combine all sections into single markdown content
                markdown_content = ""
                if sections:
                    markdown_content = "\n\n".join(section["content"] for section in sections)

                # Extract clean page name from URL path
                page_name = self._extract_page_name(page["page_url"])

                markdown_data.append({
                    "page_url": page["page_url"],
                    "page_name": page_name,
                    "markdown_content": markdown_content
                })

                self._send_progress(
                    progress_callback,
                    "page_converted",
                    {"url": page["page_url"], "markdown_length": len(markdown_content)},
                )

            # Step 4: Save both raw HTML and markdown to session directory
            await self.session_manager.save_raw_html(session_id, pages_data)
            await self.session_manager.save_markdown(session_id, markdown_data)
            await self.session_manager.save_sources(session_id, urls)

            # Mark as completed
            await self.session_manager.update_status(session_id, SessionStatus.COMPLETED)
            self._send_progress(
                progress_callback,
                "completed",
                {
                    "session_id": session_id,
                    "total_urls": len(urls),
                    "scraped_pages": len(pages_data),
                },
            )

            return session_id, True

        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            await self._handle_error(session_id, error_msg)
            self._send_progress(progress_callback, "error", {"message": error_msg})
            return session_id, False

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain (scheme + netloc)
        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_page_name(self, url: str) -> str:
        """Extract a clean page name from URL path.

        Args:
            url: Full URL

        Returns:
            Clean page name extracted from URL path
        """
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        if not path:
            return "home"

        # Get the last path segment (without file extension)
        segments = path.split('/')
        last_segment = segments[-1]

        # Remove file extensions (.html, .php, etc.)
        if '.' in last_segment:
            last_segment = last_segment.rsplit('.', 1)[0]

        # If empty after removing extension, use second-to-last segment
        if not last_segment and len(segments) > 1:
            last_segment = segments[-2]

        # Convert URL-style to readable: "about-us" -> "about-us"
        # Keep hyphens as they make good page identifiers
        return last_segment or "home"

    async def _handle_error(self, session_id: str, error_message: str) -> None:
        """Handle error by updating session status.

        Args:
            session_id: The session identifier
            error_message: Error message
        """
        await self.session_manager.update_status(
            session_id, SessionStatus.FAILED, error_message
        )

    def _send_progress(
        self,
        callback: Optional[Callable[[str, Any], None]],
        event_type: str,
        data: Any,
    ) -> None:
        """Send progress update via callback.

        Args:
            callback: Progress callback function
            event_type: Type of event
            data: Event data
        """
        if callback:
            try:
                callback(event_type, data)
            except Exception:
                # Ignore callback errors to not disrupt workflow
                pass


# Global orchestrator instance
orchestrator = OrchestratorAgent()
