"""
Tests for the component registry.
"""

import pytest
from llm_web_agent.registry import ComponentRegistry
from llm_web_agent.interfaces.browser import IBrowser
from llm_web_agent.interfaces.llm import ILLMProvider


class TestComponentRegistry:
    """Test the ComponentRegistry class."""
    
    def setup_method(self):
        """Clear registry before each test."""
        ComponentRegistry.clear_all()
    
    def teardown_method(self):
        """Clear registry after each test."""
        ComponentRegistry.clear_all()
    
    def test_register_browser(self):
        """Test registering a browser implementation."""
        @ComponentRegistry.register_browser("test")
        class TestBrowser(IBrowser):
            @property
            def is_connected(self):
                return False
            
            async def launch(self, **kwargs):
                pass
            
            async def new_page(self, **kwargs):
                pass
            
            async def new_context(self, **kwargs):
                pass
            
            async def close(self):
                pass
        
        assert "test" in ComponentRegistry.list_browsers()
        assert ComponentRegistry.get_browser("test") == TestBrowser
    
    def test_get_unknown_browser_raises(self):
        """Test that getting an unknown browser raises ValueError."""
        with pytest.raises(ValueError, match="Unknown browser"):
            ComponentRegistry.get_browser("nonexistent")
    
    def test_register_llm_provider(self):
        """Test registering an LLM provider."""
        @ComponentRegistry.register_llm("test")
        class TestProvider(ILLMProvider):
            @property
            def name(self):
                return "test"
            
            @property
            def default_model(self):
                return "test-model"
            
            @property
            def supports_vision(self):
                return False
            
            @property
            def supports_tools(self):
                return False
            
            @property
            def supports_streaming(self):
                return False
            
            async def complete(self, messages, **kwargs):
                pass
            
            async def stream(self, messages, **kwargs):
                pass
            
            async def count_tokens(self, messages, **kwargs):
                return 0
            
            async def health_check(self):
                return True
        
        assert "test" in ComponentRegistry.list_llm_providers()
        assert ComponentRegistry.get_llm_provider("test") == TestProvider
    
    def test_list_browsers(self):
        """Test listing registered browsers."""
        assert isinstance(ComponentRegistry.list_browsers(), list)
    
    def test_list_llm_providers(self):
        """Test listing registered LLM providers."""
        assert isinstance(ComponentRegistry.list_llm_providers(), list)
