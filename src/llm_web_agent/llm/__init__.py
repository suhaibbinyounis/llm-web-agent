"""
LLM Providers module - LLM provider implementations.
"""

from llm_web_agent.llm.openai_provider import OpenAIProvider
from llm_web_agent.llm.base import BaseLLMProvider

__all__ = [
    "OpenAIProvider",
    "BaseLLMProvider",
]


def _register_providers() -> None:
    """Register LLM provider implementations with the registry."""
    from llm_web_agent.registry import ComponentRegistry
    
    # Register OpenAI (eager)
    ComponentRegistry.register_llm("openai")(OpenAIProvider)
    
    # Register Anthropic (lazy)
    def anthropic_factory():
        from llm_web_agent.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider
    
    ComponentRegistry.register_llm_factory("anthropic", anthropic_factory)
    
    # Register Copilot Gateway (lazy)
    def copilot_factory():
        from llm_web_agent.llm.copilot_provider import CopilotProvider
        return CopilotProvider
    
    ComponentRegistry.register_llm_factory("copilot", copilot_factory)


# Auto-register on import
_register_providers()
