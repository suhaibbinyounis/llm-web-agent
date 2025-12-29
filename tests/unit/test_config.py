"""
Tests for configuration system.
"""

import pytest
from llm_web_agent.config import Settings, BrowserSettings, LLMSettings, AgentSettings


class TestSettings:
    """Test the Settings classes."""
    
    def test_default_settings(self):
        """Test default settings are created correctly."""
        settings = Settings()
        
        assert settings.browser.engine == "playwright"
        assert settings.browser.headless is True
        assert settings.llm.provider == "openai"
        assert settings.llm.model is None
        assert settings.agent.max_steps == 20
    
    def test_override_settings(self):
        """Test overriding settings."""
        settings = Settings(
            browser=BrowserSettings(engine="selenium", headless=False),
            llm=LLMSettings(provider="anthropic", model="claude-3-opus"),
        )
        
        assert settings.browser.engine == "selenium"
        assert settings.browser.headless is False
        assert settings.llm.provider == "anthropic"
        assert settings.llm.model == "claude-3-opus"
    
    def test_merge_with_overrides(self):
        """Test merging settings with overrides."""
        settings = Settings()
        new_settings = settings.merge_with({
            "browser": {"headless": False},
            "agent": {"verbose": True},
        })
        
        assert new_settings.browser.headless is False
        assert new_settings.agent.verbose is True
        # Other settings should remain default
        assert new_settings.browser.engine == "playwright"
    
    def test_browser_settings_validation(self):
        """Test validation of browser settings."""
        # Valid settings
        settings = BrowserSettings(timeout_ms=5000)
        assert settings.timeout_ms == 5000
        
        # Invalid timeout (below minimum)
        with pytest.raises(ValueError):
            BrowserSettings(timeout_ms=100)
    
    def test_agent_settings_validation(self):
        """Test validation of agent settings."""
        # Valid settings
        settings = AgentSettings(max_steps=50)
        assert settings.max_steps == 50
        
        # Invalid max_steps (above maximum)
        with pytest.raises(ValueError):
            AgentSettings(max_steps=200)
