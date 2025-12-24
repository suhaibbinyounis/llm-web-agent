"""
Copilot Provider - Implementation for GitHub Copilot API Gateway.

This provider uses the GitHub Copilot API Gateway extension to access
the Copilot LLM API through a local server.
"""

import os
from typing import Any, AsyncIterator, List, Optional
import logging

import httpx

from llm_web_agent.interfaces.llm import (
    Message,
    LLMResponse,
    ToolDefinition,
    Usage,
)
from llm_web_agent.llm.base import BaseLLMProvider
from llm_web_agent.exceptions.llm import LLMConnectionError

logger = logging.getLogger(__name__)


class CopilotProvider(BaseLLMProvider):
    """
    GitHub Copilot API Gateway provider.
    
    Uses the GitHub Copilot API Gateway VS Code extension to access
    Copilot's LLM through a local OpenAI-compatible API.
    
    Requires the extension to be running and the server started.
    
    Example:
        >>> provider = CopilotProvider(base_url="http://localhost:5100")
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
        Initialize the Copilot provider.
        
        Args:
            api_key: Not used (authentication handled by extension)
            model: Model to use (default: gpt-4o)
            base_url: Gateway URL (default: http://localhost:5100)
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, model, base_url, timeout)
        self._base_url = base_url or os.getenv("COPILOT_API_URL", "http://localhost:5100")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "copilot"
    
    @property
    def default_model(self) -> str:
        return "gpt-4o"
    
    @property
    def supports_vision(self) -> bool:
        return True
    
    @property
    def supports_tools(self) -> bool:
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
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
        Generate a completion via the Copilot API Gateway.
        
        Uses OpenAI-compatible API format.
        """
        client = await self._get_client()
        model_name = self._get_model(model)
        
        # Format messages (OpenAI-compatible)
        formatted_messages = self._format_messages(messages)
        
        request_body: dict = {
            "model": model_name,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            request_body["max_tokens"] = max_tokens
        
        if tools:
            request_body["tools"] = [
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
        
        try:
            response = await client.post(
                "/v1/chat/completions",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data["choices"][0]
            usage_data = data.get("usage", {})
            
            return LLMResponse(
                content=choice["message"]["content"] or "",
                model=data.get("model", model_name),
                usage=Usage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                ),
                finish_reason=choice.get("finish_reason", "stop"),
                raw_response=data,
            )
            
        except httpx.ConnectError:
            raise LLMConnectionError(
                f"Cannot connect to Copilot API Gateway at {self._base_url}. "
                "Make sure the extension is running and the server is started."
            )
        except httpx.HTTPStatusError as e:
            raise LLMConnectionError(f"Copilot API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise LLMConnectionError(f"Copilot API error: {e}")
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        # TODO: Implement streaming
        raise NotImplementedError("Copilot streaming not yet implemented")
        yield
    
    async def health_check(self) -> bool:
        """Check if the Copilot API Gateway is available."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
