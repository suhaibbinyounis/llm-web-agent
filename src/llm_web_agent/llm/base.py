"""
Base LLM Provider - Common functionality for LLM providers.
"""

from abc import abstractmethod
from typing import Any, AsyncIterator, List, Optional
import logging

from llm_web_agent.interfaces.llm import (
    ILLMProvider,
    Message,
    LLMResponse,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class BaseLLMProvider(ILLMProvider):
    """
    Base class for LLM providers with common functionality.
    
    Provides default implementations for common methods and
    utility functions used by all providers.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Initialize the provider.
        
        Args:
            api_key: API key (falls back to environment variable)
            model: Model to use (falls back to default_model)
            base_url: Custom API endpoint
            timeout: Request timeout in seconds
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
    
    @property
    def supports_streaming(self) -> bool:
        """Most providers support streaming."""
        return True
    
    async def count_tokens(self, messages: List[Message], model: Optional[str] = None) -> int:
        """
        Estimate token count.
        
        Default implementation uses a rough estimate.
        Subclasses should override for accurate counting.
        """
        # Rough estimate: 1 token ≈ 4 characters
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
    
    async def health_check(self) -> bool:
        """
        Check if the provider is available.
        
        Default implementation tries a simple completion.
        """
        try:
            response = await self.complete(
                [Message.user("Hi")],
                max_tokens=5,
            )
            return len(response.content) > 0
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    def _get_model(self, model: Optional[str] = None) -> str:
        """Get the model to use, with fallbacks."""
        return model or self._model or self.default_model
    
    def _format_messages(self, messages: List[Message]) -> List[dict]:
        """
        Format messages for the API.
        
        Override in subclasses for provider-specific formatting.
        """
        return [
            {
                "role": m.role.value,
                "content": m.content,
            }
            for m in messages
        ]
