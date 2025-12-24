"""
OpenAI Provider - Implementation of ILLMProvider for OpenAI.
"""

import os
from typing import Any, AsyncIterator, List, Optional
import logging

from llm_web_agent.interfaces.llm import (
    Message,
    LLMResponse,
    ToolDefinition,
    ToolCall,
    Usage,
)
from llm_web_agent.llm.base import BaseLLMProvider
from llm_web_agent.exceptions.llm import (
    LLMConnectionError,
    LLMAuthenticationError,
    RateLimitError,
    InvalidResponseError,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM provider implementation.
    
    Supports GPT-4, GPT-4 Turbo, GPT-4o, and other OpenAI models.
    
    Example:
        >>> provider = OpenAIProvider(api_key="sk-...")
        >>> response = await provider.complete([
        ...     Message.system("You are a helpful assistant."),
        ...     Message.user("Hello!")
        ... ])
        >>> print(response.content)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Initialize the OpenAI provider.
        
        Args:
            api_key: OpenAI API key (falls back to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o)
            base_url: Custom API endpoint (for proxies/compatible APIs)
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, model, base_url, timeout)
        
        # Resolve API key
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            logger.warning("No OpenAI API key provided. Set OPENAI_API_KEY or pass api_key.")
        
        self._client: Any = None
    
    @property
    def name(self) -> str:
        """Provider name."""
        return "openai"
    
    @property
    def default_model(self) -> str:
        """Default model."""
        return "gpt-4o"
    
    @property
    def supports_vision(self) -> bool:
        """OpenAI supports vision with GPT-4 Vision models."""
        return True
    
    @property
    def supports_tools(self) -> bool:
        """OpenAI supports function/tool calling."""
        return True
    
    async def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                
                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Install with: pip install openai"
                )
        return self._client
    
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
        Generate a completion.
        
        Args:
            messages: Conversation messages
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            tools: Available tools/functions
            **kwargs: Additional OpenAI-specific options
            
        Returns:
            LLM response
        """
        client = await self._get_client()
        model_name = self._get_model(model)
        
        # Format messages
        formatted_messages = self._format_messages_with_images(messages)
        
        # Build request
        request_params: dict = {
            "model": model_name,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            request_params["max_tokens"] = max_tokens
        
        # Add tools if provided
        if tools:
            request_params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        
        # Add any additional kwargs
        request_params.update(kwargs)
        
        try:
            response = await client.chat.completions.create(**request_params)
            
            # Parse response
            choice = response.choices[0]
            content = choice.message.content or ""
            
            # Parse tool calls if present
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in choice.message.tool_calls
                ]
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ),
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason or "stop",
                raw_response=response,
            )
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "authentication" in error_str or "api key" in error_str:
                raise LLMAuthenticationError(f"Authentication failed: {e}")
            elif "rate limit" in error_str:
                raise RateLimitError(f"Rate limit exceeded: {e}")
            else:
                raise LLMConnectionError(f"OpenAI API error: {e}")
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a completion.
        
        Yields text chunks as they are generated.
        """
        client = await self._get_client()
        model_name = self._get_model(model)
        
        formatted_messages = self._format_messages_with_images(messages)
        
        request_params: dict = {
            "model": model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens:
            request_params["max_tokens"] = max_tokens
        
        request_params.update(kwargs)
        
        try:
            stream = await client.chat.completions.create(**request_params)
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise LLMConnectionError(f"OpenAI streaming error: {e}")
    
    def _format_messages_with_images(self, messages: List[Message]) -> List[dict]:
        """Format messages including image content for vision models."""
        formatted = []
        
        for m in messages:
            if m.images:
                # Multi-modal message with images
                content = [{"type": "text", "text": m.content}]
                
                for img in m.images:
                    if img.is_url:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": img.data},
                        })
                    else:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{img.media_type};base64,{img.data}"
                            },
                        })
                
                formatted.append({
                    "role": m.role.value,
                    "content": content,
                })
            else:
                # Text-only message
                formatted.append({
                    "role": m.role.value,
                    "content": m.content,
                })
        
        return formatted
