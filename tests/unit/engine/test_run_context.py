"""
Tests for RunContext - memory and clipboard functionality.
"""

import pytest
from datetime import datetime

from llm_web_agent.engine.run_context import RunContext, ExecutedAction


class TestRunContext:
    """Test RunContext memory operations."""
    
    def test_store_and_retrieve_clipboard(self):
        """Test storing and retrieving from clipboard."""
        ctx = RunContext()
        
        ctx.store("order_number", "12345")
        ctx.store("price", "$299.99")
        
        assert ctx.retrieve("order_number") == "12345"
        assert ctx.retrieve("price") == "$299.99"
    
    def test_store_and_retrieve_variables(self):
        """Test storing and retrieving variables."""
        ctx = RunContext()
        
        ctx.store("username", "john", source="variable")
        ctx.store("email", "john@example.com", source="variable")
        
        assert ctx.retrieve("username") == "john"
        assert ctx.retrieve("email") == "john@example.com"
    
    def test_store_and_retrieve_extracted(self):
        """Test storing and retrieving extracted data."""
        ctx = RunContext()
        
        ctx.store("page_title", "Welcome", source="extracted")
        
        assert ctx.retrieve("page_title") == "Welcome"
    
    def test_retrieve_priority(self):
        """Test retrieval priority: clipboard > variables > extracted."""
        ctx = RunContext()
        
        # Same key in all sources
        ctx.store("key", "clipboard_value", source="clipboard")
        ctx.store("key", "variable_value", source="variable")
        ctx.store("key", "extracted_value", source="extracted")
        
        # Clipboard should win
        assert ctx.retrieve("key") == "clipboard_value"
    
    def test_retrieve_missing_key(self):
        """Test retrieving non-existent key returns None."""
        ctx = RunContext()
        
        assert ctx.retrieve("missing") is None
    
    def test_resolve_template_single(self):
        """Test resolving single variable in template."""
        ctx = RunContext()
        ctx.store("name", "John")
        
        result = ctx.resolve("Hello {{name}}!")
        
        assert result == "Hello John!"
    
    def test_resolve_template_multiple(self):
        """Test resolving multiple variables in template."""
        ctx = RunContext()
        ctx.store("first", "John")
        ctx.store("last", "Doe")
        
        result = ctx.resolve("Name: {{first}} {{last}}")
        
        assert result == "Name: John Doe"
    
    def test_resolve_template_missing(self):
        """Test unresolved variables are kept as-is."""
        ctx = RunContext()
        ctx.store("known", "value")
        
        result = ctx.resolve("{{known}} and {{unknown}}")
        
        assert result == "value and {{unknown}}"
    
    def test_resolve_nested_key(self):
        """Test resolving nested keys like clipboard.key."""
        ctx = RunContext()
        ctx.store("order", "12345", source="clipboard")
        
        result = ctx.resolve("Order: {{clipboard.order}}")
        
        assert result == "Order: 12345"
    
    def test_has_references(self):
        """Test detecting references in text."""
        ctx = RunContext()
        
        assert ctx.has_references("Hello {{name}}") is True
        assert ctx.has_references("Hello world") is False
    
    def test_get_references(self):
        """Test extracting references from text."""
        ctx = RunContext()
        
        refs = ctx.get_references("{{a}} and {{b}} and {{c}}")
        
        assert refs == ["a", "b", "c"]
    
    def test_key_normalization(self):
        """Test key normalization (spaces, dashes, case)."""
        ctx = RunContext()
        
        ctx.store("Order Number", "123")
        ctx.store("user-name", "john")
        ctx.store("EMAIL_ADDRESS", "test@test.com")
        
        assert ctx.retrieve("order_number") == "123"
        assert ctx.retrieve("user_name") == "john"
        assert ctx.retrieve("email_address") == "test@test.com"


