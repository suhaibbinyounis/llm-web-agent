"""
Tests for the Playwright browser adapter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPlaywrightElement:
    """Test the PlaywrightElement wrapper."""
    
    @pytest.fixture
    def mock_element(self):
        """Create a mock Playwright element."""
        element = AsyncMock()
        element.click = AsyncMock()
        element.fill = AsyncMock()
        element.select_option = AsyncMock(return_value=["value1"])
        element.get_attribute = AsyncMock(return_value="test-attr")
        element.text_content = AsyncMock(return_value="Test Text")
        element.inner_html = AsyncMock(return_value="<span>Test</span>")
        element.is_visible = AsyncMock(return_value=True)
        element.is_enabled = AsyncMock(return_value=True)
        element.hover = AsyncMock()
        element.scroll_into_view_if_needed = AsyncMock()
        element.wait_for = AsyncMock()
        element.evaluate = AsyncMock(return_value="div")
        return element
    
    @pytest.fixture
    def playwright_element(self, mock_element):
        """Create a PlaywrightElement instance."""
        from llm_web_agent.browsers.playwright_browser import PlaywrightElement
        mock_page = MagicMock()
        return PlaywrightElement(mock_element, mock_page)
    
    @pytest.mark.asyncio
    async def test_click(self, playwright_element, mock_element):
        """Test click method."""
        await playwright_element.click()
        mock_element.click.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fill(self, playwright_element, mock_element):
        """Test fill method."""
        await playwright_element.fill("test value")
        mock_element.fill.assert_called_once_with("test value")
    
    @pytest.mark.asyncio
    async def test_select_option(self, playwright_element, mock_element):
        """Test select_option method."""
        result = await playwright_element.select_option("value1")
        mock_element.select_option.assert_called_once_with("value1")
        assert result == ["value1"]
    
    @pytest.mark.asyncio
    async def test_get_attribute(self, playwright_element, mock_element):
        """Test get_attribute method."""
        result = await playwright_element.get_attribute("class")
        mock_element.get_attribute.assert_called_once_with("class")
        assert result == "test-attr"
    
    @pytest.mark.asyncio
    async def test_text_content(self, playwright_element, mock_element):
        """Test text_content method."""
        result = await playwright_element.text_content()
        assert result == "Test Text"
    
    @pytest.mark.asyncio
    async def test_is_visible(self, playwright_element, mock_element):
        """Test is_visible method."""
        result = await playwright_element.is_visible()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_enabled(self, playwright_element, mock_element):
        """Test is_enabled method."""
        result = await playwright_element.is_enabled()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_hover(self, playwright_element, mock_element):
        """Test hover method."""
        await playwright_element.hover()
        mock_element.hover.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scroll_into_view(self, playwright_element, mock_element):
        """Test scroll_into_view method."""
        await playwright_element.scroll_into_view()
        mock_element.scroll_into_view_if_needed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_for(self, playwright_element, mock_element):
        """Test wait_for method."""
        await playwright_element.wait_for(state="visible", timeout=5000)
        mock_element.wait_for.assert_called_once_with(state="visible", timeout=5000)


class TestPlaywrightPage:
    """Test the PlaywrightPage wrapper."""
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page."""
        page = AsyncMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Example")
        page.goto = AsyncMock()
        page.reload = AsyncMock()
        page.go_back = AsyncMock()
        page.go_forward = AsyncMock()
        page.query_selector = AsyncMock(return_value=AsyncMock())
        page.query_selector_all = AsyncMock(return_value=[AsyncMock()])
        page.wait_for_selector = AsyncMock(return_value=AsyncMock())
        page.click = AsyncMock()
        page.fill = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.evaluate = AsyncMock(return_value=True)
        page.screenshot = AsyncMock(return_value=b"image_data")
        page.wait_for_load_state = AsyncMock()
        page.wait_for_navigation = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.close = AsyncMock()
        page.keyboard = MagicMock()
        page.context = MagicMock()
        page.context.pages = [page]
        return page
    
    @pytest.fixture
    def playwright_page(self, mock_page):
        """Create a PlaywrightPage instance."""
        from llm_web_agent.browsers.playwright_browser import PlaywrightPage
        return PlaywrightPage(mock_page)
    
    def test_url_property(self, playwright_page):
        """Test url property."""
        assert playwright_page.url == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_goto(self, playwright_page, mock_page):
        """Test goto method."""
        await playwright_page.goto("https://test.com")
        mock_page.goto.assert_called_once_with("https://test.com")
    
    @pytest.mark.asyncio
    async def test_reload(self, playwright_page, mock_page):
        """Test reload method."""
        await playwright_page.reload()
        mock_page.reload.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_go_back(self, playwright_page, mock_page):
        """Test go_back method."""
        await playwright_page.go_back()
        mock_page.go_back.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_content(self, playwright_page, mock_page):
        """Test content method."""
        result = await playwright_page.content()
        assert result == "<html></html>"
    
    @pytest.mark.asyncio
    async def test_screenshot(self, playwright_page, mock_page):
        """Test screenshot method."""
        result = await playwright_page.screenshot()
        assert result == b"image_data"
    
    @pytest.mark.asyncio
    async def test_wait_for_load_state(self, playwright_page, mock_page):
        """Test wait_for_load_state method."""
        await playwright_page.wait_for_load_state("networkidle")
        mock_page.wait_for_load_state.assert_called()
    
    @pytest.mark.asyncio
    async def test_wait_for_selector_returns_element(self, playwright_page, mock_page):
        """Test wait_for_selector returns element when found."""
        result = await playwright_page.wait_for_selector("#test")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_wait_for_selector_with_timeout(self, playwright_page, mock_page):
        """Test wait_for_selector with custom timeout."""
        await playwright_page.wait_for_selector("#test", timeout=5000)
        mock_page.wait_for_selector.assert_called()


class TestPlaywrightBrowser:
    """Test the PlaywrightBrowser class."""
    
    def test_is_connected_before_launch(self):
        """Test is_connected returns False before launch."""
        from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser
        browser = PlaywrightBrowser()
        assert browser.is_connected is False
    
    @pytest.mark.asyncio
    async def test_new_page_before_launch_raises(self):
        """Test new_page raises error if not launched."""
        from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser
        browser = PlaywrightBrowser()
        with pytest.raises(RuntimeError, match="Browser not launched"):
            await browser.new_page()
    
    @pytest.mark.asyncio
    async def test_new_context_before_launch_raises(self):
        """Test new_context raises error if not launched."""
        from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser
        browser = PlaywrightBrowser()
        with pytest.raises(RuntimeError, match="Browser not launched"):
            await browser.new_context()
