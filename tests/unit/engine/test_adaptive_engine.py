"""
Tests for the new adaptive engine components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from llm_web_agent.engine.task_planner import (
    TaskPlanner,
    ExecutionPlan,
    PlannedStep,
    ActionType,
    Locator,
    LocatorType,
)
from llm_web_agent.engine.site_profiler import SiteProfiler, SiteProfile
from llm_web_agent.engine.accessibility_resolver import AccessibilityResolver, ResolutionResult
from llm_web_agent.engine.selector_pattern_tracker import SelectorPatternTracker


# =============================================================================
# MOCK CLASSES
# =============================================================================

class MockLLMResponse:
    def __init__(self, content: str):
        self.content = content


class MockLLMProvider:
    def __init__(self, response: str):
        self._response = response
    
    async def complete(self, messages, temperature=0.7):
        return MockLLMResponse(self._response)


class MockLocator:
    def __init__(self, count: int = 1, visible: bool = True):
        self._count = count
        self._visible = visible
        self.first = self
    
    async def count(self):
        return self._count
    
    async def is_visible(self):
        return self._visible
    
    def nth(self, i):
        return self
    
    async def click(self):
        pass
    
    async def fill(self, value: str):
        pass


class MockPage:
    def __init__(self, url: str = "https://example.com", title: str = "Test Page"):
        self._url = url
        self._title = title
        self._locators = {}
    
    @property
    def url(self):
        return self._url
    
    async def title(self):
        return self._title
    
    async def evaluate(self, script):
        if "selectorPriorities" in script:
            return {
                'framework': 'react',
                'rootSelector': '#root',
                'selectorPriorities': ['testid', 'role', 'text'],
                'usesShadowDom': False,
                'needsHydrationWait': True,
                'detectionConfidence': 0.85,
            }
        return {'elements': [], 'hasTestIds': True, 'hasAriaLabels': True}
    
    def get_by_test_id(self, testid: str):
        return self._locators.get(f'testid:{testid}', MockLocator(count=0))
    
    def get_by_role(self, role: str, name: str = None):
        key = f'role:{role}:{name}' if name else f'role:{role}'
        return self._locators.get(key, MockLocator(count=0))
    
    def get_by_text(self, text: str, exact: bool = False):
        return self._locators.get(f'text:{text}', MockLocator(count=0))
    
    def get_by_label(self, label: str):
        return self._locators.get(f'label:{label}', MockLocator(count=0))
    
    def get_by_placeholder(self, placeholder: str):
        return self._locators.get(f'placeholder:{placeholder}', MockLocator(count=0))
    
    def locator(self, selector: str):
        return self._locators.get(f'css:{selector}', MockLocator(count=0))
    
    def set_locator(self, key: str, locator: MockLocator):
        self._locators[key] = locator


# =============================================================================
# TASK PLANNER TESTS
# =============================================================================

class TestTaskPlanner:
    """Tests for TaskPlanner."""
    
    @pytest.mark.asyncio
    async def test_plan_simple_navigation(self):
        """Test planning a simple navigation task."""
        llm_response = '''
        {
            "steps": [
                {
                    "action": "navigate",
                    "target": "https://google.com",
                    "locators": [],
                    "value": "https://google.com"
                }
            ],
            "framework_hints": [],
            "recommended_strategy": null
        }
        '''
        llm = MockLLMProvider(llm_response)
        planner = TaskPlanner(llm)
        page = MockPage()
        
        plan = await planner.plan(page, "go to google.com")
        
        assert len(plan.steps) == 1
        assert plan.steps[0].action == ActionType.NAVIGATE
    
    @pytest.mark.asyncio
    async def test_plan_click_action(self):
        """Test planning a click action."""
        llm_response = '''
        {
            "steps": [
                {
                    "action": "click",
                    "target": "Login button",
                    "locators": [
                        {"type": "testid", "value": "login-btn"},
                        {"type": "role", "value": "button", "name": "Login"},
                        {"type": "text", "value": "Login"}
                    ]
                }
            ],
            "framework_hints": ["react"],
            "recommended_strategy": "testid"
        }
        '''
        llm = MockLLMProvider(llm_response)
        planner = TaskPlanner(llm)
        page = MockPage()
        
        plan = await planner.plan(page, "click the login button")
        
        assert len(plan.steps) == 1
        assert plan.steps[0].action == ActionType.CLICK
        assert len(plan.steps[0].locators) == 3
        assert plan.steps[0].locators[0].type == LocatorType.TESTID
        assert plan.framework_hints == ["react"]
    
    @pytest.mark.asyncio
    async def test_plan_multi_step(self):
        """Test planning multiple steps."""
        llm_response = '''
        {
            "steps": [
                {"action": "navigate", "target": "example.com", "locators": [], "value": "https://example.com"},
                {"action": "fill", "target": "Email field", "locators": [{"type": "label", "value": "Email"}], "value": "test@example.com"},
                {"action": "click", "target": "Submit button", "locators": [{"type": "role", "value": "button", "name": "Submit"}]}
            ],
            "framework_hints": [],
            "recommended_strategy": null
        }
        '''
        llm = MockLLMProvider(llm_response)
        planner = TaskPlanner(llm)
        page = MockPage()
        
        plan = await planner.plan(page, "go to example.com, enter email, submit")
        
        assert len(plan.steps) == 3
        assert plan.steps[1].action == ActionType.FILL
        assert plan.steps[1].value == "test@example.com"
    
    def test_fallback_step_navigation(self):
        """Test fallback step creation for navigation."""
        planner = TaskPlanner(MagicMock())
        
        steps = planner._parse_fallback_steps("go to google.com")
        
        assert len(steps) == 1
        assert steps[0].action == ActionType.NAVIGATE
        assert "google.com" in steps[0].value or "google.com" in steps[0].target


# =============================================================================
# SITE PROFILER TESTS
# =============================================================================

class TestSiteProfiler:
    """Tests for SiteProfiler."""
    
    @pytest.mark.asyncio
    async def test_detect_react_site(self):
        """Test detecting a React site."""
        profiler = SiteProfiler(cache_path="/tmp/test_profiles.json")
        page = MockPage(url="https://react-app.example.com")
        
        profile = await profiler.get_profile(page)
        
        assert profile.framework == 'react'
        assert profile.needs_hydration_wait is True
        assert 'testid' in profile.selector_priorities
    
    @pytest.mark.asyncio
    async def test_profile_caching(self):
        """Test that profiles are cached."""
        profiler = SiteProfiler(cache_path="/tmp/test_profiles.json")
        page = MockPage(url="https://cached.example.com")
        
        # First call - detection
        profile1 = await profiler.get_profile(page)
        
        # Second call - should use cache
        profile2 = await profiler.get_profile(page)
        
        assert profile1.domain == profile2.domain
    
    def test_update_priority_on_success(self):
        """Test priority update when selector type succeeds."""
        profiler = SiteProfiler(cache_path="/tmp/test_profiles.json")
        
        # Create a profile
        profiler._profiles["example.com"] = SiteProfile(
            domain="example.com",
            selector_priorities=['text', 'role', 'testid']
        )
        
        # Record success for testid (currently last)
        profiler.update_priority("example.com", "testid", success=True)
        
        # testid should move up
        profile = profiler._profiles["example.com"]
        testid_idx = profile.selector_priorities.index("testid")
        assert testid_idx < 2  # Should be closer to front


# =============================================================================
# ACCESSIBILITY RESOLVER TESTS
# =============================================================================

class TestAccessibilityResolver:
    """Tests for AccessibilityResolver."""
    
    @pytest.mark.asyncio
    async def test_resolve_by_testid(self):
        """Test resolution using data-testid."""
        resolver = AccessibilityResolver()
        page = MockPage()
        page.set_locator("testid:login-btn", MockLocator(count=1, visible=True))
        
        locators = [Locator(type=LocatorType.TESTID, value="login-btn")]
        result = await resolver.resolve(page, locators, None, "Login button")
        
        assert result.success is True
        assert result.locator_type == LocatorType.TESTID
    
    @pytest.mark.asyncio
    async def test_resolve_fallback_to_role(self):
        """Test fallback from testid to role."""
        resolver = AccessibilityResolver()
        page = MockPage()
        # testid not found, but role works
        page.set_locator("role:button:Login", MockLocator(count=1, visible=True))
        
        locators = [
            Locator(type=LocatorType.TESTID, value="login-btn"),
            Locator(type=LocatorType.ROLE, value="button", name="Login"),
        ]
        result = await resolver.resolve(page, locators, None, "Login button")
        
        assert result.success is True
        assert result.locator_type == LocatorType.ROLE
    
    @pytest.mark.asyncio
    async def test_resolve_no_match(self):
        """Test when no locator matches."""
        resolver = AccessibilityResolver()
        page = MockPage()  # No locators set
        
        locators = [Locator(type=LocatorType.TESTID, value="nonexistent")]
        result = await resolver.resolve(page, locators, None, "Missing element")
        
        assert result.success is False
    
    def test_confidence_scoring(self):
        """Test confidence scores for different locator types."""
        resolver = AccessibilityResolver()
        
        # testid should have highest confidence
        assert resolver._get_confidence(LocatorType.TESTID) > resolver._get_confidence(LocatorType.CSS)
        assert resolver._get_confidence(LocatorType.ROLE) > resolver._get_confidence(LocatorType.TEXT)


# =============================================================================
# SELECTOR PATTERN TRACKER TESTS
# =============================================================================

class TestSelectorPatternTracker:
    """Tests for SelectorPatternTracker."""
    
    def test_record_success(self):
        """Test recording a successful resolution."""
        tracker = SelectorPatternTracker(cache_path="/tmp/test_patterns.json")
        
        tracker.record_success(
            domain="example.com",
            target="Login button",
            locator_type="testid",
            selector="[data-testid='login-btn']"
        )
        
        # Should have exact match cached
        cached = tracker.get_exact_match("example.com", "Login button")
        assert cached == "[data-testid='login-btn']"
    
    def test_suggest_from_pattern(self):
        """Test getting suggestions based on learned patterns."""
        tracker = SelectorPatternTracker(cache_path="/tmp/test_patterns.json")
        
        # Record success for login
        tracker.record_success(
            domain="example.com",
            target="Login button",
            locator_type="testid",
            selector="[data-testid='login-btn']"
        )
        
        # Suggest for signup (similar pattern)
        suggestions = tracker.suggest("example.com", "Signup button")
        
        # Should suggest testid since button pattern learned
        assert len(suggestions) > 0
        assert any(s[0] == "testid" for s in suggestions)
    
    def test_extract_keywords(self):
        """Test keyword extraction."""
        tracker = SelectorPatternTracker(cache_path="/tmp/test_patterns.json")
        
        keywords = tracker._extract_keywords("Click the Login Button")
        
        assert "login" in keywords
        assert "button" in keywords
        assert "the" not in keywords  # stopword filtered
    
    def test_domain_stats(self):
        """Test getting domain statistics."""
        tracker = SelectorPatternTracker(cache_path="/tmp/test_patterns.json")
        
        # Record some interactions
        tracker.record_success("example.com", "Button 1", "testid", "sel1")
        tracker.record_success("example.com", "Button 2", "testid", "sel2")
        
        stats = tracker.get_domain_stats("example.com")
        
        assert stats is not None
        assert stats["total_resolutions"] == 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the adaptive pipeline."""
    
    @pytest.mark.asyncio
    async def test_planning_to_resolution(self):
        """Test the flow from planning to resolution."""
        # Setup
        llm_response = '''
        {
            "steps": [
                {
                    "action": "click",
                    "target": "Login button",
                    "locators": [
                        {"type": "testid", "value": "login-btn"},
                        {"type": "role", "value": "button", "name": "Login"}
                    ]
                }
            ],
            "framework_hints": ["react"],
            "recommended_strategy": "testid"
        }
        '''
        
        llm = MockLLMProvider(llm_response)
        planner = TaskPlanner(llm)
        resolver = AccessibilityResolver()
        
        page = MockPage()
        page.set_locator("testid:login-btn", MockLocator(count=1, visible=True))
        
        # Plan
        plan = await planner.plan(page, "click login")
        
        assert len(plan.steps) == 1
        step = plan.steps[0]
        
        # Resolve
        result = await resolver.resolve(page, step.locators, None, step.target)
        
        assert result.success is True
        assert result.locator_type == LocatorType.TESTID
