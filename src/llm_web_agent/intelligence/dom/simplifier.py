"""
DOM Simplifier - Reduce DOM to essential elements for LLM processing.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from llm_web_agent.intelligence.dom.parser import ParsedDOM, ParsedElement


@dataclass
class SimplifiedElement:
    """
    A simplified element representation for LLM consumption.
    
    Attributes:
        index: Unique index for referencing
        tag: HTML tag
        role: Semantic role
        text: Visible text (truncated)
        selector: CSS selector
        attributes: Key attributes only
    """
    index: int
    tag: str
    role: str
    text: str
    selector: str
    attributes: Dict[str, str]


@dataclass
class SimplifiedDOM:
    """
    Simplified DOM for LLM context.
    
    Attributes:
        url: Page URL
        title: Page title
        elements: List of simplified elements
        summary: Text summary of the page
    """
    url: str
    title: str
    elements: List[SimplifiedElement]
    summary: str = ""
    
    def to_prompt(self, max_elements: int = 50) -> str:
        """
        Convert to a string for LLM prompt.
        
        Args:
            max_elements: Maximum elements to include
            
        Returns:
            Formatted string for LLM consumption
        """
        lines = [
            f"URL: {self.url}",
            f"Title: {self.title}",
            "",
            "Interactive Elements:",
        ]
        
        for elem in self.elements[:max_elements]:
            attrs = " ".join(f'{k}="{v}"' for k, v in elem.attributes.items())
            text = elem.text[:50] + "..." if len(elem.text) > 50 else elem.text
            lines.append(f"[{elem.index}] <{elem.tag} {attrs}> {text}")
        
        if len(self.elements) > max_elements:
            lines.append(f"... and {len(self.elements) - max_elements} more elements")
        
        return "\n".join(lines)


class DOMSimplifier:
    """
    Simplify DOM for LLM consumption.
    
    Reduces the full DOM to only essential interactive elements
    with minimal attributes to fit in LLM context windows.
    
    Example:
        >>> simplifier = DOMSimplifier()
        >>> simplified = simplifier.simplify(parsed_dom)
        >>> prompt = simplified.to_prompt()
    """
    
    # Attributes to keep
    KEEP_ATTRIBUTES = {
        "id", "name", "type", "href", "placeholder",
        "aria-label", "title", "alt", "value", "data-testid",
    }
    
    def __init__(self, max_text_length: int = 100):
        """
        Initialize the simplifier.
        
        Args:
            max_text_length: Maximum text length per element
        """
        self.max_text_length = max_text_length
    
    def simplify(
        self,
        dom: ParsedDOM,
        interactive_only: bool = True,
        max_elements: int = 100,
    ) -> SimplifiedDOM:
        """
        Simplify a parsed DOM.
        
        Args:
            dom: Parsed DOM structure
            interactive_only: Only include interactive elements
            max_elements: Maximum elements to include
            
        Returns:
            Simplified DOM
        """
        source = dom.interactive_elements if interactive_only else dom.elements
        
        simplified_elements = []
        for i, elem in enumerate(source[:max_elements]):
            # Filter attributes
            filtered_attrs = {
                k: v for k, v in elem.attributes.items()
                if k in self.KEEP_ATTRIBUTES
            }
            
            # Truncate text
            text = elem.text[:self.max_text_length]
            if len(elem.text) > self.max_text_length:
                text += "..."
            
            simplified_elements.append(SimplifiedElement(
                index=i,
                tag=elem.tag,
                role=elem.role.value,
                text=text,
                selector=elem.selector,
                attributes=filtered_attrs,
            ))
        
        return SimplifiedDOM(
            url=dom.url,
            title=dom.title,
            elements=simplified_elements,
        )
    
    def get_element_by_index(
        self,
        simplified: SimplifiedDOM,
        index: int,
    ) -> Optional[SimplifiedElement]:
        """Get element by its index."""
        for elem in simplified.elements:
            if elem.index == index:
                return elem
        return None
