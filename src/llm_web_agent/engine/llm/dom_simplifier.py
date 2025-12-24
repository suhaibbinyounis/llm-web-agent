"""
DOM Simplifier - Reduce DOM to LLM-friendly format.

Extracts only interactive and relevant elements to minimize token usage.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


@dataclass
class SimplifiedElement:
    """A simplified DOM element for LLM consumption."""
    index: int
    tag: str
    text: str = ""
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None
    value: Optional[str] = None
    selector: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM prompt."""
        result = {
            "index": self.index,
            "tag": self.tag,
        }
        if self.text:
            result["text"] = self.text[:100]  # Truncate
        if self.id:
            result["id"] = self.id
        if self.name:
            result["name"] = self.name
        if self.type:
            result["type"] = self.type
        if self.placeholder:
            result["placeholder"] = self.placeholder[:50]
        if self.aria_label:
            result["aria_label"] = self.aria_label[:50]
        if self.role:
            result["role"] = self.role
        if self.href:
            result["href"] = self.href[:100]
        if self.selector:
            result["selector"] = self.selector
        return result
    
    def to_line(self) -> str:
        """Convert to single-line string for compact display."""
        attrs = []
        if self.id:
            attrs.append(f"id={self.id}")
        if self.name:
            attrs.append(f"name={self.name}")
        if self.type:
            attrs.append(f"type={self.type}")
        if self.placeholder:
            attrs.append(f"placeholder=\"{self.placeholder[:30]}\"")
        if self.aria_label:
            attrs.append(f"aria-label=\"{self.aria_label[:30]}\"")
        if self.role:
            attrs.append(f"role={self.role}")
        
        attrs_str = " ".join(attrs)
        text_str = f' "{self.text[:40]}"' if self.text else ""
        
        return f"[{self.index}] <{self.tag}> {attrs_str}{text_str}".strip()