class TestRunContextHistory:
    """Test RunContext action history."""
    
    def test_record_action(self):
        """Test recording an action."""
        ctx = RunContext()
        
        ctx.record_action(
            step_id="step1",
            action_type="click",
            target="#button",
            success=True,
            duration_ms=150,
        )
        
        assert len(ctx.history) == 1
        assert ctx.history[0].step_id == "step1"
        assert ctx.history[0].action_type == "click"
        assert ctx.history[0].success is True
    
    def test_get_last_action(self):
        """Test getting the last action."""
        ctx = RunContext()
        
        ctx.record_action("s1", "click", success=True)
        ctx.record_action("s2", "fill", success=True)
        ctx.record_action("s3", "submit", success=False, error="timeout")
        
        last = ctx.get_last_action()
        
        assert last.step_id == "s3"
        assert last.success is False
    
    def test_get_failed_actions(self):
        """Test getting failed actions."""
        ctx = RunContext()
        
        ctx.record_action("s1", "click", success=True)
        ctx.record_action("s2", "fill", success=False, error="element not found")
        ctx.record_action("s3", "submit", success=False, error="timeout")
        
        failed = ctx.get_failed_actions()
        
        assert len(failed) == 2
        assert failed[0].step_id == "s2"
        assert failed[1].step_id == "s3"


class TestRunContextPageState:
    """Test RunContext page state management."""
    
    def test_update_page_state(self):
        """Test updating page state."""
        ctx = RunContext()
        
        ctx.update_page_state("https://example.com", "Example")
        
        assert ctx.current_url == "https://example.com"
        assert ctx.page_title == "Example"
        assert ctx.extracted["current_url"] == "https://example.com"
    
    def test_dom_cache_set_and_get(self):
        """Test DOM caching."""
        ctx = RunContext()
        ctx.update_page_state("https://example.com")
        
        mock_dom = {"elements": [1, 2, 3]}
        ctx.set_dom_cache(mock_dom, "https://example.com")
        
        cached = ctx.get_dom_cache()
        
        assert cached == mock_dom
    
    def test_dom_cache_invalidate_on_navigation(self):
        """Test DOM cache invalidation on navigation."""
        ctx = RunContext()
        ctx.update_page_state("https://example.com")
        
        ctx.set_dom_cache({"elements": []}, "https://example.com")
        
        # Navigate to new page
        ctx.update_page_state("https://other.com")
        
        # Cache should be invalidated
        cached = ctx.get_dom_cache()
        assert cached is None
    
    def test_get_all_stored(self):
        """Test getting all stored data."""
        ctx = RunContext()
        
        ctx.store("clip1", "v1", source="clipboard")
        ctx.store("var1", "v2", source="variable")
        ctx.store("ext1", "v3", source="extracted")
        
        all_data = ctx.get_all_stored()
        
        assert all_data["clip1"] == "v1"
        assert all_data["var1"] == "v2"
        assert all_data["ext1"] == "v3"
    
    def test_clear(self):
        """Test clearing all data."""
        ctx = RunContext()
        
        ctx.store("key", "value")
        ctx.record_action("s1", "click", success=True)
        ctx.set_dom_cache({}, "url")
        
        ctx.clear()
        
        assert len(ctx.clipboard) == 0
        assert len(ctx.history) == 0
        assert ctx.get_dom_cache() is None


class TestRunContextSummary:
    """Test RunContext summary generation."""
    
    def test_to_summary(self):
        """Test generating summary."""
        ctx = RunContext()
        ctx.run_id = "test123"
        ctx.update_page_state("https://example.com", "Test Page")
        ctx.store("key1", "value1")
        ctx.record_action("s1", "click", success=True)
        ctx.record_action("s2", "fill", success=False, error="failed")
        
        summary = ctx.to_summary()
        
        assert summary["run_id"] == "test123"
        assert summary["current_url"] == "https://example.com"
        assert "key1" in summary["clipboard_keys"]
        assert summary["action_count"] == 2
        assert summary["failed_actions"] == 1
