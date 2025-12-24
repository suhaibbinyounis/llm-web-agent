"""
Tests for StateManager - page state and navigation handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from llm_web_agent.engine.state_manager import StateManager, PageState
from llm_web_agent.engine.run_context import RunContext


# =============================================================================
# MOCK CLASSES
# =============================================================================

class MockPage:
    """Mock page for state manager tests."""
    
    def __init__(
        self,
        url: str = "https://example.com",
        title: str = "Test Page",
    ):
        self._url = url
        self._title = title
        self._wait_calls = []
    
    @property
    def url(self) -> str:
        return self._url
    
    def set_url(self, url: str):
        """Simulate navigation."""
        self._url = url
    
    async def title(self) -> str:
        return self._title
    
    async def wait_for_load_state(self, state: str, timeout: int = 30000) -> None:
        self._wait_calls.append(f"load_state:{state}")
    
    async def wait_for_selector(
        self,
        selector: str,
        state: str = "hidden",
        timeout: int = 5000,
    ) -> None:
        self._wait_calls.append(f"selector:{selector}")
    
    async def query_selector_all(self, selector: str):
        return []
    
    async def evaluate(self, script: str) -> None:
        pass


# =============================================================================
# TESTS
# =============================================================================

class TestStateManagerCreation:
    """Test StateManager creation."""
    
    def test_create_manager(self):
        """Test creating state manager."""
        manager = StateManager()
        
        assert manager is not None
    
    def test_create_with_options(self):
        """Test creating with options."""
        manager = StateManager(
            default_timeout_ms=60000,
            stability_delay_ms=200,
        )
        
        assert manager._default_timeout == 60000
        assert manager._stability_delay == 200


class TestWaitForStable:
    """Test waiting for page stability."""
    
    @pytest.mark.asyncio
    async def test_wait_for_stable(self):
        """Test waiting for page to stabilize."""
        page = MockPage()
        manager = StateManager()
        
        result = await manager.wait_for_stable(page)
        
        assert result is True
        # Should have called wait_for_load_state
        assert any("load_state" in c for c in page._wait_calls)
    
    @pytest.mark.asyncio
    async def test_wait_for_stable_handles_timeout(self):
        """Test wait handles timeout gracefully."""
        page = MagicMock()
        page.url = "https://example.com"
        page.wait_for_load_state = AsyncMock(side_effect=TimeoutError())
        page.query_selector_all = AsyncMock(return_value=[])
        
        manager = StateManager()
        
        # Should not raise, just return True
        result = await manager.wait_for_stable(page)
        assert result is True


class TestWaitForNavigation:
    """Test waiting for navigation."""
    
    @pytest.mark.asyncio
    async def test_detect_navigation(self):
        """Test detecting URL change."""
        page = MockPage(url="https://example.com/page2")
        manager = StateManager()
        
        # Previous URL was different
        changed = await manager.wait_for_navigation(
            page,
            current_url="https://example.com/page1",
            timeout_ms=100,
        )
        
        assert changed is True
    
    @pytest.mark.asyncio
    async def test_no_navigation(self):
        """Test when URL hasn't changed."""
        page = MockPage(url="https://example.com/page1")
        manager = StateManager()
        
        changed = await manager.wait_for_navigation(
            page,
            current_url="https://example.com/page1",
            timeout_ms=100,  # Short timeout
        )
        
        assert changed is False


class TestUpdateContext:
    """Test context updating."""
    
    @pytest.mark.asyncio
    async def test_update_context(self):
        """Test updating context with page state."""
        page = MockPage(
            url="https://example.com/updated",
            title="Updated Page",
        )
        context = RunContext()
        manager = StateManager()
        
        await manager.update_context(page, context)
        
        assert context.current_url == "https://example.com/updated"
        assert context.page_title == "Updated Page"
    
    @pytest.mark.asyncio
    async def test_update_context_stores_extracted(self):
        """Test update stores in extracted dict."""
        page = MockPage(
            url="https://example.com",
            title="Page Title",
        )
        context = RunContext()
        manager = StateManager()
        
        await manager.update_context(page, context)
        
        assert context.extracted["current_url"] == "https://example.com"


class TestInvalidateOnNavigation:
    """Test cache invalidation on navigation."""
    
    @pytest.mark.asyncio
    async def test_invalidate_on_url_change(self):
        """Test DOM cache invalidated on URL change."""
        page = MockPage(url="https://example.com/new")
        context = RunContext()
        
        # Set initial state
        context.update_page_state("https://example.com/old")
        context.set_dom_cache({"elements": [1, 2, 3]}, "https://example.com/old")
        
        manager = StateManager()
        
        result = await manager.invalidate_on_navigation(
            page, context, previous_url="https://example.com/old"
        )
        
        assert result is True
        # Cache should be cleared
        assert context.get_dom_cache() is None
        # URL should be updated
        assert context.current_url == "https://example.com/new"
    
    @pytest.mark.asyncio
    async def test_no_invalidate_when_same_url(self):
        """Test no invalidation when URL is same."""
        page = MockPage(url="https://example.com/same")
        context = RunContext()
        
        # Set initial state (same URL)
        context.update_page_state("https://example.com/same")
        context.set_dom_cache({"elements": [1, 2, 3]}, "https://example.com/same")
        
        manager = StateManager()
        
        result = await manager.invalidate_on_navigation(
            page, context, previous_url="https://example.com/same"
        )
        
        assert result is False
        # Cache should still be valid
        assert context.get_dom_cache() is not None


class TestWaitForElement:
    """Test waiting for specific element."""
    
    @pytest.mark.asyncio
    async def test_wait_for_element_visible(self):
        """Test waiting for element to be visible."""
        page = MockPage()
        manager = StateManager()
        
        result = await manager.wait_for_element(page, "#loading", state="hidden")
        
        assert result is True
        assert any("selector:#loading" in c for c in page._wait_calls)


class TestGetState:
    """Test getting current page state."""
    
    @pytest.mark.asyncio
    async def test_get_state(self):
        """Test getting current state."""
        page = MockPage(
            url="https://example.com",
            title="Test Page",
        )
        manager = StateManager()
        
        state = await manager.get_state(page)
        
        assert isinstance(state, PageState)
        assert state.url == "https://example.com"
        assert state.title == "Test Page"


class TestDetectNavigation:
    """Test navigation detection."""
    
    @pytest.mark.asyncio
    async def test_detect_navigation_true(self):
        """Test detecting navigation occurred."""
        page = MockPage(url="https://new.com")
        manager = StateManager()
        
        result = await manager.detect_navigation(page, "https://old.com")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_detect_navigation_false(self):
        """Test detecting no navigation."""
        page = MockPage(url="https://same.com")
        manager = StateManager()
        
        result = await manager.detect_navigation(page, "https://same.com")
        
        assert result is False
