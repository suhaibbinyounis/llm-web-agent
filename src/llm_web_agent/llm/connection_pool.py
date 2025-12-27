"""
LLM Connection Pool - Singleton connection pool for WebSocket and HTTP LLM providers.

Provides:
- Shared WebSocket connection across multiple runs
- Automatic reconnection on failure
- Connection health monitoring
- Fallback to HTTP when WebSocket unavailable
"""

import asyncio
import logging
import time
from typing import Optional

from llm_web_agent.interfaces.llm import ILLMProvider
from llm_web_agent.llm.websocket_provider import WebSocketLLMProvider, ConnectionState
from llm_web_agent.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class LLMConnectionPool:
    """
    Singleton connection pool for LLM providers.
    
    Maintains a persistent WebSocket connection that is reused across
    multiple runs, avoiding connection setup overhead.
    
    Usage:
        pool = LLMConnectionPool.get_instance(ws_url="ws://...", http_url="http://...")
        provider = await pool.get_provider()
        response = await provider.complete(messages)
        # Connection stays alive for next run
    """
    
    _instance: Optional["LLMConnectionPool"] = None
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        ws_url: str = "ws://127.0.0.1:3030/v1/realtime",
        http_url: str = "http://127.0.0.1:3030",
        api_key: Optional[str] = None,
        model: str = "gpt-4.1",
        timeout: float = 120.0,
        prefer_websocket: bool = True,
    ):
        """Initialize the connection pool (private, use get_instance())."""
        self._ws_url = ws_url
        self._http_url = http_url
        self._api_key = api_key or "not-needed"
        self._model = model
        self._timeout = timeout
        self._prefer_websocket = prefer_websocket
        
        # Providers
        self._ws_provider: Optional[WebSocketLLMProvider] = None
        self._http_provider: Optional[OpenAIProvider] = None
        
        # Stats
        self._ws_connections = 0
        self._http_fallbacks = 0
        self._last_ws_attempt = 0.0
        self._ws_retry_interval = 60.0  # Retry WS every 60s if failed
    
    @classmethod
    async def get_instance(
        cls,
        ws_url: str = "ws://127.0.0.1:3030/v1/realtime",
        http_url: str = "http://127.0.0.1:3030",
        api_key: Optional[str] = None,
        model: str = "gpt-4.1",
        prefer_websocket: bool = True,
        **kwargs,
    ) -> "LLMConnectionPool":
        """
        Get or create the singleton connection pool.
        
        Args:
            ws_url: WebSocket URL for LLM server
            http_url: HTTP URL for LLM server
            api_key: Optional API key
            model: Default model
            prefer_websocket: Whether to prefer WebSocket over HTTP
            
        Returns:
            Shared LLMConnectionPool instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(
                    ws_url=ws_url,
                    http_url=http_url,
                    api_key=api_key,
                    model=model,
                    prefer_websocket=prefer_websocket,
                    **kwargs,
                )
                logger.info("Created LLM connection pool")
            return cls._instance
    
    async def get_provider(self) -> ILLMProvider:
        """
        Get an LLM provider from the pool.
        
        Returns WebSocket provider if connected, otherwise HTTP.
        Automatically attempts WebSocket reconnection if needed.
        
        Returns:
            Active ILLMProvider
        """
        # Try WebSocket first if preferred
        if self._prefer_websocket:
            provider = await self._get_websocket_provider()
            if provider and provider.is_connected:
                return provider
        
        # Fallback to HTTP
        return await self._get_http_provider()
    
    async def _get_websocket_provider(self) -> Optional[WebSocketLLMProvider]:
        """Get or create WebSocket provider."""
        # Check if we should retry WS connection
        now = time.time()
        
        if self._ws_provider is None:
            # First connection attempt
            self._ws_provider = WebSocketLLMProvider(
                ws_url=self._ws_url,
                api_key=self._api_key,
                model=self._model,
                timeout=self._timeout,
            )
        
        # Connect if not connected
        if not self._ws_provider.is_connected:
            # Rate limit reconnection attempts
            if now - self._last_ws_attempt < self._ws_retry_interval:
                return None  # Too soon to retry
            
            self._last_ws_attempt = now
            try:
                connected = await self._ws_provider.connect()
                if connected:
                    self._ws_connections += 1
                    logger.info(f"WebSocket connected (connection #{self._ws_connections})")
                    return self._ws_provider
                else:
                    logger.warning("WebSocket connection failed, will use HTTP")
                    return None
            except Exception as e:
                logger.warning(f"WebSocket connection error: {e}")
                return None
        
        return self._ws_provider
    
    async def _get_http_provider(self) -> OpenAIProvider:
        """Get or create HTTP provider."""
        if self._http_provider is None:
            self._http_provider = OpenAIProvider(
                base_url=self._http_url,
                api_key=self._api_key,
                model=self._model,
                timeout=self._timeout,
            )
            logger.debug("Created HTTP provider")
        
        self._http_fallbacks += 1
        return self._http_provider
    
    @property
    def is_websocket_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return (
            self._ws_provider is not None
            and self._ws_provider.is_connected
        )
    
    @property
    def stats(self) -> dict:
        """Get connection pool statistics."""
        return {
            "ws_connections": self._ws_connections,
            "http_fallbacks": self._http_fallbacks,
            "ws_connected": self.is_websocket_connected,
            "active_transport": "websocket" if self.is_websocket_connected else "http",
        }
    
    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._ws_provider:
            await self._ws_provider.close()
            self._ws_provider = None
        
        if self._http_provider:
            await self._http_provider.close()
            self._http_provider = None
        
        logger.info(f"Connection pool closed. Stats: {self.stats}")
    
    @classmethod
    async def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        async with cls._lock:
            if cls._instance:
                await cls._instance.close()
                cls._instance = None


# Convenience function for getting provider
async def get_pooled_provider(
    ws_url: str = "ws://127.0.0.1:3030/v1/realtime",
    http_url: str = "http://127.0.0.1:3030",
    api_key: Optional[str] = None,
    model: str = "gpt-4.1",
    prefer_websocket: bool = True,
) -> ILLMProvider:
    """
    Get an LLM provider from the shared pool.
    
    This is the recommended way to get a provider for most use cases.
    The connection is reused across calls.
    """
    pool = await LLMConnectionPool.get_instance(
        ws_url=ws_url,
        http_url=http_url,
        api_key=api_key,
        model=model,
        prefer_websocket=prefer_websocket,
    )
    return await pool.get_provider()
