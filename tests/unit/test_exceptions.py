"""
Tests for custom exceptions.
"""

import pytest


class TestLLMWebAgentError:
    """Test the base LLMWebAgentError exception."""
    
    def test_create_base_error(self):
        """Test creating an LLMWebAgentError."""
        from llm_web_agent.exceptions import LLMWebAgentError
        error = LLMWebAgentError("Something went wrong")
        assert str(error) == "Something went wrong"
    
    def test_base_error_is_exception(self):
        """Test that LLMWebAgentError is an exception."""
        from llm_web_agent.exceptions import LLMWebAgentError
        assert issubclass(LLMWebAgentError, Exception)


class TestConfigurationError:
    """Test the ConfigurationError exception."""
    
    def test_create_config_error(self):
        """Test creating a ConfigurationError."""
        from llm_web_agent.exceptions import ConfigurationError
        error = ConfigurationError("Invalid API key")
        assert str(error) == "Invalid API key"
    
    def test_config_error_is_base_error(self):
        """Test that ConfigurationError is subclass of LLMWebAgentError."""
        from llm_web_agent.exceptions import ConfigurationError, LLMWebAgentError
        assert issubclass(ConfigurationError, LLMWebAgentError)


class TestBrowserError:
    """Test the BrowserError exception."""
    
    def test_create_browser_error(self):
        """Test creating a BrowserError."""
        from llm_web_agent.exceptions import BrowserError
        error = BrowserError("Browser crashed")
        assert str(error) == "Browser crashed"
    
    def test_browser_error_is_base_error(self):
        """Test that BrowserError is subclass of LLMWebAgentError."""
        from llm_web_agent.exceptions import BrowserError, LLMWebAgentError
        assert issubclass(BrowserError, LLMWebAgentError)


class TestElementNotFoundError:
    """Test the ElementNotFoundError exception."""
    
    def test_create_element_not_found(self):
        """Test creating an ElementNotFoundError."""
        from llm_web_agent.exceptions import ElementNotFoundError
        error = ElementNotFoundError("Button not found", selector="#submit")
        assert "not found" in str(error).lower()
        assert error.selector == "#submit"
    
    def test_element_not_found_is_browser_error(self):
        """Test that ElementNotFoundError is subclass of BrowserError."""
        from llm_web_agent.exceptions import ElementNotFoundError, BrowserError
        assert issubclass(ElementNotFoundError, BrowserError)


class TestNavigationError:
    """Test the NavigationError exception."""
    
    def test_create_navigation_error(self):
        """Test creating a NavigationError."""
        from llm_web_agent.exceptions import NavigationError
        error = NavigationError("Failed to navigate")
        assert "navigate" in str(error).lower() or "failed" in str(error).lower()
    
    def test_navigation_error_is_browser_error(self):
        """Test that NavigationError is subclass of BrowserError."""
        from llm_web_agent.exceptions import NavigationError, BrowserError
        assert issubclass(NavigationError, BrowserError)


class TestLLMError:
    """Test the LLMError exception."""
    
    def test_create_llm_error(self):
        """Test creating an LLMError."""
        from llm_web_agent.exceptions import LLMError
        error = LLMError("Rate limited")
        assert str(error) == "Rate limited"
    
    def test_llm_error_is_base_error(self):
        """Test that LLMError is subclass of LLMWebAgentError."""
        from llm_web_agent.exceptions import LLMError, LLMWebAgentError
        assert issubclass(LLMError, LLMWebAgentError)


class TestRateLimitError:
    """Test the RateLimitError exception."""
    
    def test_create_rate_limit_error(self):
        """Test creating a RateLimitError."""
        from llm_web_agent.exceptions import RateLimitError
        error = RateLimitError("Too many requests")
        assert "requests" in str(error).lower()
    
    def test_rate_limit_is_llm_error(self):
        """Test that RateLimitError is subclass of LLMError."""
        from llm_web_agent.exceptions import RateLimitError, LLMError
        assert issubclass(RateLimitError, LLMError)


class TestActionError:
    """Test the ActionError exception."""
    
    def test_create_action_error(self):
        """Test creating an ActionError."""
        from llm_web_agent.exceptions import ActionError
        error = ActionError("Action failed")
        assert str(error) == "Action failed"
    
    def test_action_error_is_base_error(self):
        """Test that ActionError is subclass of LLMWebAgentError."""
        from llm_web_agent.exceptions import ActionError, LLMWebAgentError
        assert issubclass(ActionError, LLMWebAgentError)


class TestActionExecutionError:
    """Test the ActionExecutionError exception."""
    
    def test_create_execution_error(self):
        """Test creating an ActionExecutionError."""
        from llm_web_agent.exceptions import ActionExecutionError
        error = ActionExecutionError("Click failed", action_type="click")
        assert "failed" in str(error).lower()
        assert error.action_type == "click"
    
    def test_execution_error_is_action_error(self):
        """Test that ActionExecutionError is subclass of ActionError."""
        from llm_web_agent.exceptions import ActionExecutionError, ActionError
        assert issubclass(ActionExecutionError, ActionError)


class TestBrowserTimeoutError:
    """Test the BrowserTimeoutError exception."""
    
    def test_create_timeout_error(self):
        """Test creating a BrowserTimeoutError."""
        from llm_web_agent.exceptions import BrowserTimeoutError
        error = BrowserTimeoutError("Operation timed out", timeout_ms=30000)
        assert error.timeout_ms == 30000
    
    def test_timeout_error_is_browser_error(self):
        """Test that BrowserTimeoutError is subclass of BrowserError."""
        from llm_web_agent.exceptions import BrowserTimeoutError, BrowserError
        assert issubclass(BrowserTimeoutError, BrowserError)


class TestExceptionRaising:
    """Test that exceptions can be raised and caught properly."""
    
    def test_raise_and_catch_browser_error(self):
        """Test raising and catching BrowserError."""
        from llm_web_agent.exceptions import LLMWebAgentError, BrowserError
        
        with pytest.raises(LLMWebAgentError):
            raise BrowserError("Test")
    
    def test_exception_chain(self):
        """Test exception chaining."""
        from llm_web_agent.exceptions import BrowserError, ElementNotFoundError
        
        original = ValueError("underlying error")
        with pytest.raises(BrowserError) as exc_info:
            raise ElementNotFoundError("Not found", selector="#test") from original
        
        assert exc_info.value.__cause__ == original
