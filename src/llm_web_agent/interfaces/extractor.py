"""
Data Extractor Interface - Abstract base classes for page state extraction.

This module defines the contract for extracting structured information
from web pages for use by the LLM planner.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage, ElementHandle


@dataclass
class InteractiveElement:
    """
    An interactive element on the page.
    
    Attributes:
        index: Unique index for referencing this element
        tag: HTML tag name
        role: ARIA role or inferred role
        text: Visible text content
        selector: CSS selector for this element
        attributes: Relevant attributes (href, placeholder, etc.)
        is_visible: Whether the element is visible
        bounding_box: Position and size of the element
    """
    index: int
    tag: str
    role: str
    text: str
    selector: str
    attributes: Dict[str, str] = field(default_factory=dict)
    is_visible: bool = True
    bounding_box: Optional[Dict[str, float]] = None


@dataclass
class PageState:
    """
    Structured representation of the current page state.
    
    This is passed to the LLM to help it understand what's on the page
    and make decisions about which actions to take.
    
    Attributes:
        url: Current page URL
        title: Page title
        interactive_elements: List of clickable/interactive elements
        forms: List of forms on the page
        text_content: Visible text content (possibly summarized)
        screenshot_base64: Optional base64-encoded screenshot
        metadata: Additional page metadata
    """
    url: str
    title: str
    interactive_elements: List[InteractiveElement] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    text_content: str = ""
    screenshot_base64: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        """
        Convert page state to a string suitable for LLM prompts.
        
        Returns:
            A formatted string describing the page state
        """
        lines = [
            f"Current URL: {self.url}",
            f"Page Title: {self.title}",
            "",
            "Interactive Elements:",
        ]
        
        for elem in self.interactive_elements[:50]:  # Limit to first 50
            elem_str = f"  [{elem.index}] <{elem.tag}>"
            if elem.role:
                elem_str += f" role='{elem.role}'"
            if elem.text:
                elem_str += f" '{elem.text[:50]}'"
            lines.append(elem_str)
        
        if len(self.interactive_elements) > 50:
            lines.append(f"  ... and {len(self.interactive_elements) - 50} more elements")
        
        return "\n".join(lines)


class IDataExtractor(ABC):
    """
    Abstract interface for extracting structured data from pages.
    
    Implementations should efficiently extract relevant information
    from web pages for use by the LLM planner.
    """

    @abstractmethod
    async def extract_page_state(
        self,
        page: "IPage",
        include_screenshot: bool = False,
        max_elements: int = 100,
    ) -> PageState:
        """
        Extract the current state of a page.
        
        Args:
            page: The browser page to extract from
            include_screenshot: Whether to include a screenshot
            max_elements: Maximum number of elements to include
            
        Returns:
            A PageState object describing the page
        """
        ...

    @abstractmethod
    async def extract_interactive_elements(
        self,
        page: "IPage",
        max_elements: int = 100,
    ) -> List[InteractiveElement]:
        """
        Extract all interactive elements from the page.
        
        Args:
            page: The browser page to extract from
            max_elements: Maximum number of elements to return
            
        Returns:
            List of interactive elements
        """
        ...

    @abstractmethod
    async def extract_forms(self, page: "IPage") -> List[Dict[str, Any]]:
        """
        Extract all forms from the page.
        
        Args:
            page: The browser page to extract from
            
        Returns:
            List of form descriptions with their fields
        """
        ...

    @abstractmethod
    async def extract_text_content(
        self,
        page: "IPage",
        max_length: int = 5000,
    ) -> str:
        """
        Extract the visible text content from the page.
        
        Args:
            page: The browser page to extract from
            max_length: Maximum length of text to return
            
        Returns:
            The visible text content
        """
        ...

    @abstractmethod
    async def find_element_by_description(
        self,
        page: "IPage",
        description: str,
    ) -> Optional["ElementHandle"]:
        """
        Find an element matching a natural language description.
        
        Args:
            page: The browser page to search
            description: Natural language description of the element
            
        Returns:
            The matching element, or None if not found
        """
        ...
