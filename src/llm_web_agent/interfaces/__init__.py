"""
Interfaces module - Abstract base classes for all pluggable components.

This module defines the contracts that browser engines, LLM providers,
and actions must implement to be compatible with the agent.
"""

from llm_web_agent.interfaces.browser import (
    IBrowser,
    IPage,
    IElement,
    ElementHandle,
    BrowserType,
)
from llm_web_agent.interfaces.llm import (
    ILLMProvider,
    Message,
    MessageRole,
    LLMResponse,
)
from llm_web_agent.interfaces.action import (
    IAction,
    ActionType,
    ActionResult,
)
from llm_web_agent.interfaces.extractor import (
    IDataExtractor,
    PageState,
)

__all__ = [
    # Browser interfaces
    "IBrowser",
    "IPage",
    "IElement",
    "ElementHandle",
    "BrowserType",
    # LLM interfaces
    "ILLMProvider",
    "Message",
    "MessageRole",
    "LLMResponse",
    # Action interfaces
    "IAction",
    "ActionType",
    "ActionResult",
    # Extractor interfaces
    "IDataExtractor",
    "PageState",
]
