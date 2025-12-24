"""
LLM Provider Interface - Abstract base classes for LLM integrations.

This module defines the contract that LLM providers (OpenAI, Anthropic, etc.)
must follow to be compatible with the LLM Web Agent.

Example:
    >>> from llm_web_agent.llm import OpenAIProvider
    >>> provider = OpenAIProvider(api_key="sk-...")
    >>> response = await provider.complete([Message(role=MessageRole.USER, content="Hello")])
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union


class MessageRole(Enum):
    """Role of a message in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ImageContent:
    """
    Image content for vision-capable models.
    
    Attributes:
        data: Base64-encoded image data or URL
        media_type: MIME type (e.g., 'image/png', 'image/jpeg')
        is_url: Whether data is a URL (True) or base64 data (False)
    """
    data: str
    media_type: str = "image/png"
    is_url: bool = False


@dataclass
class Message:
    """
    A message in the LLM conversation.
    
    Attributes:
        role: The role of the message sender
        content: The text content of the message
        images: Optional list of images for vision models
        name: Optional name for the message sender (for tool messages)
        tool_call_id: Optional ID for tool response messages
    """
    role: MessageRole
    content: str
    images: Optional[List[ImageContent]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str, images: Optional[List[ImageContent]] = None) -> "Message":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content, images=images)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """Create an assistant message."""
        return cls(role=MessageRole.ASSISTANT, content=content)


@dataclass
class ToolCall:
    """
    A tool/function call from the LLM.
    
    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool/function to call
        arguments: JSON string of arguments
    """
    id: str
    name: str
    arguments: str


@dataclass
class Usage:
    """
    Token usage information from an LLM response.
    
    Attributes:
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """
    Response from an LLM completion request.
    
    Attributes:
        content: The text content of the response
        model: The model that generated the response
        usage: Token usage information
        tool_calls: Optional list of tool calls
        finish_reason: Reason the completion finished ('stop', 'length', 'tool_calls')
        raw_response: The original response object from the provider
    """
    content: str
    model: str
    usage: Usage
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = "stop"
    raw_response: Any = None


@dataclass
class ToolDefinition:
    """
    Definition of a tool/function that the LLM can call.
    
    Attributes:
        name: Name of the tool
        description: Description of what the tool does
        parameters: JSON schema for the tool's parameters
    """
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class ILLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    
    This interface defines the contract that all LLM provider implementations
    must follow. Implementations should handle authentication, request formatting,
    and response parsing for their specific provider.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of this provider.
        
        Returns:
            Provider name (e.g., 'openai', 'anthropic')
        """
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """
        Get the default model for this provider.
        
        Returns:
            Default model name
        """
        ...

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        """
        Check if this provider supports vision (image) inputs.
        
        Returns:
            True if vision is supported
        """
        ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool:
        """
        Check if this provider supports tool/function calling.
        
        Returns:
            True if tools are supported
        """
        ...

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """
        Check if this provider supports streaming responses.
        
        Returns:
            True if streaming is supported
        """
        ...

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion for the given messages.
        
        Args:
            messages: List of messages in the conversation
            model: Model to use (defaults to provider's default model)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in the response
            tools: Optional list of tools the model can call
            **kwargs: Provider-specific options
            
        Returns:
            The LLM's response
            
        Raises:
            LLMError: If the request fails
            RateLimitError: If rate limited
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a completion for the given messages.
        
        Args:
            messages: List of messages in the conversation
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Provider-specific options
            
        Yields:
            Text chunks as they are generated
            
        Raises:
            LLMError: If the request fails
            NotImplementedError: If streaming is not supported
        """
        ...

    @abstractmethod
    async def count_tokens(self, messages: List[Message], model: Optional[str] = None) -> int:
        """
        Count the number of tokens in the given messages.
        
        Args:
            messages: List of messages to count tokens for
            model: Model to use for tokenization
            
        Returns:
            Estimated token count
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is available and properly configured.
        
        Returns:
            True if the provider is healthy
        """
        ...
