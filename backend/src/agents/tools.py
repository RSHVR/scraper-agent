"""LangChain @tool decorated functions wrapping existing services."""

from langchain_core.tools import tool
from typing import Optional, List
import json


class ToolContext:
    """Shared state for tools within a session."""

    def __init__(self, session_id: str):
        from ..services.http_client import HTTPClient
        from ..services.browser_client import BrowserClient
        from ..services.html_cleaner import HTMLCleaner
        from ..services.sitemap_discovery import SitemapDiscovery
        from ..services.storage_service import StorageService

        self.session_id = session_id
        self.http = HTTPClient()
        self.browser = BrowserClient()
        self.cleaner = HTMLCleaner()
        self.sitemap = SitemapDiscovery()
        self.storage = StorageService()

        # Page state
        self.current_html: Optional[str] = None
        self.current_url: Optional[str] = None
        self.browser_context_id: Optional[str] = None


# Global context (set per-session)
_ctx: Optional[ToolContext] = None


def set_tool_context(ctx: ToolContext):
    """Set the global tool context for this session."""
    global _ctx
    _ctx = ctx


def get_tool_context() -> ToolContext:
    """Get the current tool context."""
    if _ctx is None:
        raise RuntimeError("Tool context not set. Call set_tool_context first.")
    return _ctx


def get_tools() -> list:
    """Return all scraper tools."""
    return [
        web_search,  # Discover sites first
        analyze_url,
        fetch_page,
        render_with_browser,
        click_element,
        fill_input,
        scroll_page,
        extract_content,
        convert_to_markdown,
        extract_contact_info,
        extract_structured_data,
        discover_urls,
        save_result,
        report_failure
    ]


# Terminal tool names for agent loop
TERMINAL_TOOLS = {"save_result", "report_failure"}


# --- Tool Definitions ---

@tool
def web_search(query: str, max_results: int = 10) -> str:
    """Search the web using DuckDuckGo. Use this to find websites, businesses, or information when you don't already have URLs. Essential for discovery tasks like 'find gyms in Toronto'."""
    from ddgs import DDGS

    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))

        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:200]
            })

        return json.dumps({
            "success": True,
            "query": query,
            "results": formatted,
            "count": len(formatted)
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Search failed: {str(e)}"
        })


@tool
async def analyze_url(url: str) -> str:
    """Analyze a URL to determine site type (static/JS-heavy) and recommend scraping strategy. Always call this FIRST."""
    ctx = get_tool_context()

    async with ctx.http:
        html, error = await ctx.http.fetch_url(url)

    if error:
        return json.dumps({
            "url": url,
            "accessible": False,
            "error": error,
            "recommendation": "Check URL validity or try render_with_browser"
        })

    html_lower = html.lower()
    analysis = {
        "url": url,
        "accessible": True,
        "content_length": len(html),
        "has_javascript_framework": any(x in html_lower for x in [
            "react", "vue", "angular", "__next", "gatsby", "nuxt",
            "data-reactroot", "ng-app", "_app"
        ]),
        "has_lazy_loading": 'loading="lazy"' in html or "data-src" in html,
        "has_infinite_scroll": "infinite" in html_lower or "load-more" in html_lower,
        "has_pagination": any(x in html_lower for x in ["page=", "pagination", "next page"]),
    }

    if analysis["has_javascript_framework"]:
        analysis["recommendation"] = "Use render_with_browser - JavaScript framework detected"
    elif analysis["has_lazy_loading"]:
        analysis["recommendation"] = "Use render_with_browser with scroll=true for lazy content"
    else:
        analysis["recommendation"] = "fetch_page should work for this static site"

    return json.dumps(analysis)


