"""
Run Context - Persistent memory during agent execution.

Handles:
- Clipboard for copy/paste operations
- Variables from user instructions
- Extracted data during run
- Action history for replanning
- DOM caching for performance
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutedAction:
    """Record of an executed action."""
    step_id: str
    action_type: str
    target: Optional[str]
    value: Optional[str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0
    error: Optional[str] = None
    screenshot: Optional[str] = None


@dataclass
class RunContext:
    """
    Persistent memory during an agent run.
    
    Stores clipboard data, variables, extracted values, and maintains
    action history for replanning and verification.
    
    Example:
        >>> ctx = RunContext()
        >>> ctx.store("order_number", "12345")
        >>> ctx.store("price", "$299.99")
        >>> value = ctx.retrieve("order_number")  # "12345"
        >>> resolved = ctx.resolve("Order: {{order_number}}")  # "Order: 12345"
    """
    
    # Clipboard for explicit copy/paste operations
    clipboard: Dict[str, Any] = field(default_factory=dict)
    
    # User-defined variables from instructions
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Auto-extracted data during run (URLs, titles, etc.)
    extracted: Dict[str, Any] = field(default_factory=dict)
    
    # Full action history
    history: List[ExecutedAction] = field(default_factory=list)
    
    # Current page state
    current_url: str = ""
    page_title: str = ""
    
    # DOM cache for performance
    _dom_cache: Optional[Any] = field(default=None, repr=False)
    _dom_cache_time: float = 0
    _dom_cache_url: str = ""
    
    # Run metadata
    run_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    
    # Reference pattern: {{variable_name}} or {{clipboard.key}}
    _REFERENCE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
    
    def store(self, key: str, value: Any, source: str = "clipboard") -> None:
        """
        Store a value in memory.
        
        Args:
            key: Key to store under
            value: Value to store
            source: "clipboard", "variable", or "extracted"
        """
        key = self._normalize_key(key)
        
        if source == "clipboard":
            self.clipboard[key] = value
        elif source == "variable":
            self.variables[key] = value
        elif source == "extracted":
            self.extracted[key] = value
        else:
            self.clipboard[key] = value
        
        logger.debug(f"Stored [{source}] {key} = {repr(value)[:50]}")
    
    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from memory.
        
        Checks in order: clipboard → variables → extracted
        
        Args:
            key: Key to retrieve
            
        Returns:
            Stored value or None
        """
        key = self._normalize_key(key)
        
        # Check clipboard first (explicit user storage)
        if key in self.clipboard:
            return self.clipboard[key]
        
        # Then variables
        if key in self.variables:
            return self.variables[key]
        
        # Finally extracted data
        if key in self.extracted:
            return self.extracted[key]
        
        # Handle nested keys like "clipboard.order_number"
        if "." in key:
            parts = key.split(".", 1)
            source, nested_key = parts[0], parts[1]
            
            if source == "clipboard" and nested_key in self.clipboard:
                return self.clipboard[nested_key]
            elif source == "variables" and nested_key in self.variables:
                return self.variables[nested_key]
            elif source == "extracted" and nested_key in self.extracted:
                return self.extracted[nested_key]
        
        return None
    
    def resolve(self, template: str) -> str:
        """
        Resolve variable references in a template string.
        
        Replaces {{key}} patterns with stored values.
        
        Args:
            template: String with {{variable}} placeholders
            
        Returns:
            Resolved string with values substituted
            
        Example:
            >>> ctx.store("name", "John")
            >>> ctx.resolve("Hello {{name}}!")
            "Hello John!"
        """
        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            value = self.retrieve(key)
            
            if value is not None:
                return str(value)
            else:
                logger.warning(f"Unresolved reference: {{{{{key}}}}}")
                return match.group(0)  # Keep original if not found
        
        return self._REFERENCE_PATTERN.sub(replacer, template)
    
    def has_references(self, text: str) -> bool:
        """Check if text contains variable references."""
        return bool(self._REFERENCE_PATTERN.search(text))
    
    def get_references(self, text: str) -> List[str]:
        """Extract all variable references from text."""
        return self._REFERENCE_PATTERN.findall(text)
    
    def record_action(
        self,
        step_id: str,
        action_type: str,
        target: Optional[str] = None,
        value: Optional[str] = None,
        success: bool = True,
        duration_ms: float = 0,
        error: Optional[str] = None,
    ) -> None:
        """Record an executed action in history."""
        action = ExecutedAction(
            step_id=step_id,
            action_type=action_type,
            target=target,
            value=value,
            success=success,
            duration_ms=duration_ms,
            error=error,
        )
        self.history.append(action)
    
    def get_last_action(self) -> Optional[ExecutedAction]:
        """Get the most recent action."""
        return self.history[-1] if self.history else None
    
    def get_failed_actions(self) -> List[ExecutedAction]:
        """Get all failed actions."""
        return [a for a in self.history if not a.success]
    
    def update_page_state(self, url: str, title: str = "") -> None:
        """Update current page state."""
        if url != self.current_url:
            # Page changed, invalidate DOM cache
            self.invalidate_dom_cache()
        
        self.current_url = url
        self.page_title = title
        
        # Auto-extract common data
        self.extracted["current_url"] = url
        self.extracted["page_title"] = title
    
    def set_dom_cache(self, dom: Any, url: str) -> None:
        """Cache parsed DOM for performance."""
        self._dom_cache = dom
        self._dom_cache_time = datetime.now().timestamp()
        self._dom_cache_url = url
    
    def get_dom_cache(self, max_age_seconds: float = 5.0) -> Optional[Any]:
        """
        Get cached DOM if still valid.
        
        Args:
            max_age_seconds: Maximum cache age
            
        Returns:
            Cached DOM or None if expired/invalid
        """
        if self._dom_cache is None:
            return None
        
        if self._dom_cache_url != self.current_url:
            return None
        
        age = datetime.now().timestamp() - self._dom_cache_time
        if age > max_age_seconds:
            return None
        
        return self._dom_cache
    
    def invalidate_dom_cache(self) -> None:
        """Clear DOM cache."""
        self._dom_cache = None
        self._dom_cache_time = 0
        self._dom_cache_url = ""
    
    def get_all_stored(self) -> Dict[str, Any]:
        """Get all stored data as a single dict."""
        return {
            **self.extracted,
            **self.variables,
            **self.clipboard,
        }
    
    def clear(self) -> None:
        """Clear all stored data and history."""
        self.clipboard.clear()
        self.variables.clear()
        self.extracted.clear()
        self.history.clear()
        self.invalidate_dom_cache()
    
    def to_summary(self) -> Dict[str, Any]:
        """Get a summary for debugging/logging."""
        return {
            "run_id": self.run_id,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "clipboard_keys": list(self.clipboard.keys()),
            "variable_keys": list(self.variables.keys()),
            "extracted_keys": list(self.extracted.keys()),
            "action_count": len(self.history),
            "failed_actions": len(self.get_failed_actions()),
        }
    
    @staticmethod
    def _normalize_key(key: str) -> str:
        """Normalize a storage key."""
        # Convert spaces/dashes to underscores, lowercase
        return key.strip().lower().replace(" ", "_").replace("-", "_")
