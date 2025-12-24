"""
Pytest configuration and fixtures.
"""

import pytest
from typing import AsyncGenerator


@pytest.fixture
def settings():
    """Provide test settings."""
    from llm_web_agent.config import Settings, BrowserSettings, LLMSettings
    
    return Settings(
        browser=BrowserSettings(
            engine="playwright",
            headless=True,
        ),
        llm=LLMSettings(
            provider="openai",
            model="gpt-4o-mini",  # Use smaller model for tests
        ),
    )


@pytest.fixture
def registry():
    """Provide a clean component registry for testing."""
    from llm_web_agent.registry import ComponentRegistry
    
    # Import to trigger registrations
    import llm_web_agent.browsers
    import llm_web_agent.llm
    import llm_web_agent.actions
    
    yield ComponentRegistry
    
    # Clean up after test
    ComponentRegistry.clear_all()


@pytest.fixture
async def browser():
    """Provide a browser instance for integration tests."""
    from llm_web_agent.browsers import PlaywrightBrowser
    
    browser = PlaywrightBrowser()
    await browser.launch(headless=True)
    
    yield browser
    
    await browser.close()


@pytest.fixture
async def page(browser):
    """Provide a page instance for integration tests."""
    page = await browser.new_page()
    yield page
    await page.close()
