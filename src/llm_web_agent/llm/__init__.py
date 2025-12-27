"""
LLM Providers - Concrete implementations of the LLM interface.

Available providers:
- OpenAIProvider: HTTP REST-based (default)
- WebSocketLLMProvider: WebSocket-based (lower latency)
- HybridLLMProvider: Auto-switches between WebSocket and HTTP
- LLMConnectionPool: Singleton pool for connection reuse across runs
"""

from llm_web_agent.llm.openai_provider import OpenAIProvider
from llm_web_agent.llm.websocket_provider import WebSocketLLMProvider
from llm_web_agent.llm.hybrid_provider import HybridLLMProvider, create_provider
from llm_web_agent.llm.connection_pool import LLMConnectionPool, get_pooled_provider

__all__ = [
    "OpenAIProvider",
    "WebSocketLLMProvider",
    "HybridLLMProvider",
    "create_provider",
    "LLMConnectionPool",
    "get_pooled_provider",
]