@tool
async def fetch_page(url: str) -> str:
    """Fetch page via HTTP (fast, for static sites without JavaScript)."""
    ctx = get_tool_context()

    async with ctx.http:
        html, error = await ctx.http.fetch_url(url)

    if error:
        return json.dumps({"success": False, "error": error})

    ctx.current_html = html
    ctx.current_url = url
    preview = html[:30000] if len(html) > 30000 else html

    return json.dumps({
        "success": True,
        "url": url,
        "content_length": len(html),
        "html_preview": preview[:5000],  # Limit preview for LLM context
        "truncated": len(html) > 30000
    })


@tool
async def render_with_browser(
    url: str,
    wait_for_selector: Optional[str] = None,
    scroll: bool = False
) -> str:
    """Render page with headless browser (slower, handles JavaScript). Use for React/Vue/Angular sites. Browser persists for subsequent actions like click_element and scroll_page."""
    import asyncio
    ctx = get_tool_context()

    # Mark context as active for subsequent browser actions
    ctx.browser_context_id = ctx.session_id

    try:
        # Get persistent page for this session (navigates to URL)
        page, _ = await ctx.browser.get_page(ctx.session_id, url)

        # Wait for optional selector
        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=5000)
            except Exception:
                pass  # Continue even if selector not found

        # Optional scroll for lazy content
        if scroll:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

        html = await page.content()
        ctx.current_html = html
        ctx.current_url = url

        preview = html[:30000] if len(html) > 30000 else html

        return json.dumps({
            "success": True,
            "url": url,
            "content_length": len(html),
            "html_preview": preview[:5000],  # Limit preview for LLM context
            "truncated": len(html) > 30000,
            "browser_context_active": True
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def click_element(selector: str, wait_for_selector: Optional[str] = None) -> str:
    """Click an element on the current page. Requires active browser context from render_with_browser."""
    ctx = get_tool_context()

    if not ctx.browser_context_id:
        return json.dumps({
            "success": False,
            "error": "No browser context. Call render_with_browser first."
        })

    # Use existing session (page stays open from render_with_browser)
    html, error = await ctx.browser.click_element(
        ctx.session_id, selector, wait_for_selector
    )

    if error:
        return json.dumps({"success": False, "error": error})

    ctx.current_html = html
    return json.dumps({
        "success": True,
        "clicked": selector,
        "content_length": len(html)
    })


@tool
async def fill_input(selector: str, value: str) -> str:
    """Type text into an input field on the current page. Requires active browser context."""
    ctx = get_tool_context()

    if not ctx.browser_context_id:
        return json.dumps({
            "success": False,
            "error": "No browser context. Call render_with_browser first."
        })

    # Use existing session (page stays open from render_with_browser)
    html, error = await ctx.browser.fill_input(
        ctx.session_id, selector, value
    )

    if error:
        return json.dumps({"success": False, "error": error})

    ctx.current_html = html
    return json.dumps({
        "success": True,
        "filled": selector,
        "value": value
    })


@tool
async def scroll_page(direction: str = "bottom") -> str:
    """Scroll the current page to load lazy content. Direction: 'top' or 'bottom'."""
    ctx = get_tool_context()

    if not ctx.browser_context_id:
        return json.dumps({
            "success": False,
            "error": "No browser context. Call render_with_browser first."
        })

    # Use existing session (page stays open from render_with_browser)
    html, error = await ctx.browser.scroll_page(
        ctx.session_id, direction
    )

    if error:
        return json.dumps({"success": False, "error": error})

    ctx.current_html = html
    return json.dumps({
        "success": True,
        "scrolled": direction,
        "content_length": len(html)
    })


@tool
def extract_content(target: str) -> str:
    """Extract content from current page HTML using trafilatura for robust extraction.

    Target options:
    - 'main_content': Extract main article/body content (uses trafilatura)
    - 'links': Extract all links from the page
    - 'headings': Extract all headings (h1-h6)
    - CSS selector (e.g., '.product-price'): Extract specific elements
    """
    ctx = get_tool_context()

    if not ctx.current_html:
        return json.dumps({
            "success": False,
            "error": "No page loaded. Call fetch_page or render_with_browser first."
        })

    try:
        if target == "main_content":
            # Use trafilatura for robust main content extraction
            from ..services.trafilatura_service import TrafilaturaService
            service = TrafilaturaService()
            result = service.extract_with_fallback(ctx.current_html, ctx.current_url)

            if result.error:
                return json.dumps({
                    "success": False,
                    "error": result.error
                })

            # Return both text and markdown, plus metadata
            text_content = result.text or ""
            markdown_content = result.markdown or ""

            return json.dumps({
                "success": True,
                "target": target,
                "title": result.title,
                "text": text_content[:30000] if text_content else None,
                "markdown": markdown_content[:30000] if markdown_content else None,
                "author": result.author,
                "date": result.date,
                "text_length": len(text_content),
                "truncated": len(text_content) > 30000
            })

        elif target == "links":
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(ctx.current_html, 'html.parser')
            links = [{"href": a.get("href"), "text": a.get_text(strip=True)[:100]}
                     for a in soup.find_all("a", href=True)]
            return json.dumps({
                "success": True,
                "target": target,
                "extracted": links[:100],  # Limit number of links
                "count": len(links)
            })

        elif target == "headings":
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(ctx.current_html, 'html.parser')
            headings = []
            for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                for h in soup.find_all(tag):
                    headings.append({"level": tag, "text": h.get_text(strip=True)[:200]})
            return json.dumps({
                "success": True,
                "target": target,
                "extracted": headings,
                "count": len(headings)
            })

        else:
            # CSS selector
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(ctx.current_html, 'html.parser')
            elements = soup.select(target)
            content = [el.get_text(strip=True)[:500] for el in elements]
            return json.dumps({
                "success": True,
                "target": target,
                "extracted": content[:50],  # Limit results
                "count": len(elements)
            })

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Extraction failed: {str(e)}"
        })


