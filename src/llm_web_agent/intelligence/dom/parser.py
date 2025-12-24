"""
DOM Parser - Parse and analyze HTML DOM structure.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage


class ElementRole(Enum):
    """Semantic roles for elements."""
    BUTTON = "button"
    LINK = "link"
    INPUT = "input"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    TEXTAREA = "textarea"
    HEADING = "heading"
    IMAGE = "image"
    LIST = "list"
    TABLE = "table"
    FORM = "form"
    NAVIGATION = "navigation"
    MAIN = "main"
    FOOTER = "footer"
    UNKNOWN = "unknown"


@dataclass
class ParsedElement:
    """
    A parsed DOM element with semantic information.
    
    Attributes:
        tag: HTML tag name
        role: Semantic role
        text: Visible text content
        selector: CSS selector for this element
        attributes: Element attributes
        bounding_box: Position and size
        is_interactive: Whether element accepts input
        is_visible: Whether element is visible
        children_count: Number of child elements
    """
    tag: str
    role: ElementRole
    text: str
    selector: str
    attributes: Dict[str, str] = field(default_factory=dict)
    bounding_box: Optional[Dict[str, float]] = None
    is_interactive: bool = False
    is_visible: bool = True
    children_count: int = 0


@dataclass
class ParsedDOM:
    """
    Parsed DOM structure.
    
    Attributes:
        url: Page URL
        title: Page title
        elements: All parsed elements
        interactive_elements: Only interactive elements
        forms: Detected forms
        main_content: Main content text
    """
    url: str
    title: str
    elements: List[ParsedElement] = field(default_factory=list)
    interactive_elements: List[ParsedElement] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    main_content: str = ""


class DOMParser:
    """
    Parse DOM from a browser page.
    
    Example:
        >>> parser = DOMParser()
        >>> dom = await parser.parse(page)
        >>> for elem in dom.interactive_elements:
        ...     print(f"{elem.role}: {elem.text}")
    """
    
    # Elements that are typically interactive
    INTERACTIVE_TAGS = {
        "a", "button", "input", "select", "textarea",
        "details", "summary", "[onclick]", "[tabindex]",
    }
    
    # Map tags to roles
    TAG_ROLE_MAP = {
        "a": ElementRole.LINK,
        "button": ElementRole.BUTTON,
        "input": ElementRole.INPUT,
        "select": ElementRole.SELECT,
        "textarea": ElementRole.TEXTAREA,
        "h1": ElementRole.HEADING,
        "h2": ElementRole.HEADING,
        "h3": ElementRole.HEADING,
        "h4": ElementRole.HEADING,
        "h5": ElementRole.HEADING,
        "h6": ElementRole.HEADING,
        "img": ElementRole.IMAGE,
        "nav": ElementRole.NAVIGATION,
        "main": ElementRole.MAIN,
        "form": ElementRole.FORM,
        "table": ElementRole.TABLE,
        "ul": ElementRole.LIST,
        "ol": ElementRole.LIST,
    }
    
    async def parse(
        self,
        page: "IPage",
        include_hidden: bool = False,
        max_elements: int = 500,
    ) -> ParsedDOM:
        """
        Parse the DOM of a page.
        
        Args:
            page: Browser page to parse
            include_hidden: Include hidden elements
            max_elements: Maximum elements to parse
            
        Returns:
            Parsed DOM structure
        """
        # TODO: Implement DOM parsing
        # This will use JavaScript injection to extract DOM structure
        raise NotImplementedError("DOM parsing not yet implemented")
    
    async def find_element_by_description(
        self,
        page: "IPage",
        description: str,
    ) -> Optional[ParsedElement]:
        """
        Find an element matching a natural language description.
        
        Args:
            page: Browser page
            description: Natural language description (e.g., "login button")
            
        Returns:
            Matching element or None
        """
        # TODO: Implement NL element matching
        raise NotImplementedError("Element matching not yet implemented")
    
    def _infer_role(self, tag: str, attributes: Dict[str, str]) -> ElementRole:
        """Infer element role from tag and attributes."""
        # Check ARIA role first
        if "role" in attributes:
            try:
                return ElementRole(attributes["role"])
            except ValueError:
                pass
        
        # Check input type for more specific role
        if tag == "input":
            input_type = attributes.get("type", "text")
            if input_type == "checkbox":
                return ElementRole.CHECKBOX
            elif input_type == "radio":
                return ElementRole.RADIO
            elif input_type in ("submit", "button"):
                return ElementRole.BUTTON
        
        return self.TAG_ROLE_MAP.get(tag, ElementRole.UNKNOWN)
