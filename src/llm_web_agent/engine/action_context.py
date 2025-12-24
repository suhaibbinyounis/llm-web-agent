"""
Action Context - Track state across actions for smarter resolution.

This module maintains context about recent actions and DOM changes,
enabling the resolver to prioritize newly-appeared elements (e.g., after
clicking a dropdown, prioritize items that just appeared).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING
import time
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


# JavaScript to extract element fingerprints
ELEMENT_SNAPSHOT_JS = '''() => {
    const elements = new Map();
    
    // Capture interactive elements
    const selectors = 'button, a, input, select, textarea, [role="button"], [role="menuitem"], [role="option"], [role="listitem"], li, [onclick]';
    document.querySelectorAll(selectors).forEach((el, index) => {
        // Skip invisible elements
        if (!el.offsetParent && el.tagName.toLowerCase() !== 'body') return;
        
        // Create fingerprint
        const fingerprint = {
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            text: (el.innerText || '').slice(0, 50).trim(),
            role: el.getAttribute('role'),
            ariaLabel: el.getAttribute('aria-label'),
            name: el.getAttribute('name'),
            type: el.getAttribute('type'),
            href: el.href || null,
        };
        
        // Create a unique key
        const key = `${fingerprint.tag}:${fingerprint.id || fingerprint.text || index}`;
        elements.set(key, fingerprint);
    });
    
    return Object.fromEntries(elements);
}'''


@dataclass
class ActionRecord:
    """Record of a single action."""
    action: str  # click, fill, etc.
    target: str
    selector: str
    timestamp: float
    success: bool = True


@dataclass 
class ActionContext:
    """
    Track context across actions for smarter resolution.
    
    Features:
    - Track recent actions
    - Detect newly-appeared elements after actions
    - Provide context for prioritizing dynamic elements
    
    Usage:
        context = ActionContext()
        
        # Before action
        await context.snapshot_before(page)
        
        # After action
        await context.record_action(page, "click", "Login", "#login-btn")
        
        # Check for new elements
        if context.has_new_elements():
            new_elements = context.get_new_elements()
    """
    
    # Recent action history
    history: List[ActionRecord] = field(default_factory=list)
    max_history: int = 10
    
    # Element snapshots for detecting changes
    _elements_before: Dict[str, dict] = field(default_factory=dict)
    _elements_after: Dict[str, dict] = field(default_factory=dict)
    _snapshot_time: float = 0
    
    # Newly detected elements
    _new_elements: Dict[str, dict] = field(default_factory=dict)
    _disappeared_elements: Dict[str, dict] = field(default_factory=dict)
    
    async def snapshot_before(self, page: "IPage") -> None:
        """Take a snapshot of current elements before an action."""
        try:
            self._elements_before = await page.evaluate(ELEMENT_SNAPSHOT_JS)
            self._snapshot_time = time.time()
            logger.debug(f"Snapshot before: {len(self._elements_before)} elements")
        except Exception as e:
            logger.debug(f"Failed to snapshot before: {e}")
            self._elements_before = {}
    
    async def record_action(
        self,
        page: "IPage",
        action: str,
        target: str,
        selector: str,
        success: bool = True,
    ) -> None:
        """
        Record an action and detect DOM changes.
        
        Args:
            page: Browser page
            action: Action type (click, fill, etc.)
            target: Target description
            selector: Selector used
            success: Whether action succeeded
        """
        # Record the action
        record = ActionRecord(
            action=action,
            target=target,
            selector=selector,
            timestamp=time.time(),
            success=success,
        )
        self.history.append(record)
        
        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        # Take after snapshot and detect changes
        try:
            self._elements_after = await page.evaluate(ELEMENT_SNAPSHOT_JS)
            self._detect_changes()
            logger.debug(f"Snapshot after: {len(self._elements_after)} elements, {len(self._new_elements)} new")
        except Exception as e:
            logger.debug(f"Failed to snapshot after: {e}")
            self._elements_after = {}
            self._new_elements = {}
    
    def _detect_changes(self) -> None:
        """Detect which elements appeared/disappeared."""
        before_keys = set(self._elements_before.keys())
        after_keys = set(self._elements_after.keys())
        
        # New elements = in after but not in before
        new_keys = after_keys - before_keys
        self._new_elements = {k: self._elements_after[k] for k in new_keys}
        
        # Disappeared elements
        gone_keys = before_keys - after_keys
        self._disappeared_elements = {k: self._elements_before[k] for k in gone_keys}
    
    def has_new_elements(self) -> bool:
        """Check if new elements appeared after the last action."""
        return len(self._new_elements) > 0
    
    def get_new_elements(self) -> Dict[str, dict]:
        """Get elements that appeared after the last action."""
        return self._new_elements
    
    def get_new_element_texts(self) -> List[str]:
        """Get text content of newly appeared elements."""
        return [
            el.get('text', '') 
            for el in self._new_elements.values() 
            if el.get('text')
        ]
    
    @property
    def last_action(self) -> Optional[ActionRecord]:
        """Get the most recent action."""
        return self.history[-1] if self.history else None
    
    @property
    def time_since_last_action(self) -> float:
        """Seconds since last action."""
        if not self.history:
            return float('inf')
        return time.time() - self.history[-1].timestamp
    
    def should_prioritize_new_elements(self) -> bool:
        """
        Check if we should prioritize newly-appeared elements.
        
        Returns True if:
        - We just performed an action (< 2 seconds ago)
        - New elements appeared
        - Last action was a click (likely opened something)
        """
        if not self.history:
            return False
        
        last = self.history[-1]
        recent = self.time_since_last_action < 2.0
        has_new = self.has_new_elements()
        was_click = last.action in ('click', 'tap', 'press')
        
        return recent and has_new and was_click
    
    def find_in_new_elements(self, target: str) -> Optional[str]:
        """
        Check if target text appears in newly-appeared elements.
        
        Args:
            target: Text to search for
            
        Returns:
            Element key if found, None otherwise
        """
        target_lower = target.lower().strip()
        
        for key, elem in self._new_elements.items():
            elem_text = (elem.get('text') or '').lower()
            elem_label = (elem.get('ariaLabel') or '').lower()
            
            if target_lower in elem_text or target_lower in elem_label:
                return key
        
        return None
    
    def clear(self) -> None:
        """Clear all context."""
        self.history.clear()
        self._elements_before.clear()
        self._elements_after.clear()
        self._new_elements.clear()
        self._disappeared_elements.clear()


# Global singleton
_context: Optional[ActionContext] = None


def get_context() -> ActionContext:
    """Get or create the global action context."""
    global _context
    if _context is None:
        _context = ActionContext()
    return _context
