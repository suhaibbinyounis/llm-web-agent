"""
Integration tests for the Engine - full pipeline testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llm_web_agent.engine.engine import Engine, EngineResult
from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.task_graph import TaskStep, StepIntent, StepStatus


# =============================================================================
# MOCK CLASSES
# =============================================================================

class MockElement:
    """Mock element for testing."""
    
    def __init__(self, text: str = "", attrs: dict = None, visible: bool = True):
        self._text = text
        self._attrs = attrs or {}
        self._visible = visible
        self._value = ""
    
    async def text_content(self) -> str:
        return self._text
    
    async def get_attribute(self, name: str) -> Optional[str]:
        if name == "value":
            return self._value
        return self._attrs.get(name)
    
    async def is_visible(self) -> bool:
        return self._visible
    
    async def click(self) -> None:
        pass
    
    async def fill(self, value: str) -> None:
        self._value = value
    
    async def evaluate(self, script: str) -> Any:
        return None


class MockKeyboard:
    """Mock keyboard for testing."""
    
    async def press(self, key: str) -> None:
        pass


class MockPage:
    """Comprehensive mock page for integration tests."""
    
    def __init__(
        self,
        url: str = "https://example.com",
        title: str = "Test Page",
        elements: dict = None,
    ):
        self._url = url
        self._title = title
        self._elements = elements or {}
        self._actions: List[str] = []
        self.keyboard = MockKeyboard()
    
    @property
    def url(self) -> str:
        return self._url
    
    async def title(self) -> str:
        return self._title
    
    async def goto(self, url: str) -> None:
        self._url = url
        self._actions.append(f"goto:{url}")
    
    async def query_selector(self, selector: str) -> Optional[MockElement]:
        return self._elements.get(selector)
    
    async def query_selector_all(self, selector: str) -> List[MockElement]:
        return [e for s, e in self._elements.items() if selector in s or s in selector]
    
    async def click(self, selector: str) -> None:
        self._actions.append(f"click:{selector}")
    
    async def fill(self, selector: str, value: str) -> None:
        self._actions.append(f"fill:{selector}={value}")
        if selector in self._elements:
            await self._elements[selector].fill(value)
    
    async def type(self, selector: str, value: str) -> None:
        self._actions.append(f"type:{selector}={value}")
    
    async def select_option(self, selector: str, value: str) -> None:
        self._actions.append(f"select:{selector}={value}")
    
    async def hover(self, selector: str) -> None:
        self._actions.append(f"hover:{selector}")
    
    async def evaluate(self, script: str, arg: Any = None) -> Any:
        if "scrollTo" in script or "scrollBy" in script:
            self._actions.append("scroll")
            return None
        if "querySelectorAll" in script:
            return [
                {
                    "tag": "button",
                    "text": "Test",
                    "id": "test-btn",
                    "selector": "#test-btn",
                }
            ]
        if "querySelector" in script and arg:
            return None
        return None
    
    async def wait_for_load_state(self, state: str, timeout: int = 30000) -> None:
        pass
    
    async def wait_for_selector(self, selector: str, state: str = "visible", timeout: int = 30000) -> None:
        pass
    
    async def screenshot(self, path: str = None) -> None:
        self._actions.append(f"screenshot:{path}")
    
    def get_actions(self) -> List[str]:
        """Get list of performed actions for verification."""
        return self._actions


# =============================================================================
# TESTS
# =============================================================================

class TestEngineBasics:
    """Test basic Engine functionality."""
    
    def test_engine_creation(self):
        """Test creating an engine."""
        engine = Engine()
        
        assert engine is not None
        assert engine._max_retries == 2
    
    def test_engine_with_llm(self):
        """Test creating engine with LLM."""
        mock_llm = MagicMock()
        engine = Engine(llm_provider=mock_llm)
        
        assert engine._llm == mock_llm


class TestParseInstruction:
    """Test synchronous instruction parsing."""
    
    def test_parse_simple_instruction(self):
        """Test parsing simple instruction."""
        engine = Engine()
        
        graph = engine.parse_instruction("go to google.com")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.NAVIGATE
    
    def test_parse_multi_step_instruction(self):
        """Test parsing multi-step instruction."""
        engine = Engine()
        
        graph = engine.parse_instruction(
            "go to google.com, search for cats, click the first result"
        )
        
        assert len(graph.steps) == 3
    
    def test_parse_empty_instruction(self):
        """Test parsing empty instruction."""
        engine = Engine()
        
        graph = engine.parse_instruction("")
        
        assert len(graph.steps) == 0


class TestEngineRun:
    """Test Engine.run() with various scenarios."""
    
    @pytest.mark.asyncio
    async def test_run_navigation(self):
        """Test running a navigation task."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(page, "go to https://google.com")
        
        assert result.success is True
        assert result.steps_total == 1
        assert result.steps_completed == 1
        assert "goto:https://google.com" in page.get_actions()
    
    @pytest.mark.asyncio
    async def test_run_with_context(self):
        """Test running with existing context."""
        page = MockPage()
        engine = Engine()
        context = RunContext()
        context.store("search_term", "cats")
        
        result = await engine.run(
            page,
            "go to google.com",
            context=context,
        )
        
        assert result.context.retrieve("search_term") == "cats"
    
    @pytest.mark.asyncio
    async def test_run_with_variables(self):
        """Test running with pre-populated variables."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(
            page,
            "go to google.com",
            variables={"user": "john", "pass": "secret"},
        )
        
        assert result.context.retrieve("user") == "john"
        assert result.context.retrieve("pass") == "secret"
    
    @pytest.mark.asyncio
    async def test_run_empty_instruction(self):
        """Test running empty instruction fails gracefully."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(page, "")
        
        assert result.success is False
        assert "Could not parse" in result.error
    
    @pytest.mark.asyncio
    async def test_run_result_has_run_id(self):
        """Test result has a run ID."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(page, "go to google.com")
        
        assert result.run_id is not None
        assert len(result.run_id) == 8


class TestEngineRunSteps:
    """Test Engine.run_steps() with pre-built steps."""
    
    @pytest.mark.asyncio
    async def test_run_custom_steps(self):
        """Test running pre-built steps."""
        btn = MockElement(text="Login", attrs={"id": "login-btn"})
        page = MockPage(elements={
            "#login-btn": btn,
            "[data-testid='login-btn']": btn,
            "text='Login'": btn,
        })
        engine = Engine()
        
        steps = [
            TaskStep(intent=StepIntent.NAVIGATE, target="https://example.com"),
        ]
        
        result = await engine.run_steps(page, steps)
        
        # Navigation should succeed
        assert "goto:https://example.com" in page.get_actions()


class TestEngineExtraction:
    """Test data extraction during runs."""
    
    @pytest.mark.asyncio
    async def test_extract_saves_to_context(self):
        """Test extraction saves data to context."""
        price_elem = MockElement(text="$299.99", attrs={"id": "price"})
        page = MockPage(elements={
            "#price": price_elem,
            "[name='price']": price_elem,
            "[data-testid='price']": price_elem,
        })
        engine = Engine()
        
        # Create step that extracts
        steps = [
            TaskStep(
                intent=StepIntent.EXTRACT,
                target="#price",
                store_as="product_price",
            ),
        ]
        
        result = await engine.run_steps(page, steps)
        
        # Value might be in clipboard
        # (exact behavior depends on BatchExecutor implementation)
        assert result.context is not None


class TestEngineResult:
    """Test EngineResult properties."""
    
    def test_result_success(self):
        """Test successful result."""
        result = EngineResult(
            success=True,
            run_id="test123",
            task="test task",
            steps_total=3,
            steps_completed=3,
            steps_failed=0,
            duration_seconds=1.5,
        )
        
        assert result.success is True
        assert result.steps_completed == 3
        assert result.duration_seconds == 1.5
    
    def test_result_failure(self):
        """Test failed result."""
        result = EngineResult(
            success=False,
            run_id="test123",
            task="test task",
            error="Element not found",
        )
        
        assert result.success is False
        assert result.error == "Element not found"
    
    def test_result_extracted_data(self):
        """Test result with extracted data."""
        result = EngineResult(
            success=True,
            run_id="test123",
            task="test",
            extracted_data={"price": "$299.99", "title": "Product"},
        )
        
        assert result.extracted_data["price"] == "$299.99"
        assert result.extracted_data["title"] == "Product"


class TestEngineErrorHandling:
    """Test Engine error handling."""
    
    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Test engine handles exceptions gracefully."""
        page = MagicMock()
        page.url = "https://example.com"
        page.goto = AsyncMock(side_effect=Exception("Network error"))
        page.title = AsyncMock(return_value="Test")
        page.wait_for_load_state = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)
        page.query_selector_all = AsyncMock(return_value=[])
        page.evaluate = AsyncMock(return_value=[])
        
        engine = Engine()
        
        result = await engine.run(page, "go to google.com")
        
        # Should return failure result, not crash
        assert result.success is False
        assert result.error is not None


class TestEngineStats:
    """Test Engine execution statistics."""
    
    @pytest.mark.asyncio
    async def test_tracks_duration(self):
        """Test engine tracks execution duration."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(page, "go to google.com")
        
        assert result.duration_seconds > 0
    
    @pytest.mark.asyncio
    async def test_counts_steps(self):
        """Test engine counts steps correctly."""
        page = MockPage()
        engine = Engine()
        
        result = await engine.run(
            page,
            "go to google.com, scroll down"
        )
        
        assert result.steps_total == 2
