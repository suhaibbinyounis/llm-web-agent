"""
NLP submodule - Natural language processing for task understanding.
"""

from llm_web_agent.intelligence.nlp.intent_parser import IntentParser, Intent
from llm_web_agent.intelligence.nlp.entity_extractor import EntityExtractor, Entity

__all__ = [
    "IntentParser",
    "Intent",
    "EntityExtractor",
    "Entity",
]
