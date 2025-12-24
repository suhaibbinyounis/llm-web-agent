"""
LLM Web Agent - A universal browser automation agent powered by large language models.

This package provides a modular, extensible framework for automating web browsers
using natural language instructions processed by LLMs.

Example:
    >>> from llm_web_agent import Agent
    >>> agent = Agent()
    >>> await agent.run("Go to google.com and search for Python tutorials")
"""

__version__ = "0.1.0"
__author__ = "Suhaib Bin Younis"

# Public API exports
from llm_web_agent.core.agent import Agent
from llm_web_agent.config.settings import Settings
from llm_web_agent.registry.registry import ComponentRegistry

__all__ = [
    "Agent",
    "Settings",
    "ComponentRegistry",
    "__version__",
]
