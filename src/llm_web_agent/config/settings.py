"""
Settings - Pydantic models for type-safe configuration.

This module defines all configuration settings as Pydantic models,
providing validation, type hints, and automatic environment variable loading.

Example:
    >>> from llm_web_agent.config import Settings, load_config
    >>> settings = load_config()  # Loads from env, yaml, and defaults
    >>> print(settings.browser.engine)
    'playwright'
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserSettings(BaseModel):
    """
    Browser automation settings.
    
    Attributes:
        engine: Browser automation engine to use
        headless: Run browser in headless mode
        timeout_ms: Default timeout for browser operations
        viewport_width: Browser viewport width in pixels
        viewport_height: Browser viewport height in pixels
        user_agent: Custom user agent string
        slow_mo: Slow down operations by this amount (ms) - useful for debugging
    """
    engine: Literal["playwright", "selenium"] = "playwright"
    headless: bool = True
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)
    user_agent: Optional[str] = None
    slow_mo: int = Field(default=0, ge=0, le=5000)
    
    # Browser type (chromium, firefox, webkit) - only for playwright
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"
    
    # Download settings
    downloads_path: Optional[str] = None
    accept_downloads: bool = True
    
    # UI Overlay settings
    show_overlay: bool = False  # Show sidebar with action history
    highlight_elements: bool = False  # Highlight elements before interaction
    overlay_position: Literal["left", "right"] = "right"
    highlight_color: str = "#FF6B6B"  # Coral red
    highlight_duration_ms: int = Field(default=1500, ge=100, le=5000)


class LLMSettings(BaseModel):
    """
    LLM provider settings.
    
    Attributes:
        provider: LLM provider to use
        model: Model name/identifier
        api_key: API key (loaded from environment if not set)
        base_url: Custom API endpoint URL
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
    """
    provider: Literal["openai", "anthropic", "copilot", "custom"] = "openai"
    model: str = "gpt-4o"
    api_key: Optional[SecretStr] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    timeout: int = Field(default=60, ge=5, le=300)
    
    # Vision settings
    use_vision: bool = True
    screenshot_quality: int = Field(default=80, ge=1, le=100)
    max_image_size: int = Field(default=1024, ge=256, le=4096)


class AgentSettings(BaseModel):
    """
    Agent behavior settings.
    
    Attributes:
        max_steps: Maximum number of steps per task
        retry_attempts: Number of retry attempts for failed actions
        step_delay_ms: Delay between steps in milliseconds
        screenshot_on_error: Take screenshot when an error occurs
        screenshot_on_step: Take screenshot after each step
        verbose: Enable verbose logging
    """
    max_steps: int = Field(default=20, ge=1, le=100)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    step_delay_ms: int = Field(default=500, ge=0, le=10000)
    screenshot_on_error: bool = True
    screenshot_on_step: bool = False
    verbose: bool = False
    
    # Error handling
    stop_on_error: bool = False
    continue_on_timeout: bool = True
    
    # Output settings
    output_dir: str = "./output"
    save_trace: bool = False


class LoggingSettings(BaseModel):
    """
    Logging configuration.
    
    Attributes:
        level: Log level
        format: Log format string
        file: Log file path (None for console only)
        json_format: Use JSON format for logs
    """
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    json_format: bool = False


class Settings(BaseSettings):
    """
    Root settings container - single source of truth for all configuration.
    
    Settings are loaded in this priority order (highest to lowest):
    1. Explicit values passed to constructor
    2. Environment variables (prefixed with LLM_WEB_AGENT__)
    3. Config file (YAML)
    4. Default values
    
    Example:
        >>> settings = Settings()  # Load from env vars
        >>> settings = Settings(browser=BrowserSettings(headless=False))  # Override
    """
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_WEB_AGENT__",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    # Additional top-level settings
    debug: bool = False
    profile: bool = False  # Enable performance profiling
    
    def merge_with(self, overrides: dict) -> "Settings":
        """
        Create a new Settings instance with overrides applied.
        
        Args:
            overrides: Dictionary of values to override
            
        Returns:
            New Settings instance with overrides applied
        """
        current = self.model_dump()
        
        def deep_merge(base: dict, updates: dict) -> dict:
            for key, value in updates.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        merged = deep_merge(current, overrides)
        return Settings(**merged)
