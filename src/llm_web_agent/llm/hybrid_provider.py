"""
Hybrid LLM Provider - WebSocket primary with HTTP fallback.

Automatically uses WebSocket for low latency when available,
falls back to HTTP REST when WebSocket is unavailable.
"""

import asyncio
import logging
from typing import Any, AsyncIterator, List, Optional

from llm_web_agent.interfaces.llm import (
    ILLMProvider,
    Message,
    LLMResponse,
    ToolDefinition,
)
from llm_web_agent.llm.openai_provider import OpenAIProvider
from llm_web_agent.llm.websocket_provider import WebSocketLLMProvider, ConnectionState

logger = logging.getLogger(__name__)


class HybridLLMProvider(ILLMProvider):
    """
    Hybrid LLM provider with WebSocket primary and HTTP fallback.
    
    Benefits:
    - WebSocket: Persistent connection, lower latency
    - HTTP: Always available, no special server support needed
    
    The provider automatically:
    - Tries WebSocket first
    - Falls back to HTTP on WebSocket failure
    - Periodically retries WebSocket if it failed
    
    Example:
        >>> provider = HybridLLMProvider(
        ...     ws_url="ws://127.0.0.1:3030/ws/chat",
        ...     http_url="http://127.0.0.1:3030"
        ... )
        >>> response = await provider.complete([Message.user("Hello!")])
    """
    
    def __init__(
        self,
        ws_url: str = "ws://127.0.0.1:3030/v1/realtime",
        http_url: str = "http://127.0.0.1:3030",
        api_key: Optional[str] = None,
        model: str = "gpt-4.1",
        timeout: float = 120.0,
        prefer_websocket: bool = True,
        ws_retry_interval: float = 60.0,
    ):
        """
        Initialize the hybrid provider.
        
        Args:
            ws_url: WebSocket URL for the LLM server
            http_url: HTTP URL for the LLM server
            api_key: Optional API key
            model: Default model to use
            timeout: Request timeout in seconds
            prefer_websocket: Whether to try WebSocket first
            ws_retry_interval: Seconds before retrying WebSocket after failure
        """
        self._ws_url = ws_url
        self._http_url = http_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._prefer_websocket = prefer_websocket
        self._ws_retry_interval = ws_retry_interval
        
        # Initialize providers
        self._ws_provider = WebSocketLLMProvider(
            ws_url=ws_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
        
        self._http_provider = OpenAIProvider(
            base_url=http_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
        
        # State
        self._use_websocket = prefer_websocket
        self._ws_last_failed = 0.0
        self._ws_available = None  # None = unknown, True/False = tested
        self._connection_task: Optional[asyncio.Task] = None
        
        # Stats
        self._ws_requests = 0
        self._http_requests = 0
        self._ws_failures = 0
    
    @property
    def name(self) -> str:
        return "hybrid"
    
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
    
    @property
    def active_transport(self) -> str:
        """Get the currently active transport."""
        if self._use_websocket and self._ws_provider.is_connected:
            return "websocket"
        return "http"
    
    @property
    def stats(self) -> dict:
        """Get usage statistics."""
        return {
            "websocket_requests": self._ws_requests,
            "http_requests": self._http_requests,
            "websocket_failures": self._ws_failures,
            "active_transport": self.active_transport,
            "websocket_connected": self._ws_provider.is_connected,
        }
    
    async def connect(self) -> bool:
        """
        Establish connections.
        
        Tries WebSocket first if preferred, then verifies HTTP.
        """
        ws_connected = False
        
        if self._prefer_websocket:
            try:
                ws_connected = await self._ws_provider.connect()
                self._ws_available = ws_connected
                
                if ws_connected:
                    logger.info("WebSocket connection established")
                else:
                    logger.info("WebSocket unavailable, using HTTP")
                    
            except Exception as e:
                logger.warning(f"WebSocket connection failed: {e}")
                self._ws_available = False
        
        # Verify HTTP is available
        http_available = await self._http_provider.health_check()
        
        if not http_available:
            logger.warning("HTTP endpoint may not be available")
        
        self._use_websocket = ws_connected
        
        return ws_connected or http_available
    
    async def _try_websocket_reconnect(self) -> bool:
        """Try to reconnect WebSocket if enough time has passed."""
        import time
        
        if not self._prefer_websocket:
            return False
        
        if self._ws_provider.is_connected:
            return True
        
        # Check if enough time has passed since last failure
        now = time.time()
        if now - self._ws_last_failed < self._ws_retry_interval:
            return False
        
        try:
            connected = await self._ws_provider.connect()
            if connected:
                self._use_websocket = True
                logger.info("WebSocket reconnected successfully")
                return True
        except Exception as e:
            logger.debug(f"WebSocket reconnection failed: {e}")
        
        self._ws_last_failed = now
        return False
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using best available transport."""
        import time
        
        # Try WebSocket reconnection in background
        if not self._ws_provider.is_connected and self._prefer_websocket:
            asyncio.create_task(self._try_websocket_reconnect())
        
        # Try WebSocket first
        if self._use_websocket and self._ws_provider.is_connected:
            try:
                self._ws_requests += 1
                return await self._ws_provider.complete(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(f"WebSocket request failed, falling back to HTTP: {e}")
                self._ws_failures += 1
                self._ws_last_failed = time.time()
                self._use_websocket = False
        
        # Fall back to HTTP
        self._http_requests += 1
        return await self._http_provider.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs,
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
        # Try WebSocket if connected
        if self._use_websocket and self._ws_provider.is_connected:
            try:
                async for chunk in self._ws_provider.stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"WebSocket streaming failed: {e}")
        
        # Fall back to HTTP
        async for chunk in self._http_provider.stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk
    
    async def count_tokens(self, messages: List[Message], model: Optional[str] = None) -> int:
        """Estimate token count."""
        return await self._http_provider.count_tokens(messages, model)
    
    async def health_check(self) -> bool:
        """Check if any transport is available."""
        if self._ws_provider.is_connected:
            return True
        return await self._http_provider.health_check()
    
    async def close(self) -> None:
        """Close both providers."""
        await self._ws_provider.close()
        await self._http_provider.close()


def create_provider(
    base_url: str = "http://127.0.0.1:3030",
    api_key: Optional[str] = None,
    model: str = "gpt-4.1",
    use_websocket: bool = False,
) -> ILLMProvider:
    """
    Create the appropriate LLM provider.
    
    Args:
        base_url: Base URL for the LLM server
        api_key: Optional API key
        model: Model to use
        use_websocket: Whether to enable WebSocket mode
        
    Returns:
        Configured LLM provider
    """
    if use_websocket:
        # Convert HTTP URL to WebSocket URL
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = ws_url.rstrip("/") + "/v1/realtime"
        
        return HybridLLMProvider(
            ws_url=ws_url,
            http_url=base_url,
            api_key=api_key,
            model=model,
        )
    
    return OpenAIProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
