"""
Browser Adapters - Concrete implementations of the browser interface.
"""

from llm_web_agent.browsers.playwright_browser import (
    PlaywrightBrowser,
    PlaywrightPage,
    PlaywrightElement,
    PlaywrightContext,
)

__all__ = [
    "PlaywrightBrowser",
    "PlaywrightPage",
    "PlaywrightElement",
    "PlaywrightContext",
]
