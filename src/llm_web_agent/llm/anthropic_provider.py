"""
Anthropic Provider - Stub implementation for Claude models.
"""

import os
from typing import Any, AsyncIterator, List, Optional
import logging

from llm_web_agent.interfaces.llm import (
    Message,
    LLMResponse,
    ToolDefinition,
    Usage,
)
from llm_web_agent.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic LLM provider implementation (stub).
    
    Supports Claude 3 models (Opus, Sonnet, Haiku).
    
    Example:
        >>> provider = AnthropicProvider(api_key="sk-ant-...")
        >>> response = await provider.complete([
        ...     Message.user("Hello!")
        ... ])
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Initialize the Anthropic provider.
        
        Args:
            api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY)
            model: Model to use (default: claude-3-sonnet-20240229)
            base_url: Custom API endpoint
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, model, base_url, timeout)
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def default_model(self) -> str:
        return "claude-3-sonnet-20240229"
    
    @property
    def supports_vision(self) -> bool:
        return True
    
    @property
    def supports_tools(self) -> bool:
        return True
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion."""
        # TODO: Implement Anthropic completion
        raise NotImplementedError(
            "Anthropic provider not yet implemented. "
            "Use 'openai' provider or implement this class."
        )
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        raise NotImplementedError("Anthropic streaming not yet implemented")
        yield  # Make this a generator
