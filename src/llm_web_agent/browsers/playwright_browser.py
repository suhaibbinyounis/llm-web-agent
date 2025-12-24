"""
Playwright Browser - Implementation of IBrowser using Playwright.

This module provides a Playwright-based implementation of the browser interface.
"""

from typing import Any, Dict, List, Optional, Union
import logging

from llm_web_agent.interfaces.browser import (
    IBrowser,
    IBrowserContext,
    IPage,
    IElement,
    ElementHandle,
    BrowserType,
)
from llm_web_agent.exceptions.browser import (
    BrowserLaunchError,
    BrowserConnectionError,
    NavigationError,
    ElementNotFoundError,
)

logger = logging.getLogger(__name__)


class PlaywrightElement(IElement):
    """
    Playwright implementation of IElement.
    
    Wraps a Playwright ElementHandle for interaction and inspection.
    """
    
    def __init__(self, element: Any, selector: str):
        """
        Initialize the element wrapper.
        
        Args:
            element: Playwright ElementHandle or Locator
            selector: The selector used to find this element
        """
        self._element = element
        self._selector = selector
    
    async def click(self, **options: Any) -> None:
        """Click on this element."""
        await self._element.click(**options)
    
    async def fill(self, value: str, **options: Any) -> None:
        """Fill this element with text."""
        await self._element.fill(value, **options)
    
    async def select_option(self, value: Union[str, List[str]], **options: Any) -> List[str]:
        """Select option(s) in a <select> element."""
        result = await self._element.select_option(value, **options)
        return result if isinstance(result, list) else [result]
    
    async def get_attribute(self, name: str) -> Optional[str]:
        """Get an attribute value."""
        return await self._element.get_attribute(name)
    
    async def text_content(self) -> Optional[str]:
        """Get text content."""
        return await self._element.text_content()
    
    async def inner_html(self) -> str:
        """Get inner HTML."""
        return await self._element.inner_html()
    
    async def is_visible(self) -> bool:
        """Check if visible."""
        return await self._element.is_visible()
    
    async def is_enabled(self) -> bool:
        """Check if enabled."""
        return await self._element.is_enabled()
    
    async def hover(self, **options: Any) -> None:
        """Hover over element."""
        await self._element.hover(**options)
    
    async def scroll_into_view(self) -> None:
        """Scroll into view."""
        await self._element.scroll_into_view_if_needed()
    
    async def to_handle(self) -> ElementHandle:
        """Convert to ElementHandle."""
        tag_name = await self._element.evaluate("el => el.tagName.toLowerCase()")
        text_content = await self.text_content() or ""
        
        # Get attributes
        attributes = await self._element.evaluate(
            """el => {
                const attrs = {};
                for (const attr of el.attributes) {
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }"""
        )
        
        # Get bounding box
        bounding_box = await self._element.bounding_box()
        
        return ElementHandle(
            selector=self._selector,
            tag_name=tag_name,
            attributes=attributes,
            text_content=text_content[:500],  # Limit for memory
            is_visible=await self.is_visible(),
            is_enabled=await self.is_enabled(),
            bounding_box=bounding_box,
        )


class PlaywrightPage(IPage):
    """
    Playwright implementation of IPage.
    
    Wraps a Playwright Page for navigation and interaction.
    """
    
    def __init__(self, page: Any):
        """
        Initialize the page wrapper.
        
        Args:
            page: Playwright Page object
        """
        self._page = page
    
    @property
    def url(self) -> str:
        """Get current URL."""
        return self._page.url
    
    @property
    def title(self) -> str:
        """Get page title."""
        # Note: This is sync in Playwright, but we'll wrap it
        return self._page.title()
    
    async def goto(self, url: str, **options: Any) -> None:
        """Navigate to URL."""
        try:
            await self._page.goto(url, **options)
        except Exception as e:
            raise NavigationError(f"Failed to navigate to {url}: {e}", url=url)
    
    async def reload(self, **options: Any) -> None:
        """Reload page."""
        await self._page.reload(**options)
    
    async def go_back(self, **options: Any) -> None:
        """Go back."""
        await self._page.go_back(**options)
    
    async def go_forward(self, **options: Any) -> None:
        """Go forward."""
        await self._page.go_forward(**options)
    
    async def query_selector(self, selector: str) -> Optional[IElement]:
        """Find first matching element."""
        element = await self._page.query_selector(selector)
        if element:
            return PlaywrightElement(element, selector)
        return None
    
    async def query_selector_all(self, selector: str) -> List[IElement]:
        """Find all matching elements."""
        elements = await self._page.query_selector_all(selector)
        return [PlaywrightElement(el, selector) for el in elements]
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible",
    ) -> Optional[IElement]:
        """Wait for element."""
        try:
            element = await self._page.wait_for_selector(
                selector,
                timeout=timeout,
                state=state,
            )
            if element:
                return PlaywrightElement(element, selector)
            return None
        except Exception:
            return None
    
    async def click(self, selector: str, **options: Any) -> None:
        """Click element."""
        try:
            await self._page.click(selector, **options)
        except Exception as e:
            raise ElementNotFoundError(f"Could not click: {e}", selector=selector)
    
    async def fill(self, selector: str, value: str, **options: Any) -> None:
        """Fill input."""
        try:
            await self._page.fill(selector, value, **options)
        except Exception as e:
            raise ElementNotFoundError(f"Could not fill: {e}", selector=selector)
    
    async def select_option(
        self,
        selector: str,
        value: Union[str, List[str]],
        **options: Any,
    ) -> List[str]:
        """Select option."""
        result = await self._page.select_option(selector, value, **options)
        return result if isinstance(result, list) else [result]
    
    async def type(self, selector: str, text: str, delay: int = 0, **options: Any) -> None:
        """Type text."""
        await self._page.type(selector, text, delay=delay, **options)
    
    async def press(self, selector: str, key: str, **options: Any) -> None:
        """Press key."""
        await self._page.press(selector, key, **options)
    
    async def hover(self, selector: str, **options: Any) -> None:
        """Hover over element."""
        await self._page.hover(selector, **options)
    
    async def content(self) -> str:
        """Get page HTML."""
        return await self._page.content()
    
    async def text_content(self, selector: str) -> Optional[str]:
        """Get element text."""
        return await self._page.text_content(selector)
    
    async def get_attribute(self, selector: str, name: str) -> Optional[str]:
        """Get element attribute."""
        return await self._page.get_attribute(selector, name)
    
    async def evaluate(self, expression: str, *args: Any) -> Any:
        """Execute JavaScript."""
        return await self._page.evaluate(expression, *args)
    
    async def screenshot(
        self,
        path: Optional[Any] = None,
        full_page: bool = False,
        **options: Any,
    ) -> bytes:
        """Take screenshot."""
        return await self._page.screenshot(path=path, full_page=full_page, **options)
    
    async def wait_for_load_state(self, state: str = "load", timeout: Optional[int] = None) -> None:
        """Wait for load state."""
        await self._page.wait_for_load_state(state, timeout=timeout)
    
    async def wait_for_navigation(self, **options: Any) -> None:
        """Wait for navigation."""
        await self._page.wait_for_navigation(**options)
    
    async def wait_for_timeout(self, timeout: int) -> None:
        """Wait for timeout."""
        await self._page.wait_for_timeout(timeout)
    
    async def close(self) -> None:
        """Close page."""
        await self._page.close()


