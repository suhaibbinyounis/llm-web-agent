"""
DOM submodule - Page understanding and element extraction.
"""

from llm_web_agent.intelligence.dom.parser import DOMParser
from llm_web_agent.intelligence.dom.simplifier import DOMSimplifier
from llm_web_agent.intelligence.dom.selector_generator import SelectorGenerator

__all__ = [
    "DOMParser",
    "DOMSimplifier",
    "SelectorGenerator",
]
