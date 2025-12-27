"""
LLM Providers - Concrete implementations of the LLM interface.

Available providers:
- OpenAIProvider: HTTP REST-based (default)
- WebSocketLLMProvider: WebSocket-based (lower latency)
- HybridLLMProvider: Auto-switches between WebSocket and HTTP
"""

from llm_web_agent.llm.openai_provider import OpenAIProvider
from llm_web_agent.llm.websocket_provider import WebSocketLLMProvider
from llm_web_agent.llm.hybrid_provider import HybridLLMProvider, create_provider

__all__ = [
    "OpenAIProvider",
    "WebSocketLLMProvider",
    "HybridLLMProvider",
    "create_provider",
]

