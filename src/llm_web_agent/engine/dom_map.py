"""
DOMMap - Real-time element registry for O(1) lookups.

Instead of scanning the DOM on every action, we build a comprehensive
index once and maintain it with incremental updates. This provides:
- O(1) text-based lookups
- O(1) aria-label lookups  
- O(1) data-testid lookups
- Fast spatial queries (grid-based)
- Fingerprint-based stable identification
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from llm_web_agent.engine.fingerprint import (
    FingerprintInput,
    generate_fingerprint,
    generate_selector_priority_list,
    EXTRACT_FINGERPRINT_DATA_JS,
)

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


@dataclass
class BoundingRect:
    """Element bounding rectangle."""
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center_x(self) -> int:
        return self.x + self.width // 2
    
    @property
    def center_y(self) -> int:
        return self.y + self.height // 2
    
    def distance_to(self, other: "BoundingRect") -> float:
        """Calculate Euclidean distance between centers."""
        dx = self.center_x - other.center_x
        dy = self.center_y - other.center_y
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class DOMElement:
    """Comprehensive element representation."""
    fingerprint: str
    selectors: List[str]  # Priority-ordered selectors
    text: str
    tag: str
    rect: BoundingRect
    aria_label: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    placeholder: Optional[str] = None
    data_testid: Optional[str] = None
    href: Optional[str] = None
    id: Optional[str] = None
    is_clickable: bool = False
    framework_hint: Optional[str] = None
    
    @property
    def best_selector(self) -> str:
        """Get the highest-priority selector."""
        return self.selectors[0] if self.selectors else ""
    
    @property
    def is_input(self) -> bool:
        """Check if element accepts text input."""
        return self.tag in ('input', 'textarea') or self.role == 'textbox'
    
    @property
    def is_interactive(self) -> bool:
        """Check if element is interactive."""
        return (
            self.is_clickable or 
            self.is_input or
            self.role in ('button', 'link', 'menuitem', 'option', 'tab', 'checkbox', 'radio')
        )


@dataclass
class DOMMap:
    """
    Real-time DOM registry with multiple indexes.
    
    Usage:
        dom_map = DOMMap()
        await dom_map.build(page)
        
        # O(1) lookups
        elements = dom_map.find_by_text("Sign In")
        elements = dom_map.find_by_aria("Submit form")
        element = dom_map.find_by_testid("login-button")
        
        # Spatial query
        element = dom_map.find_near("Submit", reference_text="Email")
    """
    
    # Primary indexes (all O(1) or O(k) where k = matches)
    by_text: Dict[str, List[DOMElement]] = field(default_factory=dict)
    by_word: Dict[str, List[DOMElement]] = field(default_factory=dict)
    by_aria_label: Dict[str, List[DOMElement]] = field(default_factory=dict)
    by_role: Dict[str, List[DOMElement]] = field(default_factory=dict)
    by_data_testid: Dict[str, DOMElement] = field(default_factory=dict)
    by_name: Dict[str, List[DOMElement]] = field(default_factory=dict)
    by_fingerprint: Dict[str, DOMElement] = field(default_factory=dict)
    by_placeholder: Dict[str, List[DOMElement]] = field(default_factory=dict)
    
    # Spatial grid (for "X near Y" queries)
    # Grid cells are 100x100 pixels
    _spatial_grid: Dict[Tuple[int, int], List[DOMElement]] = field(default_factory=dict)
    _grid_size: int = 100
    
    # All elements
    elements: List[DOMElement] = field(default_factory=list)
    
    # Metadata
    url: str = ""
    built_at: float = 0
    element_count: int = 0
    build_time_ms: float = 0
    
    async def build(self, page: "IPage") -> int:
        """
        Build complete index from current page state.
        
        Args:
            page: Browser page to index
            
        Returns:
            Number of elements indexed
        """
        start_time = time.time()
        
        # Clear previous data
        self._clear()
        
        try:
            # Extract element data from page
            raw_elements = await page.evaluate(EXTRACT_FINGERPRINT_DATA_JS)
        except Exception as e:
            logger.warning(f"Failed to extract DOM data: {e}")
            return 0
        
        for raw in raw_elements:
            element = self._process_raw_element(raw)
            if element:
                self._index_element(element)
        
        self.url = page.url
        self.built_at = time.time()
        self.element_count = len(self.elements)
        self.build_time_ms = (time.time() - start_time) * 1000
        
        logger.debug(
            f"DOMMap built: {self.element_count} elements in {self.build_time_ms:.0f}ms"
        )
        
        return self.element_count
    
    def _clear(self) -> None:
        """Clear all indexes."""
        self.by_text.clear()
        self.by_word.clear()
        self.by_aria_label.clear()
        self.by_role.clear()
        self.by_data_testid.clear()
        self.by_name.clear()
        self.by_fingerprint.clear()
        self.by_placeholder.clear()
        self._spatial_grid.clear()
        self.elements.clear()
    
    def _process_raw_element(self, raw: Dict) -> Optional[DOMElement]:
        """Convert raw JS data to DOMElement."""
        try:
            # Create fingerprint input
            fp_input = FingerprintInput(
                text=raw.get('text', ''),
                tag=raw.get('tag', ''),
                aria_label=raw.get('ariaLabel'),
                role=raw.get('role'),
                class_name=raw.get('className'),
                name=raw.get('name'),
                type=raw.get('type'),
                placeholder=raw.get('placeholder'),
                data_testid=raw.get('dataTestid'),
                href=raw.get('href'),
                nth_child=raw.get('nthChild', 1),
                sibling_count=raw.get('siblingCount', 1),
            )
            
            # Generate fingerprint
            fingerprint = generate_fingerprint(fp_input)
            
            # Generate selector priority list
            selectors = generate_selector_priority_list(fp_input, fingerprint)
            
            # Add ID-based selector if present
            if raw.get('id'):
                selectors.insert(0, f"#{raw['id']}")
            
            # Ensure we have at least one selector
            if not selectors:
                # Fallback: use tag name
                selectors = [raw.get('tag', 'div')]
            
            rect_data = raw.get('rect', {})
            rect = BoundingRect(
                x=rect_data.get('x', 0),
                y=rect_data.get('y', 0),
                width=rect_data.get('width', 0),
                height=rect_data.get('height', 0),
            )
            
            return DOMElement(
                fingerprint=fingerprint,
                selectors=selectors,
                text=raw.get('text', ''),
                tag=raw.get('tag', ''),
                rect=rect,
                aria_label=raw.get('ariaLabel'),
                role=raw.get('role'),
                name=raw.get('name'),
                type=raw.get('type'),
                placeholder=raw.get('placeholder'),
                data_testid=raw.get('dataTestid'),
                href=raw.get('href'),
                id=raw.get('id'),
                is_clickable=raw.get('isClickable', False),
            )
        except Exception as e:
            logger.debug(f"Failed to process element: {e}")
            return None
    
    def _index_element(self, element: DOMElement) -> None:
        """Add element to all relevant indexes."""
        self.elements.append(element)
        
        # Index by fingerprint
        self.by_fingerprint[element.fingerprint] = element
        
        # Index by text (exact match, lowercase)
        if element.text:
            text_lower = element.text.lower().strip()
            if text_lower:
                if text_lower not in self.by_text:
                    self.by_text[text_lower] = []
                self.by_text[text_lower].append(element)
                
                # Index by individual words
                for word in text_lower.split():
                    if len(word) >= 2:  # Skip single chars
                        if word not in self.by_word:
                            self.by_word[word] = []
                        self.by_word[word].append(element)
        
        # Index by aria-label
        if element.aria_label:
            label_lower = element.aria_label.lower().strip()
            if label_lower not in self.by_aria_label:
                self.by_aria_label[label_lower] = []
            self.by_aria_label[label_lower].append(element)
        
        # Index by role
        if element.role:
            if element.role not in self.by_role:
                self.by_role[element.role] = []
            self.by_role[element.role].append(element)
        
        # Index by data-testid (unique)
        if element.data_testid:
            self.by_data_testid[element.data_testid] = element
        
        # Index by name
        if element.name:
            if element.name not in self.by_name:
                self.by_name[element.name] = []
            self.by_name[element.name].append(element)
        
        # Index by placeholder
        if element.placeholder:
            ph_lower = element.placeholder.lower().strip()
            if ph_lower not in self.by_placeholder:
                self.by_placeholder[ph_lower] = []
            self.by_placeholder[ph_lower].append(element)
        
        # Add to spatial grid
        grid_x = element.rect.center_x // self._grid_size
        grid_y = element.rect.center_y // self._grid_size
        grid_key = (grid_x, grid_y)
        if grid_key not in self._spatial_grid:
            self._spatial_grid[grid_key] = []
        self._spatial_grid[grid_key].append(element)
    
    def is_stale(self, max_age_seconds: float = 10.0) -> bool:
        """Check if map needs rebuilding."""
        if not self.built_at:
            return True
        return (time.time() - self.built_at) > max_age_seconds
    
    def is_for_url(self, url: str) -> bool:
        """Check if map was built for this URL."""
        return self.url == url
    
    # =========================================================================
    # LOOKUP METHODS
    # =========================================================================
    
    def find_by_text(self, text: str) -> List[DOMElement]:
        """O(1) exact text match lookup."""
        return self.by_text.get(text.lower().strip(), [])
    
    def find_by_word(self, word: str) -> List[DOMElement]:
        """O(1) single word lookup."""
        return self.by_word.get(word.lower().strip(), [])
    
    def find_by_phrase(self, phrase: str) -> List[DOMElement]:
        """
        Find elements containing all words in phrase.
        
        Returns elements that match exact text first, then partial matches.
        """
        phrase_lower = phrase.lower().strip()
        
        # Try exact match first
        exact = self.find_by_text(phrase_lower)
        if exact:
            return exact
        
        # Try word intersection
        words = [w for w in phrase_lower.split() if len(w) >= 2]
        if not words:
            return []
        
        # Get candidates from first word
        candidates = set(e.fingerprint for e in self.find_by_word(words[0]))
        
        # Intersect with other words
        for word in words[1:]:
            word_fps = set(e.fingerprint for e in self.find_by_word(word))
            candidates &= word_fps
        
        # Return matching elements
        return [self.by_fingerprint[fp] for fp in candidates if fp in self.by_fingerprint]
    
    def find_by_aria(self, label: str) -> List[DOMElement]:
        """O(1) aria-label lookup."""
        return self.by_aria_label.get(label.lower().strip(), [])
    
    def find_by_testid(self, testid: str) -> Optional[DOMElement]:
        """O(1) data-testid lookup (unique)."""
        return self.by_data_testid.get(testid)
    
    def find_by_name(self, name: str) -> List[DOMElement]:
        """O(1) name attribute lookup."""
        return self.by_name.get(name, [])
    
    def find_by_placeholder(self, placeholder: str) -> List[DOMElement]:
        """O(1) placeholder lookup."""
        return self.by_placeholder.get(placeholder.lower().strip(), [])
    
    def find_by_role(self, role: str) -> List[DOMElement]:
        """O(1) role attribute lookup."""
        return self.by_role.get(role, [])
    
    def find_by_fingerprint(self, fingerprint: str) -> Optional[DOMElement]:
        """O(1) fingerprint lookup."""
        return self.by_fingerprint.get(fingerprint)
    
    def find_clickable(self, text: str) -> List[DOMElement]:
        """Find clickable elements matching text."""
        candidates = self.find_by_phrase(text)
        return [e for e in candidates if e.is_clickable]
    
    def find_inputs(self, query: str) -> List[DOMElement]:
        """Find input elements matching query (placeholder, name, or aria-label)."""
        results = []
        query_lower = query.lower().strip()
        
        # Check placeholder
        results.extend(self.find_by_placeholder(query_lower))
        
        # Check name
        results.extend(self.find_by_name(query_lower))
        
        # Check aria-label
        results.extend(self.find_by_aria(query_lower))
        
        # Check text (for labels)
        results.extend(self.find_by_phrase(query_lower))
        
        # Filter to input-like elements and dedupe
        seen = set()
        filtered = []
        for elem in results:
            if elem.is_input and elem.fingerprint not in seen:
                seen.add(elem.fingerprint)
                filtered.append(elem)
        
        return filtered
    
    def find_near(
        self,
        target: str,
        reference: str,
        max_distance: int = 500,
    ) -> Optional[DOMElement]:
        """
        Find element by text that is spatially near another element.
        
        Args:
            target: Text of element to find
            reference: Text of reference element
            max_distance: Maximum pixel distance
            
        Returns:
            Closest matching element, or None
        """
        # Find target candidates
        candidates = self.find_by_phrase(target)
        if not candidates:
            return None
        
        # Find reference element
        refs = self.find_by_phrase(reference)
        if not refs:
            # No reference - return first candidate
            return candidates[0] if candidates else None
        
        ref_elem = refs[0]
        
        # Score by distance
        scored: List[Tuple[DOMElement, float]] = []
        for elem in candidates:
            distance = elem.rect.distance_to(ref_elem.rect)
            if distance <= max_distance:
                scored.append((elem, distance))
        
        if not scored:
            return None
        
        # Return closest
        scored.sort(key=lambda x: x[1])
        return scored[0][0]
    
    def find_in_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> List[DOMElement]:
        """
        Find all elements within a rectangular region.
        
        Uses spatial grid for efficiency.
        """
        results = []
        
        # Determine grid cells to check
        start_gx = x // self._grid_size
        end_gx = (x + width) // self._grid_size
        start_gy = y // self._grid_size
        end_gy = (y + height) // self._grid_size
        
        for gx in range(start_gx, end_gx + 1):
            for gy in range(start_gy, end_gy + 1):
                cell_elems = self._spatial_grid.get((gx, gy), [])
                for elem in cell_elems:
                    # Check if element is actually in region
                    if (x <= elem.rect.center_x <= x + width and
                        y <= elem.rect.center_y <= y + height):
                        results.append(elem)
        
        return results
    
    def find(
        self,
        query: str,
        intent: Optional[str] = None,
    ) -> List[DOMElement]:
        """
        Universal find method - tries multiple strategies.
        
        Args:
            query: Text, aria-label, testid, or other identifier
            intent: Optional hint ('click', 'fill', etc.)
            
        Returns:
            List of matching elements, best match first
        """
        results: List[DOMElement] = []
        seen_fps: Set[str] = set()
        
        def add_unique(elems: List[DOMElement]) -> None:
            for e in elems:
                if e.fingerprint not in seen_fps:
                    seen_fps.add(e.fingerprint)
                    results.append(e)
        
        query_stripped = query.strip()
        
        # 1. Try data-testid (exact, unique)
        if testid_elem := self.find_by_testid(query_stripped):
            add_unique([testid_elem])
        
        # 2. Try exact text match
        add_unique(self.find_by_text(query_stripped))
        
        # 3. Try aria-label
        add_unique(self.find_by_aria(query_stripped))
        
        # 4. For fill intent, prioritize inputs
        if intent in ('fill', 'type'):
            add_unique(self.find_inputs(query_stripped))
        
        # 5. Try phrase match (all words)
        add_unique(self.find_by_phrase(query_stripped))
        
        # 6. Try placeholder
        add_unique(self.find_by_placeholder(query_stripped))
        
        # 7. For click intent, filter to clickable
        if intent in ('click', 'press', 'tap') and results:
            clickable = [e for e in results if e.is_clickable]
            if clickable:
                return clickable
        
        return results
    
    def stats(self) -> Dict:
        """Get map statistics."""
        return {
            'element_count': self.element_count,
            'text_entries': len(self.by_text),
            'word_entries': len(self.by_word),
            'aria_entries': len(self.by_aria_label),
            'testid_entries': len(self.by_data_testid),
            'grid_cells': len(self._spatial_grid),
            'url': self.url,
            'age_seconds': time.time() - self.built_at if self.built_at else None,
            'build_time_ms': self.build_time_ms,
        }


# Global singleton
_dom_map: Optional[DOMMap] = None


def get_dom_map() -> DOMMap:
    """Get or create the global DOM map."""
    global _dom_map
    if _dom_map is None:
        _dom_map = DOMMap()
    return _dom_map