@tool
def convert_to_markdown(include_links: bool = True, include_images: bool = False) -> str:
    """Convert current page HTML to clean markdown using trafilatura."""
    ctx = get_tool_context()

    if not ctx.current_html:
        return json.dumps({
            "success": False,
            "error": "No page loaded. Call fetch_page or render_with_browser first."
        })

    try:
        # Use trafilatura for robust markdown conversion
        from ..services.trafilatura_service import TrafilaturaService
        service = TrafilaturaService()
        result = service.extract_with_fallback(ctx.current_html, ctx.current_url)

        if result.error:
            return json.dumps({
                "success": False,
                "error": result.error
            })

        markdown = result.markdown or result.text or ""

        return json.dumps({
            "success": True,
            "markdown": markdown[:15000],  # Limit for LLM context
            "title": result.title,
            "char_count": len(markdown),
            "truncated": len(markdown) > 15000
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Conversion failed: {str(e)}"
        })


@tool
def extract_contact_info(html: Optional[str] = None) -> str:
    """Extract contact information (phones, emails, addresses) from current page or provided HTML.

    This tool uses regex patterns and JSON-LD parsing to find:
    - Phone numbers (various formats)
    - Email addresses
    - Physical addresses (from structured data)

    Args:
        html: Optional HTML string. If not provided, uses current page HTML.
    """
    import re
    from bs4 import BeautifulSoup

    ctx = get_tool_context()

    # Use provided HTML or current page
    target_html = html if html else ctx.current_html

    if not target_html:
        return json.dumps({
            "success": False,
            "error": "No HTML provided and no page loaded. Call fetch_page or render_with_browser first."
        })

    try:
        soup = BeautifulSoup(target_html, 'lxml')
        text = soup.get_text(separator=' ', strip=True)

        contacts = {
            "phones": [],
            "emails": [],
            "addresses": []
        }

        # Phone patterns - various North American and international formats
        phone_patterns = [
            r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # (123) 456-7890, 123-456-7890
            r'\([0-9]{3}\)\s*[0-9]{3}[-.\s]?[0-9]{4}',  # (123) 456-7890
            r'\+[0-9]{1,3}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}',  # International
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            contacts["phones"].extend(matches)
        # Deduplicate and clean
        contacts["phones"] = list(set(
            phone.strip() for phone in contacts["phones"]
            if len(re.sub(r'\D', '', phone)) >= 10  # At least 10 digits
        ))[:10]

        # Email patterns
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        contacts["emails"] = list(set(re.findall(email_pattern, text)))[:10]

        # Also check href="mailto:" links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0]
                if email and email not in contacts["emails"]:
                    contacts["emails"].append(email)

        # Also check href="tel:" links for phones
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href.startswith('tel:'):
                phone = href.replace('tel:', '').strip()
                if phone and phone not in contacts["phones"]:
                    contacts["phones"].append(phone)

        # Extract addresses from JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json as json_module
                data = json_module.loads(script.string)

                # Handle both single objects and arrays
                items = data if isinstance(data, list) else [data]

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    # Look for address in various locations
                    address = item.get('address') or item.get('location', {}).get('address')

                    if isinstance(address, dict):
                        parts = []
                        if address.get('streetAddress'):
                            parts.append(address['streetAddress'])
                        if address.get('addressLocality'):
                            parts.append(address['addressLocality'])
                        if address.get('addressRegion'):
                            parts.append(address['addressRegion'])
                        if address.get('postalCode'):
                            parts.append(address['postalCode'])
                        if parts:
                            addr_str = ', '.join(parts)
                            if addr_str not in contacts["addresses"]:
                                contacts["addresses"].append(addr_str)

                    elif isinstance(address, str) and address:
                        if address not in contacts["addresses"]:
                            contacts["addresses"].append(address)

                    # Also check for telephone in JSON-LD
                    phone = item.get('telephone')
                    if phone and phone not in contacts["phones"]:
                        contacts["phones"].append(phone)

                    # Check for email in JSON-LD
                    email = item.get('email')
                    if email and email not in contacts["emails"]:
                        contacts["emails"].append(email)

            except Exception:
                pass  # Skip invalid JSON-LD

        return json.dumps({
            "success": True,
            "contacts": contacts,
            "phone_count": len(contacts["phones"]),
            "email_count": len(contacts["emails"]),
            "address_count": len(contacts["addresses"])
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Contact extraction failed: {str(e)}"
        })


@tool
def extract_structured_data(html: Optional[str] = None) -> str:
    """Extract JSON-LD, schema.org, and OpenGraph data from current page or provided HTML.

    Structured data contains rich information that websites provide for search engines:
    - JSON-LD: Schema.org data (business info, products, articles, etc.)
    - OpenGraph: Social media metadata (title, description, images)
    - Twitter Cards: Twitter-specific metadata

    Args:
        html: Optional HTML string. If not provided, uses current page HTML.
    """
    import re
    from bs4 import BeautifulSoup

    ctx = get_tool_context()

    # Use provided HTML or current page
    target_html = html if html else ctx.current_html

    if not target_html:
        return json.dumps({
            "success": False,
            "error": "No HTML provided and no page loaded. Call fetch_page or render_with_browser first."
        })

    try:
        soup = BeautifulSoup(target_html, 'lxml')
        structured_data = []

        # Extract JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json as json_module
                data = json_module.loads(script.string)
                structured_data.append({
                    "type": "json-ld",
                    "data": data
                })
            except Exception:
                pass  # Skip invalid JSON

        # Extract OpenGraph metadata
        og_data = {}
        for meta in soup.find_all('meta', property=re.compile(r'^og:')):
            prop = meta.get('property', '').replace('og:', '')
            content = meta.get('content', '')
            if prop and content:
                og_data[prop] = content
        if og_data:
            structured_data.append({
                "type": "opengraph",
                "data": og_data
            })

        # Extract Twitter Card metadata
        twitter_data = {}
        for meta in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')}):
            name = meta.get('name', '').replace('twitter:', '')
            content = meta.get('content', '')
            if name and content:
                twitter_data[name] = content
        if twitter_data:
            structured_data.append({
                "type": "twitter_card",
                "data": twitter_data
            })

        # Extract standard meta tags
        meta_data = {}
        for meta in soup.find_all('meta', attrs={'name': True, 'content': True}):
            name = meta.get('name', '')
            content = meta.get('content', '')
            if name and content and not name.startswith(('twitter:', 'og:')):
                meta_data[name] = content
        if meta_data:
            structured_data.append({
                "type": "meta_tags",
                "data": meta_data
            })

        if structured_data:
            return json.dumps({
                "success": True,
                "structured_data": structured_data,
                "count": len(structured_data)
            }, indent=2)
        else:
            return json.dumps({
                "success": True,
                "message": "No structured data found on this page",
                "structured_data": [],
                "count": 0
            })

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Structured data extraction failed: {str(e)}"
        })


