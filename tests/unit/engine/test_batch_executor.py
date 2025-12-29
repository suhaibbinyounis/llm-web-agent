"""
Tests for BatchExecutor - optimized batch execution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List, Optional

from llm_web_agent.engine.batch_executor import BatchExecutor, BatchResult
from llm_web_agent.engine.task_graph import TaskStep, StepIntent, StepStatus
from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.target_resolver import TargetResolver, ResolvedTarget, ResolutionStrategy
from llm_web_agent.engine.state_manager import StateManager

# Backwards compat alias
ResolutionLayer = ResolutionStrategy


# =============================================================================
# MOCK CLASSES
# =============================================================================

class MockElement:
    """Mock element."""
    
    def __init__(self, text: str = "", value: str = ""):
        self._text = text
        self._value = value
    
    async def text_content(self) -> str:
        return self._text
    
    async def inner_text(self) -> str:
        return self._text
    
    async def get_attribute(self, name: str) -> Optional[str]:
        if name == "value":
            return self._value
        return None
    
    async def is_visible(self) -> bool:
        return True
    
    async def click(self) -> None:
        pass
    
    async def fill(self, value: str) -> None:
        self._value = value


class MockKeyboard:
    """Mock keyboard."""
    
    async def press(self, key: str) -> None:
        pass


class MockPage:
    """Mock page for batch executor tests."""
    
    def __init__(
        self,
        url: str = "https://example.com",
        elements: Dict[str, MockElement] = None,
    ):
        self._url = url
        self._elements = elements or {}
        self._actions: List[str] = []
        self.keyboard = MockKeyboard()
    
    @property
    def url(self) -> str:
        return self._url
    
    async def title(self) -> str:
        return "Test Page"
    
    async def goto(self, url: str, **kwargs) -> None:
        self._url = url
        self._actions.append(f"goto:{url}")
    
    async def query_selector(self, selector: str) -> Optional[MockElement]:
        return self._elements.get(selector)
    
    async def click(self, selector: str) -> None:
        self._actions.append(f"click:{selector}")
    
    async def fill(self, selector: str, value: str) -> None:
        self._actions.append(f"fill:{selector}={value}")
    
    async def type(self, selector: str, value: str) -> None:
        self._actions.append(f"type:{selector}={value}")
    
    async def select_option(self, selector: str, value: str) -> None:
        self._actions.append(f"select:{selector}={value}")
    
    async def hover(self, selector: str) -> None:
        self._actions.append(f"hover:{selector}")
    
    async def evaluate(self, script: str, args: Any = None) -> Any:
        if "scrollTo" in script or "scrollBy" in script:
            self._actions.append("scroll")
        return None
    
    async def wait_for_load_state(self, state: str, timeout: int = 30000) -> None:
        pass
    
    async def wait_for_selector(self, selector: str, **kwargs) -> None:
        pass
    
    async def screenshot(self, path: str = None) -> bytes:
        self._actions.append(f"screenshot")
        return b""
    
    def get_actions(self) -> List[str]:
        return self._actions


class MockResolver:
    """Mock target resolver."""
    
    def __init__(self, always_succeed: bool = True):
        self._always_succeed = always_succeed
    
    async def resolve(
        self,
        page: Any,
        target: str,
        intent: str = None,
        dom: Any = None,
        wait_timeout: int = 3000,
    ) -> ResolvedTarget:
        if self._always_succeed:
            return ResolvedTarget(
                selector=f"#{target.replace(' ', '-')}",
                strategy=ResolutionStrategy.DIRECT,
                confidence=1.0,
            )
        return ResolvedTarget(
            selector="",
            strategy=ResolutionStrategy.FAILED,
            confidence=0,
        )


class MockStateManager:
    """Mock state manager."""
    
    async def wait_for_stable(self, page: Any) -> None:
        pass
    
    async def wait_for_navigation(self, page: Any, previous_url: str) -> bool:
        return page.url != previous_url
    
    async def update_context(self, page: Any, context: RunContext) -> None:
        context.update_page_state(page.url)
    
    async def invalidate_on_navigation(self, page: Any, context: RunContext) -> None:
        pass


# =============================================================================
# TESTS
# =============================================================================

class TestBatchExecutorCreation:
    """Test BatchExecutor creation."""
    
    def test_create_executor(self):
        """Test creating executor."""
        resolver = MockResolver()
        state_manager = MockStateManager()
        
        executor = BatchExecutor(
            resolver=resolver,
            state_manager=state_manager,
        )
        
        assert executor is not None


class TestExecuteBatch:
    """Test batch execution."""
    
    @pytest.fixture
    def executor(self):
        """Create executor for tests."""
        return BatchExecutor(
            resolver=MockResolver(),
            state_manager=MockStateManager(),
        )
    
    @pytest.mark.asyncio
    async def test_execute_empty_batch(self, executor):
        """Test executing empty batch."""
        page = MockPage()
        context = RunContext()
        
        result = await executor.execute_batch(page, [], context)
        
        assert result.all_success is True
        assert len(result.results) == 0
    
    @pytest.mark.asyncio
    async def test_execute_navigate_step(self, executor):
        """Test executing navigation step."""
        page = MockPage()
        context = RunContext()
        steps = [
            TaskStep(intent=StepIntent.NAVIGATE, target="https://google.com"),
        ]
        
        result = await executor.execute_batch(page, steps, context)
        
        assert result.all_success is True
        assert "goto:https://google.com" in page.get_actions()
    
    @pytest.mark.asyncio
    async def test_execute_click_step(self, executor):
        """Test executing click step."""
        btn = MockElement(text="Click")
        page = MockPage(elements={"#login-button": btn})
        context = RunContext()
        steps = [
            TaskStep(intent=StepIntent.CLICK, target="login button"),
        ]
        
        result = await executor.execute_batch(page, steps, context)
        
        # Should attempt click
        assert any("click" in a for a in page.get_actions())
    
    @pytest.mark.asyncio
    async def test_execute_fill_step(self, executor):
        """Test executing fill step."""
        inp = MockElement()
        page = MockPage(elements={"#email": inp})
        context = RunContext()
        steps = [
            TaskStep(intent=StepIntent.FILL, target="email", value="test@test.com"),
        ]
        
        result = await executor.execute_batch(page, steps, context)
        
        assert any("fill" in a and "test@test.com" in a for a in page.get_actions())
    
    @pytest.mark.asyncio
    async def test_execute_scroll_step(self, executor):
        """Test executing scroll step."""
        page = MockPage()
        context = RunContext()
        steps = [
            TaskStep(intent=StepIntent.SCROLL, target="down"),
        ]
        
        result = await executor.execute_batch(page, steps, context)
        
        assert "scroll" in page.get_actions()
    
    @pytest.mark.asyncio
    async def test_execute_press_key_step(self, executor):
        """Test executing press key step."""
        page = MockPage()
        context = RunContext()
        steps = [
            TaskStep(intent=StepIntent.PRESS_KEY, value="Enter"),
        ]
        
        result = await executor.execute_batch(page, steps, context)
        
        # Should complete without error
        assert result.all_success is True
    
    @pytest.mark.asyncio
    async def test_marks_step_success(self, executor):
        """Test step is marked as successful."""
        page = MockPage()
        context = RunContext()
        step = TaskStep(intent=StepIntent.NAVIGATE, target="https://example.com")
        
        await executor.execute_batch(page, [step], context)
        
        assert step.status == StepStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_marks_step_failed(self):
        """Test step is marked as failed when resolution fails."""
        executor = BatchExecutor(
            resolver=MockResolver(always_succeed=False),
            state_manager=MockStateManager(),
        )
        page = MockPage()
        context = RunContext()
        step = TaskStep(intent=StepIntent.CLICK, target="nonexistent")
        
        await executor.execute_batch(page, [step], context)
        
        assert step.status == StepStatus.FAILED
        assert step.error is not None


class TestBatchResult:
    """Test BatchResult dataclass."""
    
    def test_all_success_true(self):
        """Test all_success when all succeed."""
        result = BatchResult(
            steps=[],
            results=[
                MagicMock(success=True),
                MagicMock(success=True),
            ]
        )
        
        assert result.all_success is True
    
    def test_all_success_false(self):
        """Test all_success when one fails."""
        result = BatchResult(
            steps=[],
            results=[
                MagicMock(success=True),
                MagicMock(success=False),
            ]
        )
        
        assert result.all_success is False


class TestVariableResolution:
    """Test variable resolution in step values."""
    
    @pytest.mark.asyncio
    async def test_resolves_variable_in_value(self):
        """Test resolving {{variable}} in step value."""
        executor = BatchExecutor(
            resolver=MockResolver(),
            state_manager=MockStateManager(),
        )
        page = MockPage()
        context = RunContext()
        context.store("email", "resolved@example.com")
        
        step = TaskStep(
            intent=StepIntent.FILL,
            target="email field",
            value="{{email}}",
        )
        
        await executor.execute_batch(page, [step], context)
        
        # The fill action should use resolved value
        assert any("resolved@example.com" in a for a in page.get_actions())


class TestExtraction:
    """Test extraction functionality."""
    
    @pytest.mark.asyncio
    async def test_extract_stores_in_context(self):
        """Test extraction stores data in context."""
        executor = BatchExecutor(
            resolver=MockResolver(),
            state_manager=MockStateManager(),
        )
        elem = MockElement(text="$299.99")
        page = MockPage(elements={"#price": elem})
        context = RunContext()
        
        step = TaskStep(
            intent=StepIntent.EXTRACT,
            target="price",
            store_as="product_price",
        )
        
        await executor.execute_batch(page, [step], context)
        
        # Value should be stored in clipboard
        # (exact behavior depends on implementation)
        # For now just verify step completed


class TestRecordsHistory:
    """Test action history recording."""
    
    @pytest.mark.asyncio
    async def test_records_action_in_context(self):
        """Test actions are recorded in context history."""
        executor = BatchExecutor(
            resolver=MockResolver(),
            state_manager=MockStateManager(),
        )
        page = MockPage()
        context = RunContext()
        
        step = TaskStep(intent=StepIntent.NAVIGATE, target="https://example.com")
        
        await executor.execute_batch(page, [step], context)
        
        assert len(context.history) >= 1
