"""
Tests for DOMMap module.
"""

import pytest
from llm_web_agent.engine.dom_map import (
    DOMMap,
    DOMElement,
    BoundingRect,
    get_dom_map,
)


class TestBoundingRect:
    """Test BoundingRect dataclass."""
    
    def test_center_calculation(self):
        """Test center point calculation."""
        rect = BoundingRect(x=100, y=200, width=50, height=30)
        
        assert rect.center_x == 125
        assert rect.center_y == 215
    
    def test_distance_calculation(self):
        """Test distance between rects."""
        rect1 = BoundingRect(x=0, y=0, width=100, height=100)
        rect2 = BoundingRect(x=100, y=0, width=100, height=100)
        
        # Distance between centers (50,50) and (150,50) = 100
        distance = rect1.distance_to(rect2)
        assert distance == 100.0


class TestDOMElement:
    """Test DOMElement dataclass."""
    
    def test_best_selector(self):
        """Test best_selector property."""
        elem = DOMElement(
            fingerprint="abc123",
            selectors=["#login-btn", ".btn-primary", "button"],
            text="Login",
            tag="button",
            rect=BoundingRect(0, 0, 100, 50),
        )
        
        assert elem.best_selector == "#login-btn"
    
    def test_is_input(self):
        """Test is_input property."""
        input_elem = DOMElement(
            fingerprint="abc123",
            selectors=["#email"],
            text="",
            tag="input",
            rect=BoundingRect(0, 0, 200, 40),
        )
        
        button_elem = DOMElement(
            fingerprint="def456",
            selectors=["#submit"],
            text="Submit",
            tag="button",
            rect=BoundingRect(0, 0, 100, 50),
        )
        
        assert input_elem.is_input is True
        assert button_elem.is_input is False
    
    def test_is_interactive(self):
        """Test is_interactive property."""
        button = DOMElement(
            fingerprint="abc",
            selectors=["#btn"],
            text="Click",
            tag="button",
            rect=BoundingRect(0, 0, 100, 50),
            is_clickable=True,
        )
        
        div = DOMElement(
            fingerprint="def",
            selectors=["#div"],
            text="Some text",
            tag="div",
            rect=BoundingRect(0, 0, 100, 50),
            is_clickable=False,
        )
        
        assert button.is_interactive is True
        assert div.is_interactive is False


class TestDOMMapLookups:
    """Test DOMMap lookup methods."""
    
    def setup_method(self):
        """Create a test DOMMap with sample elements."""
        self.dom_map = DOMMap()
        
        # Add test elements directly to indexes
        self.button_elem = DOMElement(
            fingerprint="btn123",
            selectors=["#submit-btn", ".MuiButton-root"],
            text="Submit Form",
            tag="button",
            rect=BoundingRect(100, 200, 120, 40),
            is_clickable=True,
        )
        
        self.input_elem = DOMElement(
            fingerprint="inp456",
            selectors=["#email-input", "[name='email']"],
            text="",
            tag="input",
            rect=BoundingRect(100, 100, 250, 40),
            placeholder="Enter your email",
            name="email",
        )
        
        # Index elements
        self.dom_map.by_text["submit form"] = [self.button_elem]
        self.dom_map.by_word["submit"] = [self.button_elem]
        self.dom_map.by_word["form"] = [self.button_elem]
        self.dom_map.by_placeholder["enter your email"] = [self.input_elem]
        self.dom_map.by_name["email"] = [self.input_elem]
        self.dom_map.by_fingerprint["btn123"] = self.button_elem
        self.dom_map.by_fingerprint["inp456"] = self.input_elem
        self.dom_map.elements = [self.button_elem, self.input_elem]
    
    def test_find_by_text(self):
        """Test exact text lookup."""
        results = self.dom_map.find_by_text("Submit Form")
        assert len(results) == 1
        assert results[0].fingerprint == "btn123"
    
    def test_find_by_word(self):
        """Test single word lookup."""
        results = self.dom_map.find_by_word("submit")
        assert len(results) == 1
        assert results[0].text == "Submit Form"
    
    def test_find_by_placeholder(self):
        """Test placeholder lookup."""
        results = self.dom_map.find_by_placeholder("Enter your email")
        assert len(results) == 1
        assert results[0].tag == "input"
    
    def test_find_by_name(self):
        """Test name attribute lookup."""
        results = self.dom_map.find_by_name("email")
        assert len(results) == 1
        assert results[0].name == "email"
    
    def test_find_by_fingerprint(self):
        """Test fingerprint lookup."""
        result = self.dom_map.find_by_fingerprint("btn123")
        assert result is not None
        assert result.text == "Submit Form"
    
    def test_find_by_phrase(self):
        """Test phrase lookup (all words)."""
        # First add form to button's word index
        self.dom_map.by_word["form"] = [self.button_elem]
        
        results = self.dom_map.find_by_phrase("Submit Form")
        assert len(results) >= 1


class TestDOMMapUniversalFind:
    """Test the universal find() method."""
    
    def setup_method(self):
        """Create test DOMMap."""
        self.dom_map = DOMMap()
        
        self.button = DOMElement(
            fingerprint="btn1",
            selectors=["#login-button"],
            text="Log In",
            tag="button",
            rect=BoundingRect(100, 100, 100, 40),
            is_clickable=True,
            data_testid="login-button",
        )
        
        # Index the button
        self.dom_map.by_text["log in"] = [self.button]
        self.dom_map.by_data_testid["login-button"] = self.button
        self.dom_map.by_fingerprint["btn1"] = self.button
    
    def test_find_by_testid(self):
        """Universal find should check testid."""
        results = self.dom_map.find("login-button")
        assert len(results) == 1
        assert results[0].data_testid == "login-button"
    
    def test_find_by_text(self):
        """Universal find should check text."""
        results = self.dom_map.find("Log In")
        assert len(results) >= 1


class TestDOMMapIsStale:
    """Test staleness checking."""
    
    def test_new_map_is_stale(self):
        """Newly created map should be stale."""
        dom_map = DOMMap()
        assert dom_map.is_stale() is True
    
    def test_is_for_url(self):
        """Test URL matching."""
        dom_map = DOMMap()
        dom_map.url = "https://example.com/page"
        
        assert dom_map.is_for_url("https://example.com/page") is True
        assert dom_map.is_for_url("https://example.com/other") is False


class TestGetDomMap:
    """Test singleton getter."""
    
    def test_returns_dom_map(self):
        """Should return a DOMMap instance."""
        dom_map = get_dom_map()
        assert isinstance(dom_map, DOMMap)
    
    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        map1 = get_dom_map()
        map2 = get_dom_map()
        assert map1 is map2
