"""
LLM Strategy - Unified LLM interaction layer for the engine.

This module provides:
- Prompt templates for all LLM use cases
- Structured output schemas
- Response parsing
- Token management
- Caching and optimization
"""

from llm_web_agent.engine.llm.prompts import (
    INSTRUCTION_PARSE_PROMPT,
    ELEMENT_FIND_PROMPT,
    ACTION_PLAN_PROMPT,
    ERROR_RECOVERY_PROMPT,
    PromptBuilder,
)
from llm_web_agent.engine.llm.schemas import (
    ParsedInstruction,
    ParsedStep,
    FoundElement,
    ActionPlan,
    LLMResponse,
)
from llm_web_agent.engine.llm.strategy import LLMStrategy
from llm_web_agent.engine.llm.dom_simplifier import DOMSimplifier, SimplifiedDOM

__all__ = [
    # Prompts
    "INSTRUCTION_PARSE_PROMPT",
    "ELEMENT_FIND_PROMPT",
    "ACTION_PLAN_PROMPT",
    "ERROR_RECOVERY_PROMPT",
    "PromptBuilder",
    # Schemas
    "ParsedInstruction",
    "ParsedStep",
    "FoundElement",
    "ActionPlan",
    "LLMResponse",
    # Strategy
    "LLMStrategy",
    # DOM
    "DOMSimplifier",
    "SimplifiedDOM",
]
