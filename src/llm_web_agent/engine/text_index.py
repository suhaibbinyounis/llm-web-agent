"""
Text Index - Pre-built inverted index for O(1) element lookups.

Instead of traversing the DOM on every resolution (O(n)),
build an inverted index once and lookup in O(1).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import logging
import time
import re

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


# JavaScript to extract text and selectors from page
TEXT_INDEX_JS = r'''() => {
    const index = {
        wordToElements: {},      // word -> [element info]
        exactText: {},           // exact text -> element info
        elementCount: 0,
    };
    
    // Build unique selector for element
    function buildSelector(el) {
        if (el.id) return '#' + el.id;
        if (el.getAttribute('data-testid')) {
            return `[data-testid="${el.getAttribute('data-testid')}"]`;
        }
        if (el.getAttribute('name')) {
            return `[name="${el.getAttribute('name')}"]`;
        }
        
        // Build path-based selector
        let path = [];
        let current = el;
        while (current && current !== document.body) {
            let selector = current.tagName.toLowerCase();
            if (current.className && typeof current.className === 'string') {
                const mainClass = current.className.split(' ')[0];
                if (mainClass && !mainClass.includes(':')) {
                    selector += '.' + mainClass;
                }
            }
            path.unshift(selector);
            current = current.parentElement;
            if (path.length >= 3) break;
        }
        return path.join(' > ');
    }
    
    // Get bounding rect for spatial queries
    function getRect(el) {
        const rect = el.getBoundingClientRect();
        return {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
        };
    }
    
    // Process interactive elements
    const selectors = 'button, a, input, select, textarea, label, [role="button"], [role="link"], [role="menuitem"], [role="option"], [role="tab"], span, div, li, h1, h2, h3, h4, p';
    
    document.querySelectorAll(selectors).forEach(el => {
        // Skip invisible
        if (!el.offsetParent && el.tagName.toLowerCase() !== 'body') return;
        
        // Get text content
        let text = '';
        if (el.tagName.toLowerCase() === 'input') {
            text = el.placeholder || el.value || el.getAttribute('aria-label') || '';
        } else {
            text = (el.innerText || el.textContent || '').trim();
        }
        
        // Skip empty or very long text
        if (!text || text.length > 200) return;
        
        // Skip if text contains newlines (probably a container, not a specific element)
        if (text.includes('\n') && text.length > 50) return;
        
        const selector = buildSelector(el);
        const elemInfo = {
            selector,
            text: text.slice(0, 100),
            tag: el.tagName.toLowerCase(),
            rect: getRect(el),
            role: el.getAttribute('role'),
            isClickable: el.tagName.match(/^(A|BUTTON)$/i) || el.getAttribute('role') === 'button' || el.onclick !== null,
        };
        
        // Index by exact text
        const textLower = text.toLowerCase();
        if (!index.exactText[textLower]) {
            index.exactText[textLower] = [];
        }
        index.exactText[textLower].push(elemInfo);
        
        // Index by words
        const words = textLower.split(/\s+/).filter(w => w.length >= 2);
        words.forEach(word => {
            if (!index.wordToElements[word]) {
                index.wordToElements[word] = [];
            }
            // Avoid duplicates
            if (!index.wordToElements[word].some(e => e.selector === selector)) {
                index.wordToElements[word].push(elemInfo);
            }
        });
        
        index.elementCount++;
    });
    
    return index;
}'''


@dataclass
class IndexedElement:
    """Element info from the index."""
    selector: str
    text: str
    tag: str
    rect: Dict[str, int]
    role: Optional[str] = None
    is_clickable: bool = False


@dataclass
class TextIndex:
    """
    Pre-built inverted index for fast text lookups.
    
    Usage:
        index = TextIndex()
        await index.build(page)
        
        # O(1) lookup
        results = index.find("Submit")
        results = index.find_phrase("Submit Form")
    """
    
    # Index data
    word_to_elements: Dict[str, List[IndexedElement]] = field(default_factory=dict)
    exact_text: Dict[str, List[IndexedElement]] = field(default_factory=dict)
    
    # Metadata
    built_at_url: str = ""
    built_at_time: float = 0
    element_count: int = 0
    
    # Cache
    _phrase_cache: Dict[str, List[IndexedElement]] = field(default_factory=dict)
    
    async def build(self, page: "IPage") -> int:
        """
        Build index from current page state.
        
        Returns:
            Number of elements indexed
        """
        start = time.time()
        
        try:
            data = await page.evaluate(TEXT_INDEX_JS)
        except Exception as e:
            logger.warning(f"Failed to build text index: {e}")
            return 0
        
        # Clear previous data
        self.word_to_elements.clear()
        self.exact_text.clear()
        self._phrase_cache.clear()
        
        # Parse results
        for word, elements in data.get('wordToElements', {}).items():
            self.word_to_elements[word] = [
                IndexedElement(
                    selector=e['selector'],
                    text=e['text'],
                    tag=e['tag'],
                    rect=e['rect'],
                    role=e.get('role'),
                    is_clickable=e.get('isClickable', False),
                )
                for e in elements
            ]
        
        for text, elements in data.get('exactText', {}).items():
            self.exact_text[text] = [
                IndexedElement(
                    selector=e['selector'],
                    text=e['text'],
                    tag=e['tag'],
                    rect=e['rect'],
                    role=e.get('role'),
                    is_clickable=e.get('isClickable', False),
                )
                for e in elements
            ]
        
        self.built_at_url = page.url
        self.built_at_time = time.time()
        self.element_count = data.get('elementCount', 0)
        
        elapsed = (time.time() - start) * 1000
        logger.debug(f"Built text index: {self.element_count} elements in {elapsed:.0f}ms")
        
        return self.element_count
    
    def is_stale(self, max_age_seconds: float = 5.0) -> bool:
        """Check if index needs rebuilding."""
        if not self.built_at_time:
            return True
        return (time.time() - self.built_at_time) > max_age_seconds
    
    def find_exact(self, text: str) -> List[IndexedElement]:
        """
        O(1) lookup by exact text match.
        
        Args:
            text: Exact text to find
            
        Returns:
            List of matching elements
        """
        return self.exact_text.get(text.lower().strip(), [])
    
    def find_word(self, word: str) -> List[IndexedElement]:
        """
        O(1) lookup by single word.
        
        Args:
            word: Word to find
            
        Returns:
            List of elements containing this word
        """
        return self.word_to_elements.get(word.lower().strip(), [])
    
    def find_phrase(self, phrase: str) -> List[IndexedElement]:
        """
        Find elements containing all words in phrase.
        
        Args:
            phrase: Multi-word phrase
            
        Returns:
            List of elements containing ALL words
        """
        phrase_lower = phrase.lower().strip()
        
        # Check cache
        if phrase_lower in self._phrase_cache:
            return self._phrase_cache[phrase_lower]
        
        # Try exact match first
        exact = self.find_exact(phrase_lower)
        if exact:
            self._phrase_cache[phrase_lower] = exact
            return exact
        
        # Word intersection
        words = [w for w in phrase_lower.split() if len(w) >= 2]
        if not words:
            return []
        
        # Get candidates from first word
        candidates = set(e.selector for e in self.find_word(words[0]))
        
        # Intersect with other words
        for word in words[1:]:
            word_selectors = set(e.selector for e in self.find_word(word))
            candidates &= word_selectors
        
        # Get full element info for matching selectors
        results = []
        for elem in self.find_word(words[0]):
            if elem.selector in candidates:
                results.append(elem)
        
        self._phrase_cache[phrase_lower] = results
        return results
    
    def find_near(
        self,
        target: str,
        reference_selector: str,
        max_distance: int = 500,
    ) -> Optional[IndexedElement]:
        """
        Find element by text near a reference element.
        
        Args:
            target: Text to find
            reference_selector: Selector of reference element
            max_distance: Maximum pixel distance
            
        Returns:
            Closest matching element, or None
        """
        # Find target candidates
        candidates = self.find_phrase(target)
        if not candidates:
            return None
        
        # Find reference element rect
        ref_elem = None
        for elements in self.exact_text.values():
            for elem in elements:
                if elem.selector == reference_selector:
                    ref_elem = elem
                    break
            if ref_elem:
                break
        
        if not ref_elem:
            # Reference not in index, return first candidate
            return candidates[0] if candidates else None
        
        # Score by distance
        ref_rect = ref_elem.rect
        scored = []
        for elem in candidates:
            rect = elem.rect
            distance = ((rect['x'] - ref_rect['x']) ** 2 + 
                       (rect['y'] - ref_rect['y']) ** 2) ** 0.5
            if distance <= max_distance:
                scored.append((elem, distance))
        
        if not scored:
            return None
        
        # Return closest
        scored.sort(key=lambda x: x[1])
        return scored[0][0]
    
    def find_clickable(self, text: str) -> List[IndexedElement]:
        """Find clickable elements matching text."""
        candidates = self.find_phrase(text)
        return [e for e in candidates if e.is_clickable]
    
    def stats(self) -> Dict:
        """Get index statistics."""
        return {
            'element_count': self.element_count,
            'word_count': len(self.word_to_elements),
            'exact_text_count': len(self.exact_text),
            'built_at': self.built_at_url,
            'age_seconds': time.time() - self.built_at_time if self.built_at_time else None,
        }


# Global singleton
_index: Optional[TextIndex] = None


def get_index() -> TextIndex:
    """Get or create the global text index."""
    global _index
    if _index is None:
        _index = TextIndex()
    return _index
