"""
Tests for TargetResolver - multi-layer element resolution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_web_agent.engine.target_resolver import (
    TargetResolver,
    ResolvedTarget,
    ResolutionLayer,
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
        return self._elements.get(selector)
    
    async def query_selector_all(self, selector: str):
        return list(self._elements.values())
    
    async def evaluate(self, script: str):
        return []


# =============================================================================
# TESTS
# =============================================================================

class TestResolvedTarget:
    """Test ResolvedTarget dataclass."""
    
    def test_is_resolved_true(self):
        """Test is_resolved when resolved."""
        target = ResolvedTarget(
            selector="#button",
            layer=ResolutionLayer.EXACT,
            confidence=1.0,
        )
        
        assert target.is_resolved is True
    
    def test_is_resolved_false_when_failed(self):
        """Test is_resolved when failed."""
        target = ResolvedTarget(
            selector="",
            layer=ResolutionLayer.FAILED,
            confidence=0,
        )
        
        assert target.is_resolved is False
    
    def test_alternatives(self):
        """Test alternatives list."""
        target = ResolvedTarget(
            selector="#btn1",
            layer=ResolutionLayer.FUZZY,
            alternatives=["#btn2", "#btn3"],
        )
        
        assert len(target.alternatives) == 2


class TestExactMatch:
    """Test exact match resolution layer."""
    
    @pytest.mark.asyncio
    async def test_match_by_id(self):
        """Test matching by ID selector."""
        element = MockElement(attrs={"id": "login-btn"})
        page = MockPage({"#login-btn": element})
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "#login-btn")
        
        assert result.is_resolved is True
        assert result.layer == ResolutionLayer.EXACT
        assert result.selector == "#login-btn"
    
    @pytest.mark.asyncio
    async def test_match_by_data_testid(self):
        """Test matching by data-testid."""
        element = MockElement(attrs={"data-testid": "submit"})
        page = MockPage({"[data-testid='submit']": element})
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "submit")
        
        assert result.is_resolved is True
        assert result.selector == "[data-testid='submit']"
    
    @pytest.mark.asyncio
    async def test_match_by_name(self):
        """Test matching by name attribute."""
        element = MockElement(attrs={"name": "email"})
        page = MockPage({"[name='email']": element})
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "email")
        
        assert result.is_resolved is True
        assert result.selector == "[name='email']"
    
    @pytest.mark.asyncio
    async def test_no_exact_match(self):
        """Test when no exact match exists."""
        page = MockPage({})
        
        resolver = TargetResolver()
        result = await resolver._try_exact_match(page, "nonexistent")
        
        assert result.is_resolved is False


class TestTextMatch:
    """Test text match resolution layer."""
    
    @pytest.mark.asyncio
    async def test_match_by_text(self):
        """Test matching by text content."""
        element = MockElement(text="Login", visible=True)
        page = MockPage({"text='Login'": element})
        
        resolver = TargetResolver()
        result = await resolver._try_text_match(page, "Login")
        
        assert result.is_resolved is True
        assert result.layer == ResolutionLayer.TEXT
    
    @pytest.mark.asyncio
    async def test_no_text_match(self):
        """Test when no text match exists."""
        page = MockPage({})
        
        resolver = TargetResolver()
        result = await resolver._try_text_match(page, "Nonexistent")
        
        assert result.is_resolved is False


class TestFuzzyMatch:
    """Test fuzzy match resolution layer."""
    
    @pytest.mark.asyncio
    async def test_fuzzy_match_word_overlap(self):
        """Test fuzzy matching with word overlap."""
        element = MockElement(
            text="Submit Form",
            attrs={"id": "submit-btn", "aria-label": "Submit the form"},
            visible=True,
        )
        page = MockPage({"button": element})
        
        resolver = TargetResolver(fuzzy_threshold=0.5)
        result = await resolver._try_fuzzy_match(page, "submit form button")
        
        assert result.is_resolved is True
        assert result.layer == ResolutionLayer.FUZZY
        assert result.confidence >= 0.5
    
    @pytest.mark.asyncio
    async def test_fuzzy_match_scores_candidates(self):
        """Test fuzzy matching scores multiple candidates."""
        elem1 = MockElement(text="Login", attrs={"id": "login"}, visible=True)
        elem2 = MockElement(text="Login to Account", attrs={"id": "login-full"}, visible=True)
        
        page = MockPage({"#login": elem1, "#login-full": elem2})
        
        resolver = TargetResolver(fuzzy_threshold=0.5)
        result = await resolver._try_fuzzy_match(page, "Login")
        
        # Should find a match
        assert result.is_resolved is True


class TestSimilarityScore:
    """Test similarity scoring function."""
    
    def test_exact_substring_match(self):
        """Test exact substring gives high score."""
        resolver = TargetResolver()
        
        score = resolver._similarity_score("login", "login button")
        
        assert score >= 0.9
    
    def test_word_overlap(self):
        """Test word overlap scoring."""
        resolver = TargetResolver()
        
        score = resolver._similarity_score("submit form", "form submit button")
        
        assert score >= 0.6
    
    def test_no_overlap(self):
        """Test no overlap gives zero."""
        resolver = TargetResolver()
        
        score = resolver._similarity_score("login", "register signup")
        
        assert score == 0.0
    
    def test_empty_strings(self):
        """Test empty strings give zero."""
        resolver = TargetResolver()
        
        assert resolver._similarity_score("", "text") == 0.0
        assert resolver._similarity_score("text", "") == 0.0


class TestInferElementTypes:
    """Test element type inference."""
    
    def test_click_intent_infers_button_link(self):
        """Test click intent infers button and link."""
        resolver = TargetResolver()
        
        types = resolver._infer_element_types("some target", "click")
        
        assert "button" in types
        assert "link" in types
    
    def test_fill_intent_infers_input(self):
        """Test fill intent infers input."""
        resolver = TargetResolver()
        
        types = resolver._infer_element_types("email field", "fill")
        
        assert "input" in types
    
    def test_keyword_button(self):
        """Test button keyword in target."""
        resolver = TargetResolver()
        
        types = resolver._infer_element_types("login button")
        
        assert "button" in types
    
    def test_keyword_search(self):
        """Test search keyword in target."""
        resolver = TargetResolver()
        
        types = resolver._infer_element_types("search box")
        
        assert "search" in types


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
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "#signin-btn", intent="click")
        
        assert result.is_resolved is True
        assert result.selector == "#signin-btn"
    
    @pytest.mark.asyncio
    async def test_fallback_chain(self):
        """Test resolution falls through layers."""
        # No exact match, should try text, fuzzy, etc.
        element = MockElement(text="Login Button", visible=True)
        page = MockPage({"text='Login Button'": element})
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "Login Button")
        
        # Should eventually find via text layer
        assert result.is_resolved is True
    
    @pytest.mark.asyncio
    async def test_resolution_fails_gracefully(self):
        """Test resolution fails gracefully when not found."""
        page = MockPage({})
        
        resolver = TargetResolver()
        result = await resolver.resolve(page, "nonexistent element xyz")
        
        assert result.is_resolved is False
        assert result.layer == ResolutionLayer.FAILED
        assert result.confidence == 0
    
    @pytest.mark.asyncio
    async def test_empty_target(self):
        """Test empty target fails immediately."""
        page = MockPage({})
        
        resolver = TargetResolver()
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
        
        resolver = TargetResolver()
        targets = {
            "email_field": "email",
            "password_field": "password",
        }
        
        results = await resolve_multiple(resolver, page, targets, intent="fill")
        
        assert "email_field" in results
        assert "password_field" in results