@tool
async def discover_urls(base_url: str, method: str = "both", max_urls: int = 100) -> str:
    """Discover all URLs on a site via sitemap or crawling. Method: 'sitemap', 'crawl', or 'both'."""
    ctx = get_tool_context()

    try:
        urls = []

        if method in ("sitemap", "both"):
            sitemap_urls = await ctx.sitemap.discover_from_robots(base_url)
            urls.extend(sitemap_urls)

        if method in ("crawl", "both") and len(urls) < max_urls:
            crawl_urls = await ctx.sitemap.discover_from_html(
                base_url, max_urls=max_urls - len(urls)
            )
            urls.extend(crawl_urls)

        # Deduplicate and limit
        urls = list(dict.fromkeys(urls))[:max_urls]

        return json.dumps({
            "success": True,
            "urls": urls,
            "count": len(urls),
            "method": method
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"URL discovery failed: {str(e)}"
        })


@tool
def save_result(data: str) -> str:
    """Save extracted content to storage. Call when goal is achieved. This is a TERMINAL action - agent loop will end.

    Input should be a JSON string with these fields:
    - content: The extracted content to save (required)
    - url: Source URL (required)
    - title: A title for the saved content (optional, defaults to 'result')
    - embed: Whether to embed for vector search (optional, defaults to false)

    Example: {"content": "The extracted text...", "url": "https://example.com", "title": "My Results"}
    """
    ctx = get_tool_context()

    try:
        # Parse JSON input
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                # If not JSON, treat as plain content
                parsed = {"content": data, "url": ctx.current_url or "unknown", "title": "result"}
        else:
            parsed = data

        content = parsed.get("content", str(parsed))
        url = parsed.get("url", ctx.current_url or "unknown")
        title = parsed.get("title", "result")

        ctx.storage.save_markdown(
            ctx.session_id,
            [{"page_url": url, "page_name": title, "markdown_content": content}]
        )

        return json.dumps({
            "success": True,
            "saved": True,
            "session_id": ctx.session_id,
            "terminal": True
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Save failed: {str(e)}",
            "terminal": False
        })


@tool
def report_failure(data: str) -> str:
    """Report that the goal cannot be achieved after trying multiple approaches. This is a TERMINAL action - agent loop will end.

    Input should be a JSON string with these fields:
    - reason: Why the goal could not be achieved (required)
    - attempted_approaches: List of approaches that were tried (optional)
    - suggestion: What else could be tried (optional)

    Example: {"reason": "Site requires login", "attempted_approaches": ["fetch_page", "render_with_browser"], "suggestion": "Provide login credentials"}
    """
    try:
        # Parse JSON input
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                # If not JSON, treat as reason text
                parsed = {"reason": data}
        else:
            parsed = data

        return json.dumps({
            "status": "failed",
            "reason": parsed.get("reason", str(parsed)),
            "attempted": parsed.get("attempted_approaches", []),
            "suggestion": parsed.get("suggestion", ""),
            "terminal": True
        })
    except Exception as e:
        return json.dumps({
            "status": "failed",
            "reason": f"Error parsing failure report: {str(e)}",
            "attempted": [],
            "suggestion": "",
            "terminal": True
        })
