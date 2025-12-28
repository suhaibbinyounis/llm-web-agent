"""
Configuration module - Centralized settings management.

This module provides type-safe configuration management using Pydantic,
supporting environment variables, YAML files, and CLI arguments.

Usage:
    from llm_web_agent.config import get_settings, load_config
    
    # Get global settings (loaded once)
    settings = get_settings()
    
    # Or load fresh settings with overrides
    settings = load_config(browser={"headless": False})

Environment Variables:
    LLM_WEB_AGENT__LLM__MODEL=gpt-4o
    LLM_WEB_AGENT__LLM__BASE_URL=https://api.openai.com/v1
    LLM_WEB_AGENT__BROWSER__HEADLESS=false
    OPENAI_API_KEY=sk-...
"""

from llm_web_agent.config.settings import (
    Settings,
    BrowserSettings,
    LLMSettings,
    AgentSettings,
    LoggingSettings,
)
from llm_web_agent.config.loader import ConfigLoader, load_config

# Global settings singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the global settings instance (singleton).
    
    Settings are loaded once from environment variables and config files.
    Call reset_settings() to reload.
    
    Returns:
        Global Settings instance
    """
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


def reset_settings() -> None:
    """Reset the global settings (forces reload on next get_settings())."""
    global _settings
    _settings = None


__all__ = [
    "Settings",
    "BrowserSettings",
    "LLMSettings",
    "AgentSettings",
    "LoggingSettings",
    "ConfigLoader",
    "load_config",
    "get_settings",
    "reset_settings",
]

