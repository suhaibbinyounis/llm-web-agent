"""
Browser Interface - Abstract base classes for browser automation engines.

This module defines the contract that browser implementations (Playwright, Selenium, etc.)
must follow to be compatible with the LLM Web Agent.

Example:
    >>> from llm_web_agent.browsers import PlaywrightBrowser
    >>> browser = PlaywrightBrowser()
    >>> await browser.launch(headless=True)
    >>> page = await browser.new_page()
    >>> await page.goto("https://example.com")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrowserType(Enum):
    """Supported browser types."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class ElementHandle:
    """
    Represents a DOM element with its properties.
    
    This is a lightweight, serializable representation of a DOM element
    that can be passed between components without holding browser references.
    
    Attributes:
        selector: The CSS/XPath selector used to find this element
        tag_name: The HTML tag name (e.g., 'div', 'button', 'input')
        attributes: Dictionary of element attributes
        text_content: The visible text content of the element
        inner_html: The inner HTML of the element (optional)
        bounding_box: The element's position and size (optional)
        is_visible: Whether the element is visible on the page
        is_enabled: Whether the element is enabled (for form elements)
    """
    selector: str
    tag_name: str
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: str = ""
    inner_html: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    is_visible: bool = True
    is_enabled: bool = True

    @property
    def id(self) -> Optional[str]:
        """Get the element's id attribute."""
        return self.attributes.get("id")

    @property
    def class_list(self) -> List[str]:
        """Get the element's class list."""
        class_attr = self.attributes.get("class", "")
        return class_attr.split() if class_attr else []


class IElement(ABC):
    """
    Abstract interface for interacting with a DOM element.
    
    This interface wraps a live browser element reference and provides
    methods for interaction and inspection.
    """

    @abstractmethod
    async def click(self, **options: Any) -> None:
        """
        Click on this element.
        
        Args:
            **options: Browser-specific click options (e.g., button, modifiers)
        """
        ...

    @abstractmethod
    async def fill(self, value: str, **options: Any) -> None:
        """
        Fill this element with text (for input/textarea elements).
        
        Args:
            value: The text to fill
            **options: Browser-specific fill options
        """
        ...

    @abstractmethod
    async def select_option(self, value: Union[str, List[str]], **options: Any) -> List[str]:
        """
        Select option(s) in a <select> element.
        
        Args:
            value: Option value(s) to select
            **options: Browser-specific options
            
        Returns:
            List of selected option values
        """
        ...

    @abstractmethod
    async def get_attribute(self, name: str) -> Optional[str]:
        """
        Get an attribute value from this element.
        
        Args:
            name: The attribute name
            
        Returns:
            The attribute value, or None if not present
        """
        ...

    @abstractmethod
    async def text_content(self) -> Optional[str]:
        """
        Get the text content of this element.
        
        Returns:
            The visible text content
        """
        ...

    @abstractmethod
    async def inner_html(self) -> str:
        """
        Get the inner HTML of this element.
        
        Returns:
            The inner HTML string
        """
        ...

    @abstractmethod
    async def is_visible(self) -> bool:
        """
        Check if this element is visible.
        
        Returns:
            True if the element is visible
        """
        ...

    @abstractmethod
    async def is_enabled(self) -> bool:
        """
        Check if this element is enabled.
        
        Returns:
            True if the element is enabled
        """
        ...

    @abstractmethod
    async def hover(self, **options: Any) -> None:
        """
        Hover over this element.
        
        Args:
            **options: Browser-specific hover options
        """
        ...

    @abstractmethod
    async def scroll_into_view(self) -> None:
        """Scroll the element into view."""
        ...

    @abstractmethod
    async def to_handle(self) -> ElementHandle:
        """
        Convert this live element to a serializable ElementHandle.
        
        Returns:
            An ElementHandle with the element's current properties
        """
        ...


