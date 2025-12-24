"""
State Manager - Track page state and detect transitions.

Handles:
- Waiting for page stability
- Detecting navigation
- Managing DOM cache validity
- Verifying action results
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import asyncio
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.engine.run_context import RunContext

logger = logging.getLogger(__name__)


@dataclass
class PageState:
    """Snapshot of page state."""
    url: str
    title: str
    timestamp: datetime
    element_count: int = 0
    is_loading: bool = False


class StateManager:
    """
    Manage page state and transitions.
    
    Tracks page changes, waits for stability, and validates
    that actions had the expected effect.
    
    Example:
        >>> manager = StateManager()
        >>> await manager.wait_for_stable(page)
        >>> navigated = await manager.detect_navigation(page, previous_url)
    """
    
    # Common loading indicators
    LOADER_SELECTORS = [
        '[class*="loading"]',
        '[class*="spinner"]',
        '[class*="loader"]',
        '[aria-busy="true"]',
        '[aria-hidden="false"][class*="modal"]',
    ]
    
    def __init__(
        self,
        default_timeout_ms: int = 10000,
        stability_delay_ms: int = 100,
    ):
        """
        Initialize the state manager.
        
        Args:
            default_timeout_ms: Default timeout for waits
            stability_delay_ms: Delay after stability checks
        """
        self._default_timeout = default_timeout_ms
        self._stability_delay = stability_delay_ms
    
    async def get_state(self, page: "IPage") -> PageState:
        """Get current page state snapshot."""
        try:
            title = await page.title()
        except Exception:
            title = ""
        
        try:
            element_count = len(await page.query_selector_all("*"))
        except Exception:
            element_count = 0
        
        return PageState(
            url=page.url,
            title=title,
            timestamp=datetime.now(),
            element_count=element_count,
        )
    
    async def wait_for_stable(
        self,
        page: "IPage",
        timeout_ms: Optional[int] = None,
        check_loaders: bool = True,
    ) -> bool:
        """
        Wait for page to reach a stable state.
        
        Args:
            page: Browser page
            timeout_ms: Maximum wait time
            check_loaders: Whether to wait for loading indicators to disappear
            
        Returns:
            True if page is stable, False if timeout
        """
        timeout = timeout_ms or self._default_timeout
        
        try:
            # Wait for network idle
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception as e:
            logger.debug(f"Network idle timeout: {e}")
        
        # Wait for DOM to be ready
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass
        
        # Check for loading indicators
        if check_loaders:
            for selector in self.LOADER_SELECTORS:
                try:
                    loaders = await page.query_selector_all(selector)
                    for loader in loaders:
                        if await loader.is_visible():
                            await loader.wait_for(state="hidden", timeout=min(timeout, 5000))
                except Exception:
                    continue
        
        # Brief delay for any final rendering
        await asyncio.sleep(self._stability_delay / 1000)
        
        return True
    
    async def wait_for_navigation(
        self,
        page: "IPage",
        current_url: str,
        timeout_ms: Optional[int] = None,
    ) -> bool:
        """
        Wait for page to navigate to a different URL.
        
        Args:
            page: Browser page
            current_url: URL before the action
            timeout_ms: Maximum wait time
            
        Returns:
            True if navigated, False if timeout
        """
        timeout = timeout_ms or self._default_timeout
        start = datetime.now()
        
        while (datetime.now() - start).total_seconds() * 1000 < timeout:
            if page.url != current_url:
                await self.wait_for_stable(page, timeout_ms=timeout // 2)
                return True
            await asyncio.sleep(0.1)
        
        return False
    
    async def wait_for_element(
        self,
        page: "IPage",
        selector: str,
        state: str = "visible",
        timeout_ms: Optional[int] = None,
    ) -> bool:
        """
        Wait for an element to reach a specific state.
        
        Args:
            page: Browser page
            selector: Element selector
            state: "visible", "hidden", "attached", "detached"
            timeout_ms: Maximum wait time
            
        Returns:
            True if element reached state, False if timeout
        """
        timeout = timeout_ms or self._default_timeout
        
        try:
            await page.wait_for_selector(selector, state=state, timeout=timeout)
            return True
        except Exception as e:
            logger.debug(f"Wait for element timeout: {selector} → {state}: {e}")
            return False
    
    async def detect_navigation(
        self,
        page: "IPage",
        previous_url: str,
    ) -> bool:
        """Check if page has navigated."""
        return page.url != previous_url
    
    async def detect_dom_change(
        self,
        page: "IPage",
        previous_state: PageState,
        threshold: int = 5,
    ) -> bool:
        """
        Detect if DOM has significantly changed.
        
        Args:
            page: Browser page
            previous_state: State before action
            threshold: Minimum element count change
            
        Returns:
            True if DOM changed significantly
        """
        current_count = len(await page.query_selector_all("*"))
        return abs(current_count - previous_state.element_count) >= threshold
    
    async def verify_action_effect(
        self,
        page: "IPage",
        action_type: str,
        target: str,
        expected_changes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Verify that an action had the expected effect.
        
        Args:
            page: Browser page
            action_type: Type of action performed
            target: Action target
            expected_changes: Expected state changes
            
        Returns:
            True if action likely succeeded
        """
        # Action-specific verification
        if action_type == "fill":
            # Verify input has value
            try:
                element = await page.query_selector(target)
                if element:
                    value = await element.get_attribute("value")
                    return bool(value)
            except Exception:
                pass
        
        elif action_type == "click":
            # For clicks, we mainly rely on no errors being thrown
            # Additional verification would need expected_changes
            return True
        
        elif action_type == "navigate":
            # Verify URL changed
            if expected_changes and "url" in expected_changes:
                return expected_changes["url"] in page.url
            return True
        
        elif action_type == "select":
            # Verify option is selected
            try:
                element = await page.query_selector(target)
                if element:
                    value = await element.evaluate("el => el.value")
                    return bool(value)
            except Exception:
                pass
        
        # Default: assume success if no error
        return True
    
    async def update_context(
        self,
        page: "IPage",
        context: "RunContext",
    ) -> None:
        """Update RunContext with current page state."""
        try:
            title = await page.title()
        except Exception:
            title = ""
        
        context.update_page_state(
            url=page.url,
            title=title,
        )
    
    async def invalidate_on_navigation(
        self,
        page: "IPage",
        context: "RunContext",
        previous_url: str,
    ) -> bool:
        """
        Check for navigation and invalidate cache if needed.
        
        Args:
            page: Browser page
            context: Run context
            previous_url: URL before potential navigation
            
        Returns:
            True if navigation occurred
        """
        if page.url != previous_url:
            context.invalidate_dom_cache()
            await self.update_context(page, context)
            return True
        return False