class PlaywrightContext(IBrowserContext):
    """
    Playwright implementation of IBrowserContext.
    """
    
    def __init__(self, context: Any):
        self._context = context
    
    async def new_page(self, **options: Any) -> IPage:
        """Create new page."""
        page = await self._context.new_page()
        return PlaywrightPage(page)
    
    async def cookies(self) -> List[Dict[str, Any]]:
        """Get cookies."""
        return await self._context.cookies()
    
    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """Add cookies."""
        await self._context.add_cookies(cookies)
    
    async def clear_cookies(self) -> None:
        """Clear cookies."""
        await self._context.clear_cookies()
    
    async def close(self) -> None:
        """Close context."""
        await self._context.close()


class PlaywrightBrowser(IBrowser):
    """
    Playwright implementation of IBrowser.
    
    This is the primary browser implementation using Playwright's
    async API for fast and reliable browser automation.
    
    Example:
        >>> browser = PlaywrightBrowser()
        >>> await browser.launch(headless=True)
        >>> page = await browser.new_page()
        >>> await page.goto("https://example.com")
        >>> await browser.close()
    """
    
    def __init__(self):
        """Initialize the browser (not launched yet)."""
        self._playwright: Any = None
        self._browser: Any = None
        self._default_context: Any = None
    
    @property
    def is_connected(self) -> bool:
        """Check if browser is connected."""
        return self._browser is not None and self._browser.is_connected()
    
    async def launch(
        self,
        headless: bool = True,
        browser_type: BrowserType = BrowserType.CHROMIUM,
        **options: Any,
    ) -> None:
        """
        Launch the browser.
        
        Args:
            headless: Whether to run headless
            browser_type: Type of browser to launch
            **options: Additional Playwright launch options
        """
        try:
            from playwright.async_api import async_playwright
            
            self._playwright = await async_playwright().start()
            
            # Get browser type
            browser_launchers = {
                BrowserType.CHROMIUM: self._playwright.chromium,
                BrowserType.FIREFOX: self._playwright.firefox,
                BrowserType.WEBKIT: self._playwright.webkit,
            }
            launcher = browser_launchers.get(browser_type, self._playwright.chromium)
            
            # Launch browser
            self._browser = await launcher.launch(
                headless=headless,
                **options,
            )
            
            logger.info(f"Launched {browser_type.value} browser (headless={headless})")
            
        except Exception as e:
            raise BrowserLaunchError(f"Failed to launch browser: {e}")
    
    async def new_page(self, **options: Any) -> IPage:
        """
        Create a new page.
        
        Args:
            **options: Page options (viewport, etc.)
            
        Returns:
            New page instance
        """
        if not self._browser:
            raise BrowserConnectionError("Browser not launched. Call launch() first.")
        
        # Create default context if not exists
        if not self._default_context:
            self._default_context = await self._browser.new_context(**options)
        
        page = await self._default_context.new_page()
        return PlaywrightPage(page)
    
    async def new_context(self, **options: Any) -> IBrowserContext:
        """
        Create a new browser context.
        
        Args:
            **options: Context options
            
        Returns:
            New context instance
        """
        if not self._browser:
            raise BrowserConnectionError("Browser not launched. Call launch() first.")
        
        context = await self._browser.new_context(**options)
        return PlaywrightContext(context)
    
    async def close(self) -> None:
        """Close the browser and cleanup."""
        if self._default_context:
            await self._default_context.close()
            self._default_context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.info("Browser closed")