class IPage(ABC):
    """
    Abstract interface for browser page operations.
    
    This interface defines all operations that can be performed on a browser page,
    including navigation, element interaction, and content extraction.
    """

    @property
    @abstractmethod
    def url(self) -> str:
        """Get the current page URL."""
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        """Get the current page title."""
        ...

    # Navigation methods
    @abstractmethod
    async def goto(self, url: str, **options: Any) -> None:
        """
        Navigate to a URL.
        
        Args:
            url: The URL to navigate to
            **options: Browser-specific navigation options (e.g., wait_until, timeout)
        """
        ...

    @abstractmethod
    async def reload(self, **options: Any) -> None:
        """Reload the current page."""
        ...

    @abstractmethod
    async def go_back(self, **options: Any) -> None:
        """Navigate back in history."""
        ...

    @abstractmethod
    async def go_forward(self, **options: Any) -> None:
        """Navigate forward in history."""
        ...

    # Element selection methods
    @abstractmethod
    async def query_selector(self, selector: str) -> Optional[IElement]:
        """
        Find the first element matching a selector.
        
        Args:
            selector: CSS selector or browser-specific selector
            
        Returns:
            The matching element, or None if not found
        """
        ...

    @abstractmethod
    async def query_selector_all(self, selector: str) -> List[IElement]:
        """
        Find all elements matching a selector.
        
        Args:
            selector: CSS selector or browser-specific selector
            
        Returns:
            List of matching elements
        """
        ...

    @abstractmethod
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible",
    ) -> Optional[IElement]:
        """
        Wait for an element matching the selector to appear.
        
        Args:
            selector: CSS selector or browser-specific selector
            timeout: Maximum time to wait in milliseconds
            state: Expected element state ('attached', 'detached', 'visible', 'hidden')
            
        Returns:
            The matching element, or None if timeout
        """
        ...

    # Direct interaction methods (convenience methods that find + interact)
    @abstractmethod
    async def click(self, selector: str, **options: Any) -> None:
        """
        Click on an element matching the selector.
        
        Args:
            selector: CSS selector for the element to click
            **options: Browser-specific click options
        """
        ...

    @abstractmethod
    async def fill(self, selector: str, value: str, **options: Any) -> None:
        """
        Fill an input element with text.
        
        Args:
            selector: CSS selector for the input element
            value: Text to fill
            **options: Browser-specific fill options
        """
        ...

    @abstractmethod
    async def select_option(
        self,
        selector: str,
        value: Union[str, List[str]],
        **options: Any,
    ) -> List[str]:
        """
        Select option(s) in a <select> element.
        
        Args:
            selector: CSS selector for the select element
            value: Option value(s) to select
            **options: Browser-specific options
            
        Returns:
            List of selected option values
        """
        ...

    @abstractmethod
    async def type(self, selector: str, text: str, delay: int = 0, **options: Any) -> None:
        """
        Type text into an element (character by character).
        
        Args:
            selector: CSS selector for the element
            text: Text to type
            delay: Delay between keystrokes in milliseconds
            **options: Browser-specific options
        """
        ...

    @abstractmethod
    async def press(self, selector: str, key: str, **options: Any) -> None:
        """
        Press a key on an element.
        
        Args:
            selector: CSS selector for the element
            key: Key to press (e.g., 'Enter', 'Tab', 'ArrowDown')
            **options: Browser-specific options
        """
        ...

    @abstractmethod
    async def hover(self, selector: str, **options: Any) -> None:
        """
        Hover over an element.
        
        Args:
            selector: CSS selector for the element
            **options: Browser-specific hover options
        """
        ...

    # Content extraction methods
    @abstractmethod
    async def content(self) -> str:
        """
        Get the full HTML content of the page.
        
        Returns:
            The page's HTML content
        """
        ...

    @abstractmethod
    async def text_content(self, selector: str) -> Optional[str]:
        """
        Get the text content of an element.
        
        Args:
            selector: CSS selector for the element
            
        Returns:
            The element's text content, or None if not found
        """
        ...

    @abstractmethod
    async def get_attribute(self, selector: str, name: str) -> Optional[str]:
        """
        Get an attribute value from an element.
        
        Args:
            selector: CSS selector for the element
            name: Attribute name
            
        Returns:
            The attribute value, or None if not found
        """
        ...

    # JavaScript execution
    @abstractmethod
    async def evaluate(self, expression: str, *args: Any) -> Any:
        """
        Execute JavaScript in the page context.
        
        Args:
            expression: JavaScript expression or function to execute
            *args: Arguments to pass to the function
            
        Returns:
            The result of the JavaScript execution
        """
        ...

    # Screenshot and PDF
    @abstractmethod
    async def screenshot(
        self,
        path: Optional["Path"] = None,
        full_page: bool = False,
        **options: Any,
    ) -> bytes:
        """
        Take a screenshot of the page.
        
        Args:
            path: Optional path to save the screenshot
            full_page: Whether to capture the full scrollable page
            **options: Browser-specific screenshot options
            
        Returns:
            The screenshot as PNG bytes
        """
        ...

    # Waiting methods
    @abstractmethod
    async def wait_for_load_state(self, state: str = "load", timeout: Optional[int] = None) -> None:
        """
        Wait for the page to reach a specific load state.
        
        Args:
            state: Load state to wait for ('load', 'domcontentloaded', 'networkidle')
            timeout: Maximum time to wait in milliseconds
        """
        ...

    @abstractmethod
    async def wait_for_navigation(self, **options: Any) -> None:
        """
        Wait for navigation to complete.
        
        Args:
            **options: Browser-specific navigation options
        """
        ...

    @abstractmethod
    async def wait_for_timeout(self, timeout: int) -> None:
        """
        Wait for a specified amount of time.
        
        Args:
            timeout: Time to wait in milliseconds
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close this page."""
        ...


