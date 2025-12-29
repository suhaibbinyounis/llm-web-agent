"""
Test fixtures for engine module tests.
"""

import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from dataclasses import dataclass


# =============================================================================
# MOCK BROWSER PAGE
# =============================================================================

class MockElement:
    """Mock browser element for testing."""
    
    def __init__(
        self,
        tag: str = "button",
        text: str = "",
        attrs: Optional[Dict[str, str]] = None,
        visible: bool = True,
    ):
        self.tag = tag
        self._text = text
        self._attrs = attrs or {}
        self._visible = visible
    
    async def text_content(self) -> str:
        return self._text
    
    async def get_attribute(self, name: str) -> Optional[str]:
        return self._attrs.get(name)
    
    async def is_visible(self) -> bool:
        return self._visible
    
    async def click(self) -> None:
        pass
    
    async def fill(self, value: str) -> None:
        self._attrs["value"] = value
    
    async def evaluate(self, script: str) -> Any:
        if "tagName" in script:
            return self.tag
        if "getSelector" in script:
            if self._attrs.get("id"):
                return f"#{self._attrs['id']}"
            return f"{self.tag}"
        return None


class MockPage:
    """Mock browser page for testing."""
    
    def __init__(
        self,
        url: str = "https://example.com",
        title: str = "Example Page",
        elements: Optional[List[MockElement]] = None,
    ):
        self._url = url
        self._title = title
        self._elements = elements or []
        self._element_map: Dict[str, MockElement] = {}
        
        # Build element map for selectors
        for elem in self._elements:
            if elem._attrs.get("id"):
                self._element_map[f"#{elem._attrs['id']}"] = elem
            if elem._attrs.get("name"):
                self._element_map[f"[name='{elem._attrs['name']}']"] = elem
            if elem._attrs.get("data-testid"):
                self._element_map[f"[data-testid='{elem._attrs['data-testid']}']"] = elem
    
    @property
    def url(self) -> str:
        return self._url
    
    async def title(self) -> str:
        return self._title
    
    async def goto(self, url: str, **kwargs) -> None:
        self._url = url
    
    async def query_selector(self, selector: str) -> Optional[MockElement]:
        # Check exact match first
        if selector in self._element_map:
            return self._element_map[selector]
        
        # Check text selectors
        if selector.startswith("text="):
            text = selector[5:].strip("'\"")
            for elem in self._elements:
                if text.lower() in elem._text.lower():
                    return elem
        
        # Check tag selectors
        for elem in self._elements:
            if elem.tag == selector:
                return elem
        
        return None
    
    async def query_selector_all(self, selector: str) -> List[MockElement]:
        results = []
        for elem in self._elements:
            if elem.tag in selector:
                results.append(elem)
        return results
    
    async def click(self, selector: str) -> None:
        elem = await self.query_selector(selector)
        if elem:
            await elem.click()
    
    async def fill(self, selector: str, value: str) -> None:
        elem = await self.query_selector(selector)
        if elem:
            await elem.fill(value)
    
    async def type(self, selector: str, value: str) -> None:
        await self.fill(selector, value)
    
    async def select_option(self, selector: str, value: str) -> None:
        pass
    
    async def hover(self, selector: str) -> None:
        pass
    
    async def evaluate(self, script: str, arg: Any = None) -> Any:
        if "scrollTo" in script or "scrollBy" in script:
            return None
        if "querySelectorAll" in script:
            return [
                {
                    "tag": e.tag,
                    "text": e._text,
                    "id": e._attrs.get("id"),
                    "name": e._attrs.get("name"),
                    "type": e._attrs.get("type"),
                    "placeholder": e._attrs.get("placeholder"),
                    "aria_label": e._attrs.get("aria-label"),
                    "role": e._attrs.get("role"),
                    "selector": f"#{e._attrs['id']}" if e._attrs.get("id") else e.tag,
                }
                for e in self._elements
            ]
        return None
    
    async def wait_for_load_state(self, state: str, timeout: int = 30000) -> None:
        pass
    
    async def wait_for_selector(self, selector: str, state: str = "visible", timeout: int = 30000) -> None:
        pass
    
    async def screenshot(self, path: str) -> None:
        pass
    
    @property
    def keyboard(self):
        return MockKeyboard()


class MockKeyboard:
    """Mock keyboard for testing."""
    
    async def press(self, key: str) -> None:
        pass


# =============================================================================
# MOCK LLM PROVIDER
# =============================================================================

@dataclass
class MockMessage:
    role: str
    content: str


@dataclass  
class MockUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50
    total_tokens: int = 150


@dataclass
class MockToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class MockLLMResponse:
    content: str
    usage: MockUsage = None
    tool_calls: List[MockToolCall] = None
    
    def __post_init__(self):
        if self.usage is None:
            self.usage = MockUsage()
        if self.tool_calls is None:
            self.tool_calls = []


class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, responses: Optional[List[str]] = None):
        self._responses = responses or []
        self._call_count = 0
        self._calls: List[List[MockMessage]] = []
    
    async def complete(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
        **kwargs,
    ) -> MockLLMResponse:
        self._calls.append(messages)
        
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
        else:
            response = '{"steps": []}'
        
        self._call_count += 1
        return MockLLMResponse(content=response)
    
    def get_call_count(self) -> int:
        return self._call_count
    
    def get_calls(self) -> List[List[MockMessage]]:
        return self._calls


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_page():
    """Create a mock page with common elements."""
    elements = [
        MockElement("button", "Login", {"id": "login-btn", "type": "submit"}),
        MockElement("button", "Sign Up", {"id": "signup-btn"}),
        MockElement("input", "", {"id": "email", "name": "email", "type": "email", "placeholder": "Enter email"}),
        MockElement("input", "", {"id": "password", "name": "password", "type": "password", "placeholder": "Password"}),
        MockElement("a", "Home", {"href": "/home"}),
        MockElement("a", "About", {"href": "/about"}),
        MockElement("input", "", {"id": "search", "name": "q", "type": "search", "placeholder": "Search..."}),
        MockElement("button", "Search", {"id": "search-btn", "aria-label": "Search"}),
    ]
    return MockPage(
        url="https://example.com/login",
        title="Login Page",
        elements=elements,
    )


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_responses():
    """Create a mock LLM provider factory with custom responses."""
    def create(responses: List[str]):
        return MockLLMProvider(responses)
    return create
