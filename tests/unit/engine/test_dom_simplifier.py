"""
Tests for DOMSimplifier - DOM extraction for LLM context.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from llm_web_agent.engine.llm.dom_simplifier import (
    DOMSimplifier,
    SimplifiedDOM,
    SimplifiedElement,
)


class TestSimplifiedElement:
    """Test SimplifiedElement dataclass."""
    
    def test_create_element(self):
        """Test creating a simplified element."""
        elem = SimplifiedElement(
            index=0,
            tag="button",
            text="Click Me",
            id="btn1",
        )
        
        assert elem.index == 0
        assert elem.tag == "button"
        assert elem.text == "Click Me"
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        elem = SimplifiedElement(
            index=0,
            tag="input",
            id="email",
            name="user_email",
            type="email",
            placeholder="Enter email",
        )
        
        d = elem.to_dict()
        
        assert d["index"] == 0
        assert d["tag"] == "input"
        assert d["id"] == "email"
        assert d["name"] == "user_email"
        assert d["type"] == "email"
        assert d["placeholder"] == "Enter email"
    
    def test_to_dict_excludes_none(self):
        """Test dict excludes None values."""
        elem = SimplifiedElement(index=0, tag="button")
        
        d = elem.to_dict()
        
        assert "id" not in d
        assert "name" not in d
    
    def test_to_dict_truncates_text(self):
        """Test dict truncates long text."""
        long_text = "A" * 200
        elem = SimplifiedElement(index=0, tag="p", text=long_text)
        
        d = elem.to_dict()
        
        assert len(d["text"]) <= 100
    
    def test_to_line(self):
        """Test converting to single line string."""
        elem = SimplifiedElement(
            index=5,
            tag="button",
            text="Submit",
            id="submit-btn",
            aria_label="Submit form",
        )
        
        line = elem.to_line()
        
        assert "[5]" in line
        assert "<button>" in line
        assert "id=submit-btn" in line
        assert "Submit" in line


class TestSimplifiedDOM:
    """Test SimplifiedDOM dataclass."""
    
    def test_create_dom(self):
        """Test creating simplified DOM."""
        dom = SimplifiedDOM(
            url="https://example.com",
            title="Test Page",
        )
        
        assert dom.url == "https://example.com"
        assert dom.title == "Test Page"
        assert dom.element_count == 0
    
    def test_element_count(self):
        """Test element count property."""
        dom = SimplifiedDOM(
            url="https://example.com",
            title="Test",
            elements=[
                SimplifiedElement(0, "button"),
                SimplifiedElement(1, "input"),
                SimplifiedElement(2, "a"),
            ],
        )
        
        assert dom.element_count == 3
    
    def test_get_element_by_index(self):
        """Test getting element by index."""
        elem = SimplifiedElement(5, "button", text="Click")
        dom = SimplifiedDOM(
            url="url",
            title="title",
            elements=[elem],
        )
        
        found = dom.get_element(5)
        
        assert found == elem
        assert found.text == "Click"
    
    def test_get_element_not_found(self):
        """Test getting non-existent element."""
        dom = SimplifiedDOM(url="url", title="title")
        
        found = dom.get_element(99)
        
        assert found is None
    
    def test_to_elements_list(self):
        """Test converting to list of dicts."""
        dom = SimplifiedDOM(
            url="url",
            title="title",
            elements=[
                SimplifiedElement(0, "button", text="A"),
                SimplifiedElement(1, "button", text="B"),
            ],
        )
        
        lst = dom.to_elements_list()
        
        assert len(lst) == 2
        assert lst[0]["text"] == "A"
        assert lst[1]["text"] == "B"
    
    def test_to_compact_string(self):
        """Test converting to compact string."""
        dom = SimplifiedDOM(
            url="https://example.com",
            title="Test Page",
            elements=[
                SimplifiedElement(0, "button", text="Click", id="btn"),
            ],
        )
        
        s = dom.to_compact_string()
        
        assert "URL: https://example.com" in s
        assert "Title: Test Page" in s
        assert "[0]" in s
        assert "<button>" in s
    
    def test_to_compact_string_truncates(self):
        """Test compact string truncates long lists."""
        elements = [SimplifiedElement(i, "button") for i in range(150)]
        dom = SimplifiedDOM(url="url", title="title", elements=elements)
        
        s = dom.to_compact_string(max_elements=50)
        
        assert "[49]" in s
        assert "[100]" not in s
        assert "more elements" in s


class TestDOMSimplifier:
    """Test DOMSimplifier functionality."""
    
    def test_create_simplifier(self):
        """Test creating simplifier."""
        simplifier = DOMSimplifier()
        
        assert simplifier is not None
    
    def test_create_with_options(self):
        """Test creating with options."""
        simplifier = DOMSimplifier(
            max_elements=100,
            include_text_content=False,
            max_text_length=50,
        )
        
        assert simplifier._max_elements == 100
        assert simplifier._include_text is False
        assert simplifier._max_text == 50


class TestDOMSimplifierSimplify:
    """Test DOMSimplifier.simplify() method."""
    
    @pytest.fixture
    def mock_page(self):
        """Create mock page."""
        page = MagicMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.evaluate = AsyncMock(return_value=[
            {
                "tag": "button",
                "text": "Login",
                "id": "login-btn",
                "name": None,
                "type": "submit",
                "placeholder": None,
                "aria_label": "Login button",
                "role": None,
                "href": None,
                "value": None,
                "selector": "#login-btn",
            },
            {
                "tag": "input",
                "text": "",
                "id": "email",
                "name": "email",
                "type": "email",
                "placeholder": "Enter email",
                "aria_label": None,
                "role": None,
                "href": None,
                "value": "",
                "selector": "#email",
            },
        ])
        return page
    
    @pytest.mark.asyncio
    async def test_simplify_extracts_elements(self, mock_page):
        """Test simplify extracts interactive elements."""
        simplifier = DOMSimplifier()
        
        dom = await simplifier.simplify(mock_page)
        
        assert dom.url == "https://example.com"
        assert dom.title == "Test Page"
        assert dom.element_count == 2
    
    @pytest.mark.asyncio
    async def test_simplify_creates_elements(self, mock_page):
        """Test simplify creates SimplifiedElement objects."""
        simplifier = DOMSimplifier()
        
        dom = await simplifier.simplify(mock_page)
        
        elem = dom.elements[0]
        assert isinstance(elem, SimplifiedElement)
        assert elem.tag == "button"
        assert elem.id == "login-btn"
    
    @pytest.mark.asyncio
    async def test_simplify_handles_empty(self):
        """Test simplify handles empty page."""
        page = MagicMock()
        page.url = "https://empty.com"
        page.title = AsyncMock(return_value="Empty")
        page.evaluate = AsyncMock(return_value=[])
        
        simplifier = DOMSimplifier()
        dom = await simplifier.simplify(page)
        
        assert dom.element_count == 0
    
    @pytest.mark.asyncio
    async def test_simplify_handles_error(self):
        """Test simplify handles JS evaluation error."""
        page = MagicMock()
        page.url = "https://error.com"
        page.title = AsyncMock(return_value="Error")
        page.evaluate = AsyncMock(side_effect=Exception("JS error"))
        
        simplifier = DOMSimplifier()
        dom = await simplifier.simplify(page)
        
        assert dom.element_count == 0


class TestDOMSimplifierFilters:
    """Test filtered element extraction."""
    
    @pytest.fixture
    def mock_page_with_forms(self):
        """Create mock page with form elements."""
        page = MagicMock()
        page.url = "https://form.com"
        page.title = AsyncMock(return_value="Form Page")
        page.evaluate = AsyncMock(return_value=[
            {"tag": "input", "type": "text", "selector": "input[type='text']"},
            {"tag": "input", "type": "email", "selector": "input[type='email']"},
            {"tag": "textarea", "selector": "textarea"},
            {"tag": "select", "selector": "select"},
            {"tag": "button", "text": "Submit", "selector": "button"},
            {"tag": "a", "text": "Link", "href": "/page", "selector": "a"},
        ])
        return page
    
    @pytest.mark.asyncio
    async def test_get_form_elements(self, mock_page_with_forms):
        """Test getting form elements only."""
        simplifier = DOMSimplifier()
        
        elements = await simplifier.get_form_elements(mock_page_with_forms)
        
        # Should only return input, textarea, select
        assert all(e.tag in ("input", "textarea", "select") for e in elements)
    
    @pytest.mark.asyncio
    async def test_get_clickable_elements(self, mock_page_with_forms):
        """Test getting clickable elements only."""
        simplifier = DOMSimplifier()
        
        elements = await simplifier.get_clickable_elements(mock_page_with_forms)
        
        # Should only return button, a
        assert all(e.tag in ("button", "a") for e in elements)


class TestInteractiveTags:
    """Test interactive element detection."""
    
    def test_interactive_tags_defined(self):
        """Test interactive tags are defined."""
        assert "button" in DOMSimplifier.INTERACTIVE_TAGS
        assert "input" in DOMSimplifier.INTERACTIVE_TAGS
        assert "a" in DOMSimplifier.INTERACTIVE_TAGS
        assert "select" in DOMSimplifier.INTERACTIVE_TAGS
    
    def test_interactive_roles_defined(self):
        """Test interactive roles are defined."""
        assert "button" in DOMSimplifier.INTERACTIVE_ROLES
        assert "link" in DOMSimplifier.INTERACTIVE_ROLES
        assert "textbox" in DOMSimplifier.INTERACTIVE_ROLES
        assert "checkbox" in DOMSimplifier.INTERACTIVE_ROLES
