"""
Intelligence Module - DOM parsing, NLP, and planning for web automation.

This module contains the core intelligence for understanding web pages,
parsing natural language instructions, and planning action sequences.
"""

from llm_web_agent.intelligence.dom.parser import DOMParser
from llm_web_agent.intelligence.dom.simplifier import DOMSimplifier
from llm_web_agent.intelligence.nlp.intent_parser import IntentParser
from llm_web_agent.intelligence.planning.task_decomposer import TaskDecomposer

__all__ = [
    "DOMParser",
    "DOMSimplifier",
    "IntentParser",
    "TaskDecomposer",
]
