"""
Exceptions module - Custom exception hierarchy.

This module defines all custom exceptions used throughout the LLM Web Agent,
providing clear error types for different failure scenarios.
"""

from llm_web_agent.exceptions.base import (
    LLMWebAgentError,
    ConfigurationError,
    InitializationError,
)
from llm_web_agent.exceptions.browser import (
    BrowserError,
    BrowserLaunchError,
    BrowserConnectionError,
    PageError,
    NavigationError,
    ElementNotFoundError,
    ElementNotVisibleError,
    ElementNotInteractableError,
    TimeoutError as BrowserTimeoutError,
)
from llm_web_agent.exceptions.llm import (
    LLMError,
    LLMConnectionError,
    LLMAuthenticationError,
    RateLimitError,
    TokenLimitError,
    InvalidResponseError,
)
from llm_web_agent.exceptions.action import (
    ActionError,
    ActionValidationError,
    ActionExecutionError,
    ActionTimeoutError,
)

__all__ = [
    # Base exceptions
    "LLMWebAgentError",
    "ConfigurationError",
    "InitializationError",
    # Browser exceptions
    "BrowserError",
    "BrowserLaunchError",
    "BrowserConnectionError",
    "PageError",
    "NavigationError",
    "ElementNotFoundError",
    "ElementNotVisibleError",
    "ElementNotInteractableError",
    "BrowserTimeoutError",
    # LLM exceptions
    "LLMError",
    "LLMConnectionError",
    "LLMAuthenticationError",
    "RateLimitError",
    "TokenLimitError",
    "InvalidResponseError",
    # Action exceptions
    "ActionError",
    "ActionValidationError",
    "ActionExecutionError",
    "ActionTimeoutError",
]
