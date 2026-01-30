"""Browser client service for rendering JavaScript-heavy pages."""
import asyncio
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from bs4 import BeautifulSoup

from ..config import settings
from ..utils.logger import logger


class BrowserClient:
    """Headless browser client using Playwright for JavaScript rendering.

    Uses a singleton browser pattern with session-based persistence for agentic workflows.
    Sessions (context + page) persist across tool calls and are cleaned up via TTL.
    """

    # Class-level browser singleton (shared across all instances in the same process)
    _browser: Optional[Browser] = None
    _playwright: Optional[Playwright] = None
    _browser_lock = asyncio.Lock()

    # Session storage: {session_id: (context, page, last_used_timestamp)}
    _sessions: dict[str, tuple[BrowserContext, Page, float]] = {}
    _session_ttl = 1800  # 30 minutes

    def __init__(
        self,
        timeout: Optional[int] = None,
        page_load_delay: float = 0.5,  # Reduced from 1.0 for faster scraping
        scroll_delay: float = 0.5      # Reduced from 1.0 for faster scraping
    ):
        """Initialize the browser client.

        Args:
            timeout: Page load timeout in seconds. Defaults to settings browser_timeout
            page_load_delay: Delay after page load for JS to execute (default 0.5s)
            scroll_delay: Delay after scrolling for lazy-load content (default 0.5s)
        """
        self.timeout = (timeout or settings.browser_timeout) * 1000  # Convert to ms
        self.page_load_delay = page_load_delay
        self.scroll_delay = scroll_delay

    async def __aenter__(self):
        """Async context manager entry - ensures browser is running."""
        await self.ensure_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - does NOT close browser (singleton pattern)."""
        # Browser stays open; sessions are cleaned up by TTL or explicit kill_session
        pass

    async def ensure_browser(self) -> Browser:
        """Ensure browser is running (singleton pattern).

        Returns:
            Running Browser instance
        """
        async with BrowserClient._browser_lock:
            if BrowserClient._browser is None or not BrowserClient._browser.is_connected():
                logger.info("Starting singleton browser instance")
                BrowserClient._playwright = await async_playwright().start()
                BrowserClient._browser = await BrowserClient._playwright.chromium.launch(
                    headless=True
                )
        return BrowserClient._browser

    async def get_page(
        self, session_id: str, url: Optional[str] = None
    ) -> tuple[Page, BrowserContext]:
        """Get or create a persistent page for this session.

        Args:
            session_id: Unique identifier for this session
            url: Optional URL to navigate to (only used when creating new session)

        Returns:
            Tuple of (page, context) for the session
        """
        # Cleanup expired sessions periodically
        self._cleanup_expired_sessions()

        # Reuse existing session
        if session_id in BrowserClient._sessions:
            context, page, _ = BrowserClient._sessions[session_id]
            # Update timestamp
            BrowserClient._sessions[session_id] = (context, page, time.time())
            logger.debug(f"Reusing existing browser session: {session_id}")
            return page, context

        # Create new session
        logger.info(f"Creating new browser session: {session_id}")
        browser = await self.ensure_browser()

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

        BrowserClient._sessions[session_id] = (context, page, time.time())
        return page, context

    async def kill_session(self, session_id: str):
        """Close a specific session.

        Args:
            session_id: Session to close
        """
        if session_id in BrowserClient._sessions:
            context, page, _ = BrowserClient._sessions.pop(session_id)
            try:
                await page.close()
                await context.close()
                logger.info(f"Closed browser session: {session_id}")
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")

    def _cleanup_expired_sessions(self):
        """Remove sessions older than TTL."""
        now = time.time()
        expired = [
            sid for sid, (_, _, ts) in BrowserClient._sessions.items()
            if now - ts > self._session_ttl
        ]
        for sid in expired:
            logger.info(f"Session {sid} expired (TTL exceeded)")
            asyncio.create_task(self.kill_session(sid))

    @classmethod
    async def shutdown(cls):
        """Shutdown the singleton browser (for application shutdown)."""
        async with cls._browser_lock:
            # Close all sessions
            for sid in list(cls._sessions.keys()):
                context, page, _ = cls._sessions.pop(sid)
                try:
                    await page.close()
                    await context.close()
                except Exception:
                    pass

            # Close browser
            if cls._browser:
                await cls._browser.close()
                cls._browser = None

            # Stop playwright
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None

            logger.info("Browser singleton shutdown complete")

    async def _dismiss_modals(
        self,
        page: Page,
        timeout: int = 3,
        max_attempts: int = 3
    ) -> int:
        """Attempt to dismiss any modal popups on the page.

        Tries multiple strategies:
        1. Press Escape key
        2. Look for and click common close buttons
        3. Click on modal overlays
        4. Dismiss JavaScript dialogs

        Args:
            page: Playwright page instance
            timeout: Timeout in seconds for finding modals
            max_attempts: Maximum number of dismissal attempts

        Returns:
            Number of modals successfully dismissed
        """
        dismissed_count = 0

        # Strategy 1: Setup dialog handler for JavaScript alerts/confirms
        def handle_dialog(dialog):
            nonlocal dismissed_count
            try:
                dialog.dismiss()
                dismissed_count += 1
                logger.info(f"Dismissed JavaScript dialog: {dialog.type}")
            except Exception as e:
                logger.warning(f"Failed to dismiss dialog: {e}")

        page.on("dialog", handle_dialog)

        # Strategy 2: Press Escape key (works for many modals)
        try:
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.15)  # Reduced from 0.3
            logger.debug("Pressed Escape key")
        except Exception as e:
            logger.debug(f"Escape key press failed: {e}")

        # Strategy 3: Look for common close button selectors
        close_selectors = [
            # ARIA labels
            'button[aria-label*="close" i]',
            'button[aria-label*="dismiss" i]',
            '[aria-label="Close"]',

            # Common class patterns
            'button[class*="close" i]',
            'button.close',
            '.modal-close',
            'a.close',

            # Modal-specific patterns
            '[class*="modal"] button[class*="close"]',
            '[class*="popup"] button[class*="close"]',
            '[class*="dialog"] button[class*="close"]',

            # Data attributes
            'button[data-dismiss="modal"]',
            '[data-action="close"]',

            # Cookie consent specific
            'button[id*="accept" i]',
            'button[id*="consent" i]',
            '#onetrust-accept-btn-handler',
            '.cookie-accept',

            # Newsletter/subscription specific
            '[class*="newsletter"] button[class*="close"]',
            '[class*="subscribe"] button[class*="close"]',

            # SVG close icons
            'svg[class*="close"]',
            'button svg[aria-label="Close"]',
        ]

        for attempt in range(max_attempts):
            for selector in close_selectors:
                try:
                    # Use count() to check if element exists
                    elements = page.locator(selector)
                    count = await elements.count()

                    if count > 0:
                        # Click first visible element
                        await elements.first.click(timeout=timeout * 1000, force=True)
                        dismissed_count += 1
                        logger.info(f"Dismissed modal using selector: {selector}")
                        await asyncio.sleep(0.2)  # Reduced from 0.5
                        break  # Exit selector loop on success
                except Exception as e:
                    # Selector not found or click failed, continue
                    logger.debug(f"Selector '{selector}' attempt {attempt + 1} failed: {e}")
                    continue

            # Brief pause between attempts
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.2)  # Reduced from 0.5

        # Strategy 4: Click on modal overlays/backdrops
        overlay_selectors = [
            '.modal-backdrop',
            '.overlay',
            '[class*="backdrop"]',
            '[class*="overlay"]',
        ]

        for selector in overlay_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    await elements.first.click(timeout=1000)
                    dismissed_count += 1
                    logger.info(f"Clicked overlay: {selector}")
                    await asyncio.sleep(0.15)  # Reduced from 0.3
            except Exception as e:
                logger.debug(f"Overlay click failed for '{selector}': {e}")
                continue

        # Remove dialog listener
        page.remove_listener("dialog", handle_dialog)

        if dismissed_count > 0:
            logger.info(f"Successfully dismissed {dismissed_count} modal(s)")
        else:
            logger.debug("No modals detected or dismissed")

        return dismissed_count

    async def render_page(
        self, url: str, wait_for: str = "domcontentloaded", dismiss_modals: bool = True,
        session_id: Optional[str] = None
    ) -> tuple[str, Optional[str]]:
        """Render a page with full JavaScript execution.

        Args:
            url: URL to render
            wait_for: Wait condition - 'networkidle', 'load', or 'domcontentloaded'
            dismiss_modals: Whether to attempt dismissing modal popups
            session_id: Optional session ID for persistent browser context

        Returns:
            Tuple of (html_content, error_message)
            If successful, returns (html, None)
            If failed, returns ("", error_message)
        """
        try:
            # Use session-based page if session_id provided (agentic mode)
            if session_id:
                page, _ = await self.get_page(session_id, url)
            else:
                # Legacy mode: create temporary page
                browser = await self.ensure_browser()
                page = await browser.new_page()
                await page.goto(url, wait_until=wait_for, timeout=self.timeout)

            # Wait for any delayed JavaScript (configurable, default 0.5s)
            await asyncio.sleep(self.page_load_delay)

            # Dismiss modal popups before scrolling
            if dismiss_modals:
                try:
                    await self._dismiss_modals(page, timeout=2, max_attempts=2)
                except Exception as e:
                    logger.warning(f"Modal dismissal failed: {e}")
                    # Continue with scraping even if modal dismissal fails

            # Scroll through the page to trigger lazy-loaded content
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 200;  // Faster scroll: 200px instead of 100px
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 50);  // Faster interval: 50ms instead of 100ms
                    });
                }
            """)

            # Wait for any lazy-loaded content to render (configurable, default 0.5s)
            await asyncio.sleep(self.scroll_delay)

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")

            # Get full rendered HTML
            html = await page.content()

            # Only close page if not session-based
            if not session_id:
                await page.close()

            logger.info(f"Successfully rendered page: {url} ({len(html)} bytes)")
            return html, None

        except Exception as e:
            error_msg = f"Failed to render page {url}: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    @staticmethod
    def clean_html(html: str) -> str:
        """Clean HTML by removing scripts, styles, and keeping structure.

        Args:
            html: Raw HTML content

        Returns:
            Cleaned HTML with scripts and styles removed
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove script tags
            for script in soup.find_all('script'):
                script.decompose()

            # Remove style tags
            for style in soup.find_all('style'):
                style.decompose()

            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
                comment.extract()

            # Get cleaned HTML
            cleaned = str(soup)

            logger.debug(f"Cleaned HTML: {len(html)} -> {len(cleaned)} bytes")
            return cleaned

        except Exception as e:
            logger.warning(f"Failed to clean HTML: {e}. Returning original.")
            return html

    # --- Session-Based Methods for Agentic Interactions ---

    async def click_element(
        self,
        session_id: str,
        selector: str,
        wait_for: Optional[str] = None,
        timeout: int = 5000
    ) -> tuple[str, Optional[str]]:
        """Click an element on the page and return updated HTML.

        Args:
            session_id: Session identifier (must have active session from get_page)
            selector: CSS selector to click
            wait_for: Optional selector to wait for after click
            timeout: Timeout in milliseconds

        Returns:
            Tuple of (html_content, error_message)
        """
        try:
            page, _ = await self.get_page(session_id)
            await page.click(selector, timeout=timeout)

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=timeout)

            # Brief pause for updates
            await asyncio.sleep(0.3)

            html = await page.content()
            logger.info(f"Clicked element: {selector}")
            return html, None

        except Exception as e:
            error_msg = f"Failed to click {selector}: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    async def fill_input(
        self,
        session_id: str,
        selector: str,
        value: str,
        timeout: int = 5000
    ) -> tuple[str, Optional[str]]:
        """Fill an input field on the page.

        Args:
            session_id: Session identifier (must have active session from get_page)
            selector: CSS selector of the input
            value: Text to type
            timeout: Timeout in milliseconds

        Returns:
            Tuple of (html_content, error_message)
        """
        try:
            page, _ = await self.get_page(session_id)
            await page.fill(selector, value, timeout=timeout)

            html = await page.content()
            logger.info(f"Filled input {selector} with value")
            return html, None

        except Exception as e:
            error_msg = f"Failed to fill {selector}: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    async def scroll_page(
        self,
        session_id: str,
        direction: str = "bottom",
        timeout: int = 5000
    ) -> tuple[str, Optional[str]]:
        """Scroll the page to load lazy content.

        Args:
            session_id: Session identifier (must have active session from get_page)
            direction: "top" or "bottom"
            timeout: Timeout in milliseconds (unused but kept for consistency)

        Returns:
            Tuple of (html_content, error_message)
        """
        try:
            page, _ = await self.get_page(session_id)

            if direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            else:
                await page.evaluate("window.scrollBy(0, 500)")  # Default scroll down

            # Wait for lazy-loaded content
            await asyncio.sleep(0.5)

            html = await page.content()
            logger.info(f"Scrolled page to {direction}")
            return html, None

        except Exception as e:
            error_msg = f"Failed to scroll: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    async def close_context(self, context_id: str):
        """Close a persistent browser context (alias for kill_session).

        Args:
            context_id: Browser context/session identifier to close
        """
        await self.kill_session(context_id)


async def render_page(url: str) -> tuple[str, Optional[str]]:
    """Convenience function to render a single page (non-session mode).

    Args:
        url: URL to render

    Returns:
        Tuple of (html_content, error_message)
    """
    client = BrowserClient()
    html, error = await client.render_page(url)
    if error:
        return html, error
    return client.clean_html(html), None
