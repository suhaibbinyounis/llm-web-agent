"""
Context Module - Document loading and context injection.

This module handles loading files and documents to provide
context for automation tasks.
"""

from llm_web_agent.context.loaders.base import IContextLoader, LoadedDocument
from llm_web_agent.context.context_manager import ContextManager

__all__ = [
    "IContextLoader",
    "LoadedDocument",
    "ContextManager",
]
