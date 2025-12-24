"""
Browser-related exceptions.
"""

from llm_web_agent.exceptions.base import LLMWebAgentError


class BrowserError(LLMWebAgentError):
    """Base exception for browser-related errors."""
    pass


class BrowserLaunchError(BrowserError):
    """
    Error launching the browser.
    
    Raised when the browser fails to start, which could be due to:
    - Missing browser binaries
    - Invalid browser options
    - Resource constraints
    """
    pass


class BrowserConnectionError(BrowserError):
    """
    Error connecting to the browser.
    
    Raised when the connection to the browser is lost or cannot be established.
    """
    pass


class PageError(BrowserError):
    """Base exception for page-related errors."""
    pass


class NavigationError(PageError):
    """
    Error during page navigation.
    
    Raised when navigation fails, such as:
    - Invalid URL
    - Network error
    - Server error (4xx, 5xx)
    - Navigation timeout
    """
    
    def __init__(self, message: str, url: str | None = None, status_code: int | None = None):
        super().__init__(message, {"url": url, "status_code": status_code})
        self.url = url
        self.status_code = status_code


class ElementNotFoundError(PageError):
    """
    Element not found on the page.
    
    Raised when an element matching the selector cannot be found.
    """
    
    def __init__(self, message: str, selector: str):
        super().__init__(message, {"selector": selector})
        self.selector = selector


class ElementNotVisibleError(PageError):
    """
    Element exists but is not visible.
    
    Raised when an element is found but is not visible (hidden, off-screen, etc.).
    """
    
    def __init__(self, message: str, selector: str):
        super().__init__(message, {"selector": selector})
        self.selector = selector


class ElementNotInteractableError(PageError):
    """
    Element cannot be interacted with.
    
    Raised when an element is found and visible but cannot receive interactions
    (e.g., covered by another element, disabled).
    """
    
    def __init__(self, message: str, selector: str, reason: str | None = None):
        super().__init__(message, {"selector": selector, "reason": reason})
        self.selector = selector
        self.reason = reason


class TimeoutError(PageError):
    """
    Operation timed out.
    
    Raised when a browser operation exceeds its timeout.
    """
    
    def __init__(self, message: str, timeout_ms: int, operation: str | None = None):
        super().__init__(message, {"timeout_ms": timeout_ms, "operation": operation})
        self.timeout_ms = timeout_ms
        self.operation = operation
