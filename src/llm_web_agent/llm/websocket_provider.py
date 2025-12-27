"""
WebSocket LLM Provider - Persistent connection for lower latency.

Features:
- Persistent WebSocket connection (always ready)
- Automatic reconnection with exponential backoff
- Request/response correlation via UUIDs
- Concurrent request support
- Heartbeat/ping-pong for connection health
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

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


class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class PendingRequest:
    """A pending request awaiting response."""
    request_id: str
    future: asyncio.Future
    created_at: float
    timeout: float


class WebSocketLLMProvider(ILLMProvider):
    """
    WebSocket-based LLM provider with persistent connection.
    
    Maintains a single WebSocket connection to the LLM server,
    enabling faster request/response cycles by avoiding HTTP overhead.
    
    Example:
        >>> provider = WebSocketLLMProvider(
        ...     ws_url="ws://127.0.0.1:3030/ws/chat"
        ... )
        >>> await provider.connect()
        >>> response = await provider.complete([Message.user("Hello!")])
    """
    
    def __init__(
        self,
        ws_url: str = "ws://127.0.0.1:3030/v1/realtime",
        api_key: Optional[str] = None,
        model: str = "gpt-4.1",
        timeout: float = 120.0,
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        heartbeat_interval: float = 30.0,
    ):
        """
        Initialize the WebSocket provider.
        
        Args:
            ws_url: WebSocket URL for the LLM server
            api_key: Optional API key
            model: Default model to use
            timeout: Request timeout in seconds
            reconnect_attempts: Max reconnection attempts
            reconnect_delay: Initial delay between reconnects (exponential backoff)
            heartbeat_interval: Seconds between heartbeat pings
        """
        self._ws_url = ws_url
        self._api_key = api_key or "not-needed"
        self._model = model
        self._timeout = timeout
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._heartbeat_interval = heartbeat_interval
        
        # Connection state
        self._ws = None
        self._state = ConnectionState.DISCONNECTED
        self._pending_requests: Dict[str, PendingRequest] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
    
    @property
    def name(self) -> str:
        return "websocket"
    
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
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        
        Returns:
            True if connected successfully
        """
        if self._state == ConnectionState.CONNECTED:
            return True
        
        self._state = ConnectionState.CONNECTING
        
        try:
            import websockets
            
            headers = {"Authorization": f"Bearer {self._api_key}"}
            
            self._ws = await websockets.connect(
                self._ws_url,
                extra_headers=headers,
                ping_interval=self._heartbeat_interval,
                ping_timeout=10,
            )
            
            self._state = ConnectionState.CONNECTED
            
            # Start listener
            self._listen_task = asyncio.create_task(self._listen_loop())
            
            logger.info(f"WebSocket connected to {self._ws_url}")
            
            if self._on_connect:
                self._on_connect()
            
            return True
            
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets")
            self._state = ConnectionState.DISCONNECTED
            return False
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self._state = ConnectionState.DISCONNECTED
            return False
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._state = ConnectionState.DISCONNECTED
        
        # Cancel tasks
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        # Fail pending requests
        for req in self._pending_requests.values():
            if not req.future.done():
                req.future.set_exception(ConnectionError("WebSocket disconnected"))
        
        self._pending_requests.clear()
        
        logger.info("WebSocket disconnected")
        
        if self._on_disconnect:
            self._on_disconnect()
    
    async def _listen_loop(self) -> None:
        """Listen for incoming WebSocket messages."""
        import websockets
        
        try:
            async for message in self._ws:
                await self._handle_message(message)
                
        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            asyncio.create_task(self._reconnect())
            
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")
            asyncio.create_task(self._reconnect())
    
    async def _handle_message(self, raw_message: str) -> None:
        """Handle an incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            
            request_id = data.get("request_id")
            msg_type = data.get("type", "")
            
            if not request_id or request_id not in self._pending_requests:
                logger.debug(f"Received message for unknown request: {request_id}")
                return
            
            pending = self._pending_requests[request_id]
            
            if msg_type == "chat.completions.response":
                # Full response
                payload = data.get("payload", {})
                response = self._parse_response(payload)
                
                if not pending.future.done():
                    pending.future.set_result(response)
                
                del self._pending_requests[request_id]
                
            elif msg_type == "chat.completions.error":
                # Error response
                error = data.get("error", "Unknown error")
                
                if not pending.future.done():
                    pending.future.set_exception(Exception(error))
                
                del self._pending_requests[request_id]
                
            elif msg_type == "chat.completions.chunk":
                # Streaming chunk - handled separately
                pass
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
    
    def _parse_response(self, data: Dict) -> LLMResponse:
        """Parse OpenAI-format response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        # Extract tool calls
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
            model=data.get("model", self._model),
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._state == ConnectionState.RECONNECTING:
            return
        
        self._state = ConnectionState.RECONNECTING
        
        for attempt in range(self._reconnect_attempts):
            delay = self._reconnect_delay * (2 ** attempt)
            
            logger.info(f"Reconnecting in {delay}s (attempt {attempt + 1}/{self._reconnect_attempts})")
            await asyncio.sleep(delay)
            
            if await self.connect():
                return
        
        logger.error("Max reconnection attempts reached")
        self._state = ConnectionState.DISCONNECTED
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion via WebSocket."""
        import time
        
        if not self.is_connected:
            connected = await self.connect()
            if not connected:
                raise ConnectionError("WebSocket not connected")
        
        model = model or self._model
        request_id = str(uuid.uuid4())
        
        # Format messages
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
        
        # Build payload
        payload = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if tools:
            payload["tools"] = [
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
        
        payload.update(kwargs)
        
        # Create request
        request = {
            "request_id": request_id,
            "type": "chat.completions",
            "payload": payload,
        }
        
        # Create future
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        self._pending_requests[request_id] = PendingRequest(
            request_id=request_id,
            future=future,
            created_at=time.time(),
            timeout=self._timeout,
        )
        
        try:
            # Send request
            await self._ws.send(json.dumps(request))
            
            # Wait for response with timeout
            return await asyncio.wait_for(future, timeout=self._timeout)
            
        except asyncio.TimeoutError:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            raise TimeoutError(f"Request timed out after {self._timeout}s")
            
        except Exception as e:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion via WebSocket."""
        # For now, fall back to non-streaming
        # Full streaming implementation would require async queue
        response = await self.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        yield response.content
    
    async def count_tokens(self, messages: List[Message], model: Optional[str] = None) -> int:
        """Estimate token count."""
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4
    
    async def health_check(self) -> bool:
        """Check connection health."""
        return self.is_connected
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        await self.disconnect()
