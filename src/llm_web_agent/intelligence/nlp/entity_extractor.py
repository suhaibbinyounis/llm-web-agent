"""
Entity Extractor - Extract entities from natural language.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import re


class EntityType(Enum):
    """Types of entities that can be extracted."""
    URL = "url"
    EMAIL = "email"
    SELECTOR = "selector"
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    ELEMENT_REF = "element_ref"  # e.g., "the login button"
    FILE_PATH = "file_path"


@dataclass
class Entity:
    """
    An extracted entity.
    
    Attributes:
        entity_type: Type of entity
        value: Entity value
        start: Start position in text
        end: End position in text
        confidence: Confidence score
    """
    entity_type: EntityType
    value: str
    start: int
    end: int
    confidence: float = 1.0


class EntityExtractor:
    """
    Extract entities from natural language text.
    
    Identifies URLs, emails, selectors, element references,
    and other entities from user instructions.
    
    Example:
        >>> extractor = EntityExtractor()
        >>> entities = extractor.extract("Go to https://google.com")
        >>> print(entities[0].value)  # "https://google.com"
    """
    
    # Regex patterns for entity extraction
    PATTERNS = {
        EntityType.URL: re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+'
        ),
        EntityType.EMAIL: re.compile(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        ),
        EntityType.SELECTOR: re.compile(
            r'[#.][a-zA-Z][a-zA-Z0-9_-]*|'
            r'\[[a-zA-Z-]+=[^\]]+\]'
        ),
        EntityType.FILE_PATH: re.compile(
            r'(?:/[^/\s]+)+|'
            r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'
        ),
    }
    
    # Patterns for element references
    ELEMENT_PATTERNS = [
        r'the\s+([a-zA-Z]+\s+)?button',
        r'the\s+([a-zA-Z]+\s+)?link',
        r'the\s+([a-zA-Z]+\s+)?input',
        r'the\s+([a-zA-Z]+\s+)?field',
        r'the\s+([a-zA-Z]+\s+)?checkbox',
        r'the\s+([a-zA-Z]+\s+)?dropdown',
    ]
    
    def __init__(self):
        """Initialize the extractor."""
        self._element_pattern = re.compile(
            '|'.join(f'({p})' for p in self.ELEMENT_PATTERNS),
            re.IGNORECASE
        )
    
    def extract(self, text: str) -> List[Entity]:
        """
        Extract all entities from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            List of extracted entities
        """
        entities = []
        
        # Extract using regex patterns
        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append(Entity(
                    entity_type=entity_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                ))
        
        # Extract element references
        for match in self._element_pattern.finditer(text):
            entities.append(Entity(
                entity_type=EntityType.ELEMENT_REF,
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.8,
            ))
        
        # Sort by position
        entities.sort(key=lambda e: e.start)
        
        return entities
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract all URLs from text."""
        return [e.value for e in self.extract(text) if e.entity_type == EntityType.URL]
    
    def extract_element_refs(self, text: str) -> List[str]:
        """Extract all element references from text."""
        return [e.value for e in self.extract(text) if e.entity_type == EntityType.ELEMENT_REF]
