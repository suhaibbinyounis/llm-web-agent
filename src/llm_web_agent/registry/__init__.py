"""
Registry module - Component registration and discovery.

This module provides a registry pattern for dynamically registering
and discovering pluggable components like browsers and LLM providers.
"""

from llm_web_agent.registry.registry import (
    ComponentRegistry,
    register_browser,
    register_llm,
    register_action,
    register_extractor,
    get_browser,
    get_llm_provider,
    get_action,
)

__all__ = [
    "ComponentRegistry",
    "register_browser",
    "register_llm",
    "register_action",
    "register_extractor",
    "get_browser",
    "get_llm_provider",
    "get_action",
]
