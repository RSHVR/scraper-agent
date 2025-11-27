"""Browser client service for rendering JavaScript-heavy pages."""
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup

from ..config import settings
from ..utils.logger import logger


class BrowserClient:
    """Headless browser client using Playwright for JavaScript rendering."""

    def __init__(self, timeout: Optional[int] = None):
        """Initialize the browser client.

        Args:
            timeout: Page load timeout in seconds. Defaults to settings browser_timeout
        """
        self.timeout = (timeout or settings.browser_timeout) * 1000  # Convert to ms
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.playwright = await async_playwright().start()
        self._browser = await self.playwright.chromium.launch(headless=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._browser:
            await self._browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

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
            await asyncio.sleep(0.3)
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
                        await asyncio.sleep(0.5)
                        break  # Exit selector loop on success
                except Exception as e:
                    # Selector not found or click failed, continue
                    logger.debug(f"Selector '{selector}' attempt {attempt + 1} failed: {e}")
                    continue

            # Brief pause between attempts
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5)

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
                    await asyncio.sleep(0.3)
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
        self, url: str, wait_for: str = "networkidle", dismiss_modals: bool = True
    ) -> tuple[str, Optional[str]]:
        """Render a page with full JavaScript execution.

        Args:
            url: URL to render
            wait_for: Wait condition - 'networkidle', 'load', or 'domcontentloaded'
            dismiss_modals: Whether to attempt dismissing modal popups

        Returns:
            Tuple of (html_content, error_message)
            If successful, returns (html, None)
            If failed, returns ("", error_message)
        """
        if not self._browser:
            return "", "Browser not initialized. Use as async context manager."

        try:
            page = await self._browser.new_page()

            # Navigate to URL
            await page.goto(url, wait_until=wait_for, timeout=self.timeout)

            # Wait a bit for any delayed JavaScript
            await asyncio.sleep(1)

            # Dismiss modal popups before scrolling
            if dismiss_modals:
                try:
                    await self._dismiss_modals(page, timeout=3, max_attempts=3)
                except Exception as e:
                    logger.warning(f"Modal dismissal failed: {e}")
                    # Continue with scraping even if modal dismissal fails

            # Scroll through the page to trigger lazy-loaded content
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)

            # Wait for any lazy-loaded content to render
            await asyncio.sleep(1)

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")

            # Get full rendered HTML
            html = await page.content()

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


async def render_page(url: str) -> tuple[str, Optional[str]]:
    """Convenience function to render a single page.

    Args:
        url: URL to render

    Returns:
        Tuple of (html_content, error_message)
    """
    async with BrowserClient() as client:
        html, error = await client.render_page(url)
        if error:
            return html, error
        return client.clean_html(html), None
