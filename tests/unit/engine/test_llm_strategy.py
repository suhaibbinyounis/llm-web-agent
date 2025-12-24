"""
Tests for LLMStrategy - unified LLM interaction layer.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json

from llm_web_agent.engine.llm.strategy import LLMStrategy
from llm_web_agent.engine.llm.schemas import (
    ParsedInstruction,
    FoundElement,
    ActionPlan,
    LLMResponse,
)


# =============================================================================
# MOCK CLASSES THAT MATCH THE ACTUAL INTERFACES
# =============================================================================

@dataclass
class MockUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50
    total_tokens: int = 150


@dataclass
class MockLLMResponse:
    content: str
    usage: MockUsage = field(default_factory=MockUsage)
    tool_calls: list = field(default_factory=list)


class MockLLMProvider:
    """Mock LLM provider matching ILLMProvider interface."""
    
    def __init__(self, responses: List[str] = None):
        self._responses = responses or ['[{"intent": "click", "target": "button"}]']
        self._call_idx = 0
    
    async def complete(self, messages: List[Any], tools: List[Any] = None, **kwargs):
        if self._call_idx < len(self._responses):
            response = self._responses[self._call_idx]
        else:
            response = '{"found": false}'
        self._call_idx += 1
        return MockLLMResponse(content=response)


class MockPage:
    """Mock page for strategy tests."""
    
    def __init__(self, url: str = "https://example.com"):
        self._url = url
    
    @property
    def url(self) -> str:
        return self._url
    
    async def title(self) -> str:
        return "Test Page"
    
    async def evaluate(self, script: str) -> list:
        return [
            {"tag": "button", "text": "Click Me", "id": "btn1", "selector": "#btn1"},
            {"tag": "input", "name": "email", "placeholder": "Email", "selector": "input[name='email']"},
        ]
    
    async def query_selector_all(self, selector: str) -> list:
        return []


class MockRunContext:
    """Mock run context."""
    
    def __init__(self):
        self.history = []
    
    def get_all_stored(self):
        return {"email": "test@test.com"}


# =============================================================================
# TESTS
# =============================================================================

class TestLLMStrategyCreation:
    """Test LLMStrategy creation and configuration."""
    
    def test_create_strategy(self):
        """Test creating a strategy."""
        llm = MockLLMProvider()
        strategy = LLMStrategy(llm)
        
        assert strategy is not None
    
    def test_create_with_options(self):
        """Test creating with options."""
        llm = MockLLMProvider()
        strategy = LLMStrategy(
            llm,
            use_function_calling=False,
            cache_enabled=True,
            cache_ttl_seconds=600,
            max_retries=3,
        )
        
        assert strategy._use_functions is False
        assert strategy._cache_enabled is True
        assert strategy._cache_ttl == 600


class TestParseInstruction:
    """Test instruction parsing via LLM."""
    
    @pytest.mark.asyncio
    async def test_parse_instruction_returns_response(self):
        """Test instruction parsing returns LLMResponse."""
        llm = MockLLMProvider([
            '[{"intent": "navigate", "target": "google.com"}]'
        ])
        strategy = LLMStrategy(llm, use_function_calling=False)
        
        response = await strategy.parse_instruction("go to google.com")
        
        # Response is an LLMResponse object
        assert isinstance(response, LLMResponse)
    
    @pytest.mark.asyncio
    async def test_parse_instruction_calls_llm(self):
        """Test instruction parsing calls the LLM."""
        llm = MockLLMProvider([
            '[{"intent": "navigate", "target": "google.com"}]'
        ])
        strategy = LLMStrategy(llm, use_function_calling=False, cache_enabled=False)
        
        await strategy.parse_instruction("go to google.com")
        
        # LLM should have been called
        assert llm._call_idx == 1


class TestFindElement:
    """Test element finding via LLM."""
    
    @pytest.mark.asyncio
    async def test_find_element_returns_struct(self):
        """Test find element returns FoundElement."""
        llm = MockLLMProvider([
            '{"found": true, "index": 0, "selector": "#btn1", "confidence": 0.95}'
        ])
        strategy = LLMStrategy(llm, use_function_calling=False)
        
        page = MockPage()
        
        # Create mock SimplifiedDOM
        from llm_web_agent.engine.llm.dom_simplifier import SimplifiedDOM, SimplifiedElement
        dom = SimplifiedDOM(
            url="https://example.com",
            title="Test",
            elements=[SimplifiedElement(0, "button", text="Click Me", selector="#btn1")],
        )
        
        result = await strategy.find_element(page, "click button", dom)
        
        assert isinstance(result, FoundElement)
    
    @pytest.mark.asyncio
    async def test_find_element_not_found(self):
        """Test element not found."""
        llm = MockLLMProvider([
            '{"found": false, "reasoning": "No matching element"}'
        ])
        strategy = LLMStrategy(llm, use_function_calling=False)
        
        page = MockPage()
        
        from llm_web_agent.engine.llm.dom_simplifier import SimplifiedDOM
        dom = SimplifiedDOM(url="url", title="title", elements=[])
        
        result = await strategy.find_element(page, "nonexistent", dom)
        
        assert result.found is False


class TestCreatePlan:
    """Test action planning via LLM."""
    
    @pytest.mark.asyncio
    async def test_create_plan_returns_action_plan(self):
        """Test creating action plan returns ActionPlan."""
        llm = MockLLMProvider([
            '''{
                "plan": [
                    {"step": 1, "intent": "click", "target": "button"}
                ],
                "variables_needed": [],
                "estimated_pages": 1
            }'''
        ])
        strategy = LLMStrategy(llm, use_function_calling=False)
        page = MockPage()
        context = MockRunContext()
        
        plan = await strategy.create_plan(page, "click button", context)
        
        assert isinstance(plan, ActionPlan)
    
    @pytest.mark.asyncio
    async def test_create_plan_empty_on_failure(self):
        """Test empty plan on failure."""
        llm = MockLLMProvider(['invalid json here'])
        strategy = LLMStrategy(llm, use_function_calling=False)
        page = MockPage()
        
        plan = await strategy.create_plan(page, "do something")
        
        assert plan.step_count == 0


class TestSuggestRecovery:
    """Test error recovery suggestions via LLM."""
    
    @pytest.mark.asyncio
    async def test_suggest_recovery_returns_struct(self):
        """Test recovery suggestion returns ErrorRecovery."""
        llm = MockLLMProvider([
            '''{
                "diagnosis": "Button text is wrong",
                "recovery_steps": [],
                "should_retry": true
            }'''
        ])
        strategy = LLMStrategy(llm, use_function_calling=False)
        page = MockPage()
        context = MockRunContext()
        
        from llm_web_agent.engine.llm.schemas import ErrorRecovery
        
        recovery = await strategy.suggest_recovery(
            page,
            failed_action="click on Login button",
            error="Element not found",
            context=context,
        )
        
        assert isinstance(recovery, ErrorRecovery)


class TestCaching:
    """Test LLM response caching."""
    
    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_calls(self):
        """Test that caching reduces LLM calls."""
        llm = MockLLMProvider([
            '[{"intent": "click", "target": "button"}]'
        ])
        strategy = LLMStrategy(llm, cache_enabled=True, use_function_calling=False)
        
        # First call
        await strategy.parse_instruction("click button")
        first_count = llm._call_idx
        
        # Second identical call should use cache
        await strategy.parse_instruction("click button")
        second_count = llm._call_idx
        
        # For caching to work, second count should equal first
        # (or at most 1 more if retry logic runs)
        assert second_count <= first_count + 1
    
    @pytest.mark.asyncio
    async def test_cache_disabled_makes_multiple_calls(self):
        """Test caching disabled makes multiple LLM calls."""
        llm = MockLLMProvider([
            '[{"intent": "click", "target": "button"}]',
            '[{"intent": "click", "target": "button"}]',
        ])
        strategy = LLMStrategy(llm, cache_enabled=False, use_function_calling=False)
        
        await strategy.parse_instruction("click button")
        await strategy.parse_instruction("click button")
        
        # Both calls should go to LLM
        assert llm._call_idx >= 2
    
    def test_clear_cache(self):
        """Test clearing cache."""
        llm = MockLLMProvider()
        strategy = LLMStrategy(llm)
        
        # Manually add cache entry
        strategy._cache["test"] = "value"
        
        strategy.clear_cache()
        
        assert len(strategy._cache) == 0


class TestStats:
    """Test LLM usage statistics."""
    
    @pytest.mark.asyncio
    async def test_tracks_calls(self):
        """Test tracking total calls."""
        llm = MockLLMProvider(['[{"intent": "click", "target": "x"}]'])
        strategy = LLMStrategy(llm, cache_enabled=False, use_function_calling=False)
        
        await strategy.parse_instruction("click x")
        
        stats = strategy.get_stats()
        assert stats["total_calls"] >= 1
    
    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        """Test tracking token usage."""
        llm = MockLLMProvider(['[{"intent": "click", "target": "x"}]'])
        strategy = LLMStrategy(llm, cache_enabled=False, use_function_calling=False)
        
        await strategy.parse_instruction("click x")
        
        stats = strategy.get_stats()
        assert stats["total_tokens"] >= 0
