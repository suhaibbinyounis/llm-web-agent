"""
Selector Generator - Generate robust CSS/XPath selectors.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class SelectorStrategy(Enum):
    """Strategies for generating selectors."""
    ID = "id"
    DATA_TESTID = "data-testid"
    NAME = "name"
    ARIA_LABEL = "aria-label"
    CSS_CLASS = "css-class"
    XPATH_TEXT = "xpath-text"
    COMBINED = "combined"


@dataclass
class GeneratedSelector:
    """
    A generated selector with metadata.
    
    Attributes:
        selector: The CSS or XPath selector
        strategy: Strategy used to generate
        confidence: Confidence score (0-1)
        is_unique: Whether selector is unique on page
    """
    selector: str
    strategy: SelectorStrategy
    confidence: float
    is_unique: bool


class SelectorGenerator:
    """
    Generate robust selectors for elements.
    
    Creates multiple selector options prioritizing:
    1. ID attributes
    2. data-testid attributes
    3. ARIA labels
    4. Unique CSS class combinations
    5. XPath with text content
    
    Example:
        >>> generator = SelectorGenerator()
        >>> selectors = generator.generate(element_attributes)
        >>> best = selectors[0]  # Highest confidence
    """
    
    def __init__(self):
        """Initialize the generator."""
        self._priority = [
            SelectorStrategy.ID,
            SelectorStrategy.DATA_TESTID,
            SelectorStrategy.NAME,
            SelectorStrategy.ARIA_LABEL,
            SelectorStrategy.CSS_CLASS,
            SelectorStrategy.XPATH_TEXT,
        ]
    
    def generate(
        self,
        tag: str,
        attributes: Dict[str, str],
        text: str = "",
        parent_context: Optional[str] = None,
    ) -> List[GeneratedSelector]:
        """
        Generate selectors for an element.
        
        Args:
            tag: HTML tag name
            attributes: Element attributes
            text: Element text content
            parent_context: Parent selector for context
            
        Returns:
            List of selectors sorted by confidence
        """
        selectors = []
        
        # ID selector (highest confidence)
        if "id" in attributes:
            selectors.append(GeneratedSelector(
                selector=f"#{attributes['id']}",
                strategy=SelectorStrategy.ID,
                confidence=0.95,
                is_unique=True,
            ))
        
        # data-testid selector
        if "data-testid" in attributes:
            selectors.append(GeneratedSelector(
                selector=f"[data-testid='{attributes['data-testid']}']",
                strategy=SelectorStrategy.DATA_TESTID,
                confidence=0.90,
                is_unique=True,
            ))
        
        # name selector
        if "name" in attributes:
            selectors.append(GeneratedSelector(
                selector=f"{tag}[name='{attributes['name']}']",
                strategy=SelectorStrategy.NAME,
                confidence=0.85,
                is_unique=True,
            ))
        
        # aria-label selector
        if "aria-label" in attributes:
            selectors.append(GeneratedSelector(
                selector=f"[aria-label='{attributes['aria-label']}']",
                strategy=SelectorStrategy.ARIA_LABEL,
                confidence=0.80,
                is_unique=True,
            ))
        
        # Text-based XPath
        if text and len(text) > 0 and len(text) < 50:
            selectors.append(GeneratedSelector(
                selector=f"//{tag}[contains(text(), '{text[:30]}')]",
                strategy=SelectorStrategy.XPATH_TEXT,
                confidence=0.70,
                is_unique=False,
            ))
        
        # Sort by confidence
        selectors.sort(key=lambda s: s.confidence, reverse=True)
        
        return selectors
    
    def get_best_selector(
        self,
        tag: str,
        attributes: Dict[str, str],
        text: str = "",
    ) -> Optional[str]:
        """
        Get the best selector for an element.
        
        Args:
            tag: HTML tag
            attributes: Element attributes
            text: Element text
            
        Returns:
            Best selector string or None
        """
        selectors = self.generate(tag, attributes, text)
        return selectors[0].selector if selectors else None