@dataclass
class SimplifiedDOM:
    """Simplified DOM representation for LLM."""
    url: str
    title: str
    elements: List[SimplifiedElement] = field(default_factory=list)
    
    @property
    def element_count(self) -> int:
        return len(self.elements)
    
    def get_element(self, index: int) -> Optional[SimplifiedElement]:
        """Get element by index."""
        for elem in self.elements:
            if elem.index == index:
                return elem
        return None
    
    def to_elements_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dicts for prompt building."""
        return [e.to_dict() for e in self.elements]
    
    def to_compact_string(self, max_elements: int = 100) -> str:
        """Convert to compact string representation."""
        lines = [f"URL: {self.url}", f"Title: {self.title}", ""]
        
        for elem in self.elements[:max_elements]:
            lines.append(elem.to_line())
        
        if len(self.elements) > max_elements:
            lines.append(f"... and {len(self.elements) - max_elements} more elements")
        
        return "\n".join(lines)


class DOMSimplifier:
    """
    Simplify DOM for LLM consumption.
    
    Extracts interactive elements and reduces to essential attributes
    to minimize token usage while preserving element identification.
    """
    
    # Tags of interactive elements
    INTERACTIVE_TAGS = {
        "a", "button", "input", "select", "textarea",
        "details", "summary", "dialog",
    }
    
    # Roles that indicate interactivity
    INTERACTIVE_ROLES = {
        "button", "link", "textbox", "checkbox", "radio",
        "combobox", "listbox", "menu", "menuitem", "menuitemcheckbox",
        "menuitemradio", "option", "searchbox", "slider", "spinbutton",
        "switch", "tab", "treeitem",
    }
    
    # Attributes that indicate interactivity
    INTERACTIVE_ATTRS = {"onclick", "onsubmit", "href", "data-action"}
    
    def __init__(
        self,
        max_elements: int = 200,
        include_text_content: bool = True,
        max_text_length: int = 100,
    ):
        """
        Initialize the simplifier.
        
        Args:
            max_elements: Maximum elements to include
            include_text_content: Whether to include text content
            max_text_length: Maximum text length per element
        """
        self._max_elements = max_elements
        self._include_text = include_text_content
        self._max_text = max_text_length
    
    async def simplify(self, page: "IPage") -> SimplifiedDOM:
        """
        Simplify page DOM.
        
        Args:
            page: Browser page
            
        Returns:
            SimplifiedDOM with interactive elements
        """
        url = page.url
        title = await page.title()
        
        # Get all interactive elements
        elements = await self._extract_interactive_elements(page)
        
        return SimplifiedDOM(
            url=url,
            title=title,
            elements=elements,
        )
    
    async def _extract_interactive_elements(
        self,
        page: "IPage",
    ) -> List[SimplifiedElement]:
        """Extract interactive elements from page."""
        
        # JavaScript to extract elements
        extraction_script = """
        () => {
            const results = [];
            const seen = new Set();
            
            // Interactive tag selectors
            const selectors = [
                'a[href]',
                'button',
                'input',
                'select',
                'textarea',
                '[role="button"]',
                '[role="link"]',
                '[role="textbox"]',
                '[role="checkbox"]',
                '[role="radio"]',
                '[role="combobox"]',
                '[role="listbox"]',
                '[role="menuitem"]',
                '[role="option"]',
                '[role="searchbox"]',
                '[role="tab"]',
                '[onclick]',
                '[data-action]',
            ];
            
            function getSelector(el) {
                if (el.id) return '#' + el.id;
                if (el.getAttribute('data-testid')) {
                    return `[data-testid="${el.getAttribute('data-testid')}"]`;
                }
                if (el.name && el.tagName.toLowerCase() === 'input') {
                    return `input[name="${el.name}"]`;
                }
                // Generate path
                let path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.tagName.toLowerCase();
                    if (el.id) {
                        selector = '#' + el.id;
                        path.unshift(selector);
                        break;
                    }
                    let sibling = el;
                    let nth = 1;
                    while (sibling = sibling.previousElementSibling) {
                        if (sibling.tagName === el.tagName) nth++;
                    }
                    if (nth > 1) selector += ':nth-of-type(' + nth + ')';
                    path.unshift(selector);
                    el = el.parentNode;
                    if (path.length > 3) break;
                }
                return path.join(' > ');
            }
            
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && 
                       rect.height > 0 && 
                       style.visibility !== 'hidden' &&
                       style.display !== 'none' &&
                       style.opacity !== '0';
            }
            
            for (const selector of selectors) {
                try {
                    for (const el of document.querySelectorAll(selector)) {
                        // Skip if already processed
                        const key = getSelector(el);
                        if (seen.has(key)) continue;
                        seen.add(key);
                        
                        // Skip invisible elements
                        if (!isVisible(el)) continue;
                        
                        // Extract element info
                        const info = {
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                            id: el.id || null,
                            name: el.name || null,
                            type: el.type || null,
                            placeholder: el.placeholder || null,
                            aria_label: el.getAttribute('aria-label') || null,
                            role: el.getAttribute('role') || null,
                            href: el.href || null,
                            value: el.value || null,
                            selector: key,
                        };
                        
                        results.push(info);
                        
                        if (results.length >= 200) break;
                    }
                } catch (e) {
                    // Skip selector errors
                }
                if (results.length >= 200) break;
            }
            
            return results;
        }
        """
        
        try:
            raw_elements = await page.evaluate(extraction_script)
            
            elements = []
            for i, raw in enumerate(raw_elements[:self._max_elements]):
                elem = SimplifiedElement(
                    index=i,
                    tag=raw.get("tag", "?"),
                    text=raw.get("text", "")[:self._max_text] if self._include_text else "",
                    id=raw.get("id"),
                    name=raw.get("name"),
                    type=raw.get("type"),
                    placeholder=raw.get("placeholder"),
                    aria_label=raw.get("aria_label"),
                    role=raw.get("role"),
                    href=raw.get("href"),
                    value=raw.get("value"),
                    selector=raw.get("selector", ""),
                )
                elements.append(elem)
            
            return elements
        
        except Exception as e:
            logger.error(f"DOM extraction failed: {e}")
            return []
    
    async def get_form_elements(self, page: "IPage") -> List[SimplifiedElement]:
        """Get only form-related elements."""
        dom = await self.simplify(page)
        
        return [
            e for e in dom.elements
            if e.tag in ("input", "textarea", "select")
            or e.role in ("textbox", "combobox", "listbox", "searchbox")
        ]
    
    async def get_clickable_elements(self, page: "IPage") -> List[SimplifiedElement]:
        """Get only clickable elements."""
        dom = await self.simplify(page)
        
        return [
            e for e in dom.elements
            if e.tag in ("a", "button")
            or e.role in ("button", "link", "menuitem", "tab")
            or e.type in ("submit", "button")
        ]