class IBrowser(ABC):
    """
    Abstract interface for browser management.
    
    This interface defines the contract for launching, managing, and closing
    browser instances. Implementations should handle browser-specific setup
    and teardown.
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the browser is connected and running."""
        ...

    @abstractmethod
    async def launch(
        self,
        headless: bool = True,
        browser_type: BrowserType = BrowserType.CHROMIUM,
        **options: Any,
    ) -> None:
        """
        Launch a browser instance.
        
        Args:
            headless: Whether to run in headless mode
            browser_type: Type of browser to launch
            **options: Browser-specific launch options
        """
        ...

    @abstractmethod
    async def new_page(self, **options: Any) -> IPage:
        """
        Create a new browser page/tab.
        
        Args:
            **options: Browser-specific page options (e.g., viewport size)
            
        Returns:
            A new page instance
        """
        ...

    @abstractmethod
    async def new_context(self, **options: Any) -> "IBrowserContext":
        """
        Create a new browser context (isolated session).
        
        Args:
            **options: Browser-specific context options
            
        Returns:
            A new browser context
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        ...


class IBrowserContext(ABC):
    """
    Abstract interface for browser context (isolated session).
    
    A browser context provides an isolated environment with its own cookies,
    localStorage, and cache. Useful for running multiple independent sessions.
    """

    @abstractmethod
    async def new_page(self, **options: Any) -> IPage:
        """
        Create a new page in this context.
        
        Args:
            **options: Browser-specific page options
            
        Returns:
            A new page instance
        """
        ...

    @abstractmethod
    async def cookies(self) -> List[Dict[str, Any]]:
        """
        Get all cookies in this context.
        
        Returns:
            List of cookie dictionaries
        """
        ...

    @abstractmethod
    async def add_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """
        Add cookies to this context.
        
        Args:
            cookies: List of cookie dictionaries to add
        """
        ...

    @abstractmethod
    async def clear_cookies(self) -> None:
        """Clear all cookies in this context."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close this context and all its pages."""
        ...
