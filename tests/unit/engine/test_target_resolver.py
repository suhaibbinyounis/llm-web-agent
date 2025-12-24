"""
Tests for TargetResolver - multi-strategy element resolution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_web_agent.engine.target_resolver import (
    TargetResolver,
    ResolvedTarget,
    ResolutionStrategy,
    ResolutionLayer,  # Alias for backwards compat
    resolve_multiple,
)


# =============================================================================
# MOCK FIXTURES
# =============================================================================

class MockElement:
    """Mock browser element."""
    
    def __init__(
        self,
        text: str = "",
        attrs: dict = None,
        visible: bool = True,
    ):
        self._text = text
        self._attrs = attrs or {}
        self._visible = visible
    
    async def text_content(self) -> str:
        return self._text
    
    async def get_attribute(self, name: str):
        return self._attrs.get(name)
    
    async def is_visible(self) -> bool:
        return self._visible
    
    async def evaluate(self, script: str):
        if "tagName" in script:
            return self._attrs.get("_tag", "button")
        if "getSelector" in script:
            return f"#{self._attrs.get('id', 'elem')}"
        return None


class MockPage:
    """Mock browser page."""
    
    def __init__(self, elements: dict = None):
        self._elements = elements or {}
        self._url = "https://example.com"
    
    @property
    def url(self) -> str:
        return self._url
    
    async def title(self) -> str:
        return "Test Page"
    
    async def query_selector(self, selector: str):
        # Support both exact and partial matching
        if selector in self._elements:
            return self._elements[selector]
        # Try to find any matching selector
        for key, elem in self._elements.items():
            if selector in key or key in selector:
                return elem
        return None
    
    async def query_selector_all(self, selector: str):
        return list(self._elements.values())
    
    async def evaluate(self, script, *args):
        return []
    
    async def wait_for_selector(self, selector: str, **kwargs):
        return self._elements.get(selector)


# =============================================================================
# TESTS
# =============================================================================

class TestResolvedTarget:
    """Test ResolvedTarget dataclass."""
    
    def test_is_resolved_true(self):
        """Test is_resolved when resolved."""
        target = ResolvedTarget(
            selector="#button",
            strategy=ResolutionStrategy.DIRECT,
            confidence=1.0,
        )
        
        assert target.is_resolved is True
    
    def test_is_resolved_false_when_failed(self):
        """Test is_resolved when failed."""
        target = ResolvedTarget(
            selector="",
            strategy=ResolutionStrategy.FAILED,
            confidence=0,
        )
        
        assert target.is_resolved is False
    
    def test_alternatives(self):
        """Test alternatives list."""
        target = ResolvedTarget(
            selector="#btn1",
            strategy=ResolutionStrategy.FUZZY,
            alternatives=["#btn2", "#btn3"],
        )
        
        assert len(target.alternatives) == 2
    
    def test_layer_alias(self):
        """Test layer property for backwards compat."""
        target = ResolvedTarget(
            selector="#btn",
            strategy=ResolutionStrategy.DIRECT,
        )
        
        assert target.layer == target.strategy


class TestResolutionStrategyAliases:
    """Test strategy enum aliases."""
    
    def test_resolution_layer_alias(self):
        """Test ResolutionLayer is an alias for ResolutionStrategy."""
        assert ResolutionLayer is ResolutionStrategy
    
    def test_exact_alias(self):
        """Test EXACT is an alias for DIRECT."""
        assert ResolutionStrategy.EXACT.value == ResolutionStrategy.DIRECT.value
    
    def test_text_alias(self):
        """Test TEXT is an alias for TEXT_FIRST."""
        assert ResolutionStrategy.TEXT.value == ResolutionStrategy.TEXT_FIRST.value


class TestDirectSelector:
    """Test direct selector matching."""
    
    @pytest.mark.asyncio
    async def test_match_by_id(self):
        """Test matching by ID selector."""
        element = MockElement(attrs={"id": "login-btn"})
        page = MockPage({"#login-btn": element})
        
        resolver = TargetResolver(enable_indexing=False)
        result = await resolver.resolve(page, "#login-btn")
        
        assert result.is_resolved is True
        assert result.selector == "#login-btn"


class TestResolverIntegration:
    """Integration tests for full resolution flow."""
    
    @pytest.mark.asyncio
    async def test_full_resolution_flow(self):
        """Test complete resolution flow."""
        element = MockElement(
            text="Sign In",
            attrs={"id": "signin-btn"},
            visible=True,
        )
        page = MockPage({"#signin-btn": element})
        
        resolver = TargetResolver(enable_indexing=False)
        result = await resolver.resolve(page, "#signin-btn", intent="click")
        
        assert result.is_resolved is True
        assert result.selector == "#signin-btn"
    
    @pytest.mark.asyncio
    async def test_resolution_fails_gracefully(self):
        """Test resolution fails gracefully when not found."""
        page = MockPage({})
        
        resolver = TargetResolver(enable_indexing=False)
        result = await resolver.resolve(page, "nonexistent element xyz")
        
        assert result.is_resolved is False
        assert result.strategy == ResolutionStrategy.FAILED
        assert result.confidence == 1.0  # Default confidence
    
    @pytest.mark.asyncio
    async def test_empty_target(self):
        """Test empty target fails immediately."""
        page = MockPage({})
        
        resolver = TargetResolver(enable_indexing=False)
        result = await resolver.resolve(page, "")
        
        assert result.is_resolved is False


class TestResolveMultiple:
    """Test resolving multiple targets."""
    
    @pytest.mark.asyncio
    async def test_resolve_multiple_targets(self):
        """Test resolving multiple targets at once."""
        elem1 = MockElement(attrs={"id": "email"})
        elem2 = MockElement(attrs={"id": "password"})
        page = MockPage({
            "#email": elem1,
            "[name='email']": elem1,
            "#password": elem2,
            "[name='password']": elem2,
        })
        
        resolver = TargetResolver(enable_indexing=False)
        targets = {
            "email_field": "#email",
            "password_field": "#password",
        }
        
        results = await resolve_multiple(resolver, page, targets, intent="fill")
        
        assert "email_field" in results
        assert "password_field" in results
