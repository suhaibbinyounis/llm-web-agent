"""
Prompts module - LLM prompt templates for planning and action selection.
"""

from llm_web_agent.prompts.system_prompts import (
    AGENT_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    ACTION_SELECTOR_PROMPT,
)

__all__ = [
    "AGENT_SYSTEM_PROMPT",
    "PLANNER_SYSTEM_PROMPT",
    "ACTION_SELECTOR_PROMPT",
]
