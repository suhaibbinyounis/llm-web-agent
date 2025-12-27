"""
Context-Aware Error Recovery - Instant logical recovery without LLM overhead.

Provides automatic recovery strategies based on error type and context.
Recovery actions are fast, logical operations that don't require LLM calls.

Features:
- Error classification (element not found, timeout, etc.)
- Context-aware recovery selection
- Graduated retry with escalation
- Per-domain recovery learning
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classified error types for recovery selection."""
    ELEMENT_NOT_FOUND = "element_not_found"
    ELEMENT_NOT_VISIBLE = "element_not_visible"
    ELEMENT_NOT_CLICKABLE = "element_not_clickable"
    ELEMENT_DETACHED = "element_detached"
    TIMEOUT = "timeout"
    NAVIGATION_FAILED = "navigation_failed"
    FILL_FAILED = "fill_failed"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class RecoveryAction:
    """A single recovery action to attempt."""
    name: str
    description: str
    cost_ms: int  # Estimated execution time
    max_attempts: int = 1


@dataclass 
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    action_taken: str
    should_retry: bool
    new_timeout: Optional[int] = None
    message: str = ""


class ErrorRecovery:
    """
    Context-aware error recovery with instant logical actions.
    
    Provides fast recovery strategies that don't require LLM calls:
    - Wait + retry for transient issues
    - Scroll into view for visibility issues
    - Clear + retype for input issues
    - Extended timeout for slow pages
    
    Usage:
        recovery = ErrorRecovery()
        result = await recovery.recover(error, page, context)
        if result.should_retry:
            # Retry the action
    """
    
    # Error patterns → ErrorType mapping
    ERROR_PATTERNS = {
        ErrorType.ELEMENT_NOT_FOUND: [
            "could not find",
            "no element matching",
            "element not found",
            "locator resolved to",
            "waiting for selector",
        ],
        ErrorType.ELEMENT_NOT_VISIBLE: [
            "not visible",
            "hidden",
            "display: none",
            "visibility: hidden",
            "zero-size",
        ],
        ErrorType.ELEMENT_NOT_CLICKABLE: [
            "not clickable",
            "intercepted",
            "covered by",
            "pointer-events: none",
        ],
        ErrorType.ELEMENT_DETACHED: [
            "detached",
            "removed from document",
            "stale element",
        ],
        ErrorType.TIMEOUT: [
            "timeout",
            "timed out",
            "deadline exceeded",
        ],
        ErrorType.NAVIGATION_FAILED: [
            "navigation failed",
            "net::",
            "ERR_",
            "connection refused",
        ],
        ErrorType.FILL_FAILED: [
            "fill failed",
            "cannot type",
            "readonly",
            "disabled",
        ],
        ErrorType.NETWORK_ERROR: [
            "network error",
            "fetch failed",
            "connection reset",
        ],
    }
    
    def __init__(self, max_recovery_attempts: int = 3):
        self._max_attempts = max_recovery_attempts
        self._attempt_counts: Dict[str, int] = {}  # Track attempts per step
    
    def classify_error(self, error: Exception) -> ErrorType:
        """Classify an exception into an ErrorType."""
        error_str = str(error).lower()
        
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_str:
                    return error_type
        
        return ErrorType.UNKNOWN
    
    async def recover(
        self,
        error: Exception,
        page: "IPage",
        context: Dict[str, Any],
    ) -> RecoveryResult:
        """
        Attempt to recover from an error.
        
        Args:
            error: The exception that occurred
            page: Browser page
            context: Execution context with:
                - step_id: Identifier for tracking attempts
                - target: Element target (optional)
                - selector: CSS selector (optional)
                - timeout: Current timeout in ms (optional)
                
        Returns:
            RecoveryResult indicating what was done and if retry is worthwhile
        """
        error_type = self.classify_error(error)
        step_id = context.get("step_id", "unknown")
        
        # Track attempts for this step
        attempt_key = f"{step_id}:{error_type.value}"
        self._attempt_counts[attempt_key] = self._attempt_counts.get(attempt_key, 0) + 1
        attempt = self._attempt_counts[attempt_key]
        
        if attempt > self._max_attempts:
            return RecoveryResult(
                success=False,
                action_taken="max_attempts_exceeded",
                should_retry=False,
                message=f"Max recovery attempts ({self._max_attempts}) exceeded for {error_type.value}",
            )
        
        logger.info(f"Recovery attempt {attempt}/{self._max_attempts} for {error_type.value}")
        
        # Dispatch to appropriate recovery strategy
        try:
            if error_type == ErrorType.ELEMENT_NOT_FOUND:
                return await self._recover_element_not_found(page, context, attempt)
            
            elif error_type == ErrorType.ELEMENT_NOT_VISIBLE:
                return await self._recover_element_not_visible(page, context, attempt)
            
            elif error_type == ErrorType.ELEMENT_NOT_CLICKABLE:
                return await self._recover_element_not_clickable(page, context, attempt)
            
            elif error_type == ErrorType.ELEMENT_DETACHED:
                return await self._recover_element_detached(page, context, attempt)
            
            elif error_type == ErrorType.TIMEOUT:
                return await self._recover_timeout(page, context, attempt)
            
            elif error_type == ErrorType.NAVIGATION_FAILED:
                return await self._recover_navigation_failed(page, context, attempt)
            
            elif error_type == ErrorType.FILL_FAILED:
                return await self._recover_fill_failed(page, context, attempt)
            
            else:
                # Generic recovery: wait and retry
                return await self._recover_generic(page, context, attempt)
                
        except Exception as recovery_error:
            logger.warning(f"Recovery action failed: {recovery_error}")
            return RecoveryResult(
                success=False,
                action_taken="recovery_failed",
                should_retry=False,
                message=str(recovery_error),
            )
    
    async def _recover_element_not_found(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from element not found."""
        if attempt == 1:
            # First attempt: short wait (element might be loading)
            await asyncio.sleep(0.5)
            return RecoveryResult(
                success=True,
                action_taken="wait_short",
                should_retry=True,
                message="Waited 500ms for element to appear",
            )
        
        elif attempt == 2:
            # Second attempt: scroll to expose element
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(0.3)
            return RecoveryResult(
                success=True,
                action_taken="scroll_down",
                should_retry=True,
                message="Scrolled down to expose element",
            )
        
        else:
            # Third attempt: dismiss any modals/overlays
            dismissed = await self._dismiss_overlays(page)
            if dismissed:
                return RecoveryResult(
                    success=True,
                    action_taken="dismiss_overlays",
                    should_retry=True,
                    message="Dismissed overlay/modal",
                )
            return RecoveryResult(
                success=False,
                action_taken="none",
                should_retry=False,
                message="No more recovery options",
            )
    
    async def _recover_element_not_visible(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from element not visible."""
        selector = context.get("selector")
        
        if attempt == 1 and selector:
            # Scroll element into view
            try:
                await page.evaluate(
                    f"document.querySelector('{selector}')?.scrollIntoView({{behavior: 'instant', block: 'center'}})"
                )
                await asyncio.sleep(0.2)
                return RecoveryResult(
                    success=True,
                    action_taken="scroll_into_view",
                    should_retry=True,
                    message="Scrolled element into view",
                )
            except:
                pass
        
        elif attempt == 2:
            # Dismiss overlays
            dismissed = await self._dismiss_overlays(page)
            return RecoveryResult(
                success=dismissed,
                action_taken="dismiss_overlays" if dismissed else "none",
                should_retry=dismissed,
                message="Dismissed overlay" if dismissed else "No overlay found",
            )
        
        return RecoveryResult(
            success=False,
            action_taken="none",
            should_retry=False,
        )
    
    async def _recover_element_not_clickable(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from element not clickable."""
        if attempt == 1:
            # Wait for any animation/transition
            await asyncio.sleep(0.3)
            return RecoveryResult(
                success=True,
                action_taken="wait_animation",
                should_retry=True,
                message="Waited for animation",
            )
        
        elif attempt == 2:
            # Try to dismiss overlays
            dismissed = await self._dismiss_overlays(page)
            if dismissed:
                return RecoveryResult(
                    success=True,
                    action_taken="dismiss_overlays",
                    should_retry=True,
                )
        
        # Suggest force click in context
        context["force_click"] = True
        return RecoveryResult(
            success=True,
            action_taken="enable_force_click",
            should_retry=True,
            message="Enabled force click option",
        )
    
    async def _recover_element_detached(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from stale/detached element."""
        # Signal that selector should be re-resolved
        context["re_resolve"] = True
        await asyncio.sleep(0.2)  # Wait for DOM to stabilize
        
        return RecoveryResult(
            success=True,
            action_taken="re_resolve_selector",
            should_retry=True,
            message="Flagged for selector re-resolution",
        )
    
    async def _recover_timeout(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from timeout - extend timeout and retry."""
        current_timeout = context.get("timeout", 5000)
        
        if attempt == 1:
            # Double the timeout
            new_timeout = min(current_timeout * 2, 30000)
            return RecoveryResult(
                success=True,
                action_taken="extend_timeout",
                should_retry=True,
                new_timeout=new_timeout,
                message=f"Extended timeout to {new_timeout}ms",
            )
        
        elif attempt == 2:
            # Wait for network idle
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                return RecoveryResult(
                    success=True,
                    action_taken="wait_network_idle",
                    should_retry=True,
                    message="Waited for network idle",
                )
            except:
                pass
        
        return RecoveryResult(
            success=False,
            action_taken="none",
            should_retry=False,
            message="Timeout recovery exhausted",
        )
    
    async def _recover_navigation_failed(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from navigation failure."""
        if attempt == 1:
            # Simple retry with delay
            await asyncio.sleep(1.0)
            return RecoveryResult(
                success=True,
                action_taken="wait_and_retry",
                should_retry=True,
                message="Waiting 1s before retry",
            )
        
        elif attempt == 2:
            # Try going back and retrying
            try:
                await page.go_back()
                await asyncio.sleep(0.5)
                return RecoveryResult(
                    success=True,
                    action_taken="go_back",
                    should_retry=True,
                    message="Navigated back, will retry",
                )
            except:
                pass
        
        return RecoveryResult(
            success=False,
            action_taken="none",
            should_retry=False,
        )
    
    async def _recover_fill_failed(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Recover from fill/type failure."""
        selector = context.get("selector")
        
        if attempt == 1 and selector:
            # Clear field first
            try:
                await page.fill(selector, "")
                await asyncio.sleep(0.1)
                return RecoveryResult(
                    success=True,
                    action_taken="clear_field",
                    should_retry=True,
                    message="Cleared field before retry",
                )
            except:
                pass
        
        elif attempt == 2:
            # Try clicking to focus first
            try:
                if selector:
                    await page.click(selector)
                    await asyncio.sleep(0.1)
                return RecoveryResult(
                    success=True,
                    action_taken="click_to_focus",
                    should_retry=True,
                    message="Clicked to focus before retry",
                )
            except:
                pass
        
        # Suggest character-by-character typing
        context["type_slowly"] = True
        return RecoveryResult(
            success=True,
            action_taken="enable_slow_type",
            should_retry=True,
            message="Enabled character-by-character typing",
        )
    
    async def _recover_generic(
        self, page: "IPage", context: Dict[str, Any], attempt: int
    ) -> RecoveryResult:
        """Generic recovery: wait and retry."""
        wait_time = 0.5 * attempt  # Escalating wait
        await asyncio.sleep(wait_time)
        
        return RecoveryResult(
            success=True,
            action_taken=f"wait_{wait_time}s",
            should_retry=attempt < self._max_attempts,
            message=f"Generic recovery: waited {wait_time}s",
        )
    
    async def _dismiss_overlays(self, page: "IPage") -> bool:
        """Try to dismiss common overlay patterns."""
        overlay_selectors = [
            # Cookie consent
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("Got it")',
            '[aria-label="Close"]',
            '[aria-label="Dismiss"]',
            # Modals
            '.modal-close',
            '.close-button',
            '[data-dismiss="modal"]',
            'button.close',
            # Popups
            '.popup-close',
            '.overlay-close',
        ]
        
        for selector in overlay_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(0.3)
                    logger.info(f"Dismissed overlay: {selector}")
                    return True
            except:
                continue
        
        # Try Escape key as last resort
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            return True
        except:
            return False
    
    def reset_attempts(self, step_id: str = None) -> None:
        """Reset attempt counters."""
        if step_id:
            # Reset for specific step
            keys_to_remove = [k for k in self._attempt_counts if k.startswith(f"{step_id}:")]
            for k in keys_to_remove:
                del self._attempt_counts[k]
        else:
            # Reset all
            self._attempt_counts.clear()


# Global singleton
_error_recovery: Optional[ErrorRecovery] = None


def get_error_recovery(max_attempts: int = 3) -> ErrorRecovery:
    """Get or create the global error recovery instance."""
    global _error_recovery
    if _error_recovery is None:
        _error_recovery = ErrorRecovery(max_attempts)
    return _error_recovery
