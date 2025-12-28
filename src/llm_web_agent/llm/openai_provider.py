"""
OpenAI-compatible LLM Provider.

Supports any OpenAI-compatible API including:
- OpenAI
- Azure OpenAI
- Local servers (LM Studio, Ollama, etc.)
- Custom gateways (like the Copilot Gateway)
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from llm_web_agent.interfaces.llm import (
    ILLMProvider,
    Message,
    MessageRole,
    LLMResponse,
    ToolCall,
    ToolDefinition,
    Usage,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(ILLMProvider):
    """
    OpenAI-compatible LLM provider.
    
    Works with any OpenAI-compatible API endpoint.
    
    Example:
        >>> provider = OpenAIProvider(
        ...     base_url="https://api.openai.com/v1",
        ...     model="gpt-4o"
        ... )
        >>> response = await provider.complete([
        ...     Message.user("Hello!")
        ... ])
    """
    
    def __init__(
        self,
        base_url: str,  # Required - no default
        model: str,     # Required - no default
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Initialize the provider.
        
        Args:
            base_url: Base URL for the API (no /v1 suffix needed)
            model: Model to use for completions
            api_key: Optional API key (reads from OPENAI_API_KEY env var if not set)
            timeout: Request timeout in seconds
        """
        import os
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-needed")
        self._model = model
        self._timeout = timeout
        
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def default_model(self) -> str:
        return self._model
    
    @property
    def supports_vision(self) -> bool:
        return True
    
    @property
    def supports_tools(self) -> bool:
        return True
    
    @property
    def supports_streaming(self) -> bool:
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
        model = model or self._model
        
        # Convert messages to OpenAI format
        formatted_messages = []
        for msg in messages:
            formatted = {
                "role": msg.role.value if isinstance(msg.role, MessageRole) else msg.role,
                "content": msg.content,
            }
            if msg.name:
                formatted["name"] = msg.name
            if msg.tool_call_id:
                formatted["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(formatted)
        
        # Build request body
        body: Dict[str, Any] = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            body["max_tokens"] = max_tokens
        
        # Add tools if provided
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        
        # Add any extra kwargs
        body.update(kwargs)
        
        logger.debug(f"Calling OpenAI API: {model}")
        
        try:
            response = await self._client.post(
                "/v1/chat/completions",
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            choice = data["choices"][0]
            message = choice["message"]
            
            # Extract tool calls if present
            tool_calls = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    )
                    for tc in message["tool_calls"]
                ]
            
            # Parse usage
            usage_data = data.get("usage", {})
            usage = Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
            
            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=usage,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop"),
                raw_response=data,
            )
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        model = model or self._model
        
        # Convert messages
        formatted_messages = [
            {
                "role": msg.role.value if isinstance(msg.role, MessageRole) else msg.role,
                "content": msg.content,
            }
            for msg in messages
        ]
        
        body = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens:
            body["max_tokens"] = max_tokens
        
        body.update(kwargs)
        
        async with self._client.stream(
            "POST",
            "/v1/chat/completions",
            json=body,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue
    
    async def count_tokens(self, messages: List[Message], model: Optional[str] = None) -> int:
        """Estimate token count (approximate)."""
        # Simple estimation: ~4 chars per token
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4
    
    async def health_check(self) -> bool:
        """Check if the API is available."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
