"""
Playwright Browser Adapter.

Implements the browser interfaces using Playwright.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from llm_web_agent.interfaces.browser import (
    IBrowser,
    IBrowserContext,
    IElement,
    IPage,
    BrowserType,
    ElementHandle,
)

logger = logging.getLogger(__name__)


class PlaywrightElement(IElement):
    """Playwright element wrapper."""
    
    def __init__(self, element, page):
        self._element = element
        self._page = page
    
    async def click(self, **options: Any) -> None:
        await self._element.click(**options)
    
    async def fill(self, value: str, **options: Any) -> None:
        await self._element.fill(value, **options)
    
    async def select_option(self, value: Union[str, List[str]], **options: Any) -> List[str]:
        return await self._element.select_option(value, **options)
    
    async def get_attribute(self, name: str) -> Optional[str]:
        return await self._element.get_attribute(name)
    
    async def text_content(self) -> Optional[str]:
        return await self._element.text_content()
    
    async def inner_html(self) -> str:
        return await self._element.inner_html()
    
    async def is_visible(self) -> bool:
        return await self._element.is_visible()
    
    async def is_enabled(self) -> bool:
        return await self._element.is_enabled()
    
    async def hover(self, **options: Any) -> None:
        await self._element.hover(**options)
    
    async def scroll_into_view(self) -> None:
        await self._element.scroll_into_view_if_needed()
    
    async def wait_for(self, state: str = "visible", timeout: int = 30000) -> None:
        """Wait for element to reach a state."""
        await self._element.wait_for(state=state, timeout=timeout)
    
    async def to_handle(self) -> ElementHandle:
        tag = await self._element.evaluate("el => el.tagName.toLowerCase()")
        attrs = await self._element.evaluate("""el => {
            const attrs = {};
            for (const attr of el.attributes) {
                attrs[attr.name] = attr.value;
            }
            return attrs;
        }""")
        text = await self._element.text_content() or ""
        visible = await self._element.is_visible()
        enabled = await self._element.is_enabled()
        
        return ElementHandle(
            selector="",
            tag_name=tag,
            attributes=attrs,
            text_content=text.strip(),
            is_visible=visible,
            is_enabled=enabled,
        )


class PlaywrightPage(IPage):
    """Playwright page wrapper."""
    
    def __init__(self, page):
        self._page = page
        self._keyboard = page.keyboard
    
    @property
    def url(self) -> str:
        return self._page.url
    
    @property
    def title(self) -> str:
        # Note: This is sync, but Playwright's title() is async
        # We'll need to handle this differently
        return ""  # Use async title() method instead
    
    async def title(self) -> str:
        return await self._page.title()
    
    @property
    def keyboard(self):
        return self._keyboard
    
    async def goto(self, url: str, **options: Any) -> None:
        await self._page.goto(url, **options)
    
    async def reload(self, **options: Any) -> None:
        await self._page.reload(**options)
    
    async def go_back(self, **options: Any) -> None:
        await self._page.go_back(**options)
    
    async def go_forward(self, **options: Any) -> None:
        await self._page.go_forward(**options)
    
    async def query_selector(self, selector: str) -> Optional[PlaywrightElement]:
        element = await self._page.query_selector(selector)
        if element:
            return PlaywrightElement(element, self._page)
        return None
    
    async def query_selector_all(self, selector: str) -> List[PlaywrightElement]:
        elements = await self._page.query_selector_all(selector)
        return [PlaywrightElement(el, self._page) for el in elements]
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible",
    ) -> Optional[PlaywrightElement]:
        try:
            element = await self._page.wait_for_selector(
                selector,
                timeout=timeout or 30000,
                state=state,
            )
            if element:
                return PlaywrightElement(element, self._page)
        except Exception:
            pass
        return None
    
    async def click(self, selector: str, **options: Any) -> None:
        await self._page.click(selector, **options)
    
    async def fill(self, selector: str, value: str, **options: Any) -> None:
        await self._page.fill(selector, value, **options)
    
    async def select_option(
        self,
        selector: str,
        value: Union[str, List[str]],
        **options: Any,
    ) -> List[str]:
        return await self._page.select_option(selector, value, **options)
    
    async def type(self, selector: str, text: str, delay: int = 0, **options: Any) -> None:
        await self._page.type(selector, text, delay=delay, **options)
    
    async def press(self, selector: str, key: str, **options: Any) -> None:
        await self._page.press(selector, key, **options)
    
    async def hover(self, selector: str, **options: Any) -> None:
        await self._page.hover(selector, **options)
    
    async def content(self) -> str:
        return await self._page.content()
    
    async def text_content(self, selector: str) -> Optional[str]:
        return await self._page.text_content(selector)
    
    async def get_attribute(self, selector: str, name: str) -> Optional[str]:
        return await self._page.get_attribute(selector, name)
    
    async def evaluate(self, expression: str, *args: Any) -> Any:
        if args:
            return await self._page.evaluate(expression, args[0])
        return await self._page.evaluate(expression)
    
    async def screenshot(
        self,
        path: Optional[Path] = None,
        full_page: bool = False,
        **options: Any,
    ) -> bytes:
        return await self._page.screenshot(path=path, full_page=full_page, **options)
    
    async def wait_for_load_state(self, state: str = "load", timeout: Optional[int] = None) -> None:
        await self._page.wait_for_load_state(state, timeout=timeout)
    
    async def wait_for_navigation(self, **options: Any) -> None:
        await self._page.wait_for_navigation(**options)
    
    async def wait_for_timeout(self, timeout: int) -> None:
        await self._page.wait_for_timeout(timeout)
    
    async def close(self) -> None:
        await self._page.close()


class PlaywrightContext(IBrowserContext):
    """Playwright browser context wrapper."""
    
    def __init__(self, context):
        self._context = context
    
    async def new_page(self, **options: Any) -> PlaywrightPage:
        page = await self._context.new_page()
        return PlaywrightPage(page)
    
    async def cookies(self) -> List[Dict[str, Any]]:
        return await self._context.cookies()
    
    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        await self._context.add_cookies(cookies)
    
    async def clear_cookies(self) -> None:
        await self._context.clear_cookies()
    
    async def close(self) -> None:
        await self._context.close()


class PlaywrightBrowser(IBrowser):
    """
    Playwright browser implementation.
    
    Example:
        >>> browser = PlaywrightBrowser()
        >>> await browser.launch(headless=False)
        >>> page = await browser.new_page()
        >>> await page.goto("https://google.com")
    """
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._default_context = None
    
    @property
    def is_connected(self) -> bool:
        return self._browser is not None and self._browser.is_connected()
    
    async def launch(
        self,
        headless: bool = True,
        browser_type: BrowserType = BrowserType.CHROMIUM,
        **options: Any,
    ) -> None:
        """Launch the browser."""
        from playwright.async_api import async_playwright
        
        self._playwright = await async_playwright().start()
        
        # Select browser type
        if browser_type == BrowserType.FIREFOX:
            browser_launcher = self._playwright.firefox
        elif browser_type == BrowserType.WEBKIT:
            browser_launcher = self._playwright.webkit
        else:
            browser_launcher = self._playwright.chromium
        
        self._browser = await browser_launcher.launch(
            headless=headless,
            **options,
        )
        
        logger.info(f"Launched {browser_type.value} browser (headless={headless})")
    
    async def new_page(self, **options: Any) -> PlaywrightPage:
        """Create a new page."""
        if not self._browser:
            raise RuntimeError("Browser not launched. Call launch() first.")
        
        # Create default context if needed
        if not self._default_context:
            self._default_context = await self._browser.new_context(**options)
        
        page = await self._default_context.new_page()
        return PlaywrightPage(page)
    
    async def new_context(self, **options: Any) -> PlaywrightContext:
        """Create a new browser context."""
        if not self._browser:
            raise RuntimeError("Browser not launched. Call launch() first.")
        
        context = await self._browser.new_context(**options)
        return PlaywrightContext(context)
    
    async def close(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.info("Browser closed")
