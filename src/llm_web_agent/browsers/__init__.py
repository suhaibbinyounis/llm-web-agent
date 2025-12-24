"""
Browsers module - Browser automation implementations.
"""

from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser

__all__ = [
    "PlaywrightBrowser",
]


def _register_browsers() -> None:
    """Register browser implementations with the registry."""
    from llm_web_agent.registry import ComponentRegistry
    
    # Register Playwright (eager)
    ComponentRegistry.register_browser("playwright")(PlaywrightBrowser)
    
    # Register Selenium (lazy - only loads when needed)
    def selenium_factory():
        from llm_web_agent.browsers.selenium_browser import SeleniumBrowser
        return SeleniumBrowser
    
    ComponentRegistry.register_browser_factory("selenium", selenium_factory)


# Auto-register on import
_register_browsers()
