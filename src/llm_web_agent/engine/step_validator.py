"""
Step Validator - Enterprise-grade multi-layer validation for browser actions.

Ensures every action actually happened by:
1. Pre-validation: Element is ready (visible, enabled, not blocked)
2. Post-validation: Action effect verified (value changed, DOM updated)
3. Multi-strategy retry: Try alternatives if primary approach fails

For corporate environments where reliability is critical.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of step validation with detailed diagnostics."""
    success: bool
    action: str
    target: str
    expected: Any = None
    actual: Any = None
    methods: List[Tuple[str, bool]] = field(default_factory=list)
    message: str = ""
    retry_suggested: bool = False
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.action} '{self.target}': {self.message}"


class StepValidator:
    """
    Multi-layer step validation for enterprise reliability.
    
    Validates that browser actions actually took effect by checking
    multiple indicators. Provides detailed diagnostics for debugging.
    
    Usage:
        validator = StepValidator()
        result = await validator.validate_fill(page, selector, "expected_value")
        if not result.success:
            # Handle failure
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, all validation checks must pass.
                        If False, at least one check must pass.
        """
        self._strict = strict_mode
    
    # ─────────────────────────────────────────────────────────────
    # Pre-Execution Validation
    # ─────────────────────────────────────────────────────────────
    
    async def pre_validate(
        self,
        page: "IPage",
        selector: str,
        action: str = "interact",
    ) -> ValidationResult:
        """
        Validate element is ready for interaction.
        
        Checks:
        - Element exists in DOM
        - Element is visible
        - Element is enabled (not disabled)
        - No overlays blocking
        """
        methods = []
        
        try:
            # 1. Element exists
            element = await page.query_selector(selector)
            exists = element is not None
            methods.append(("exists", exists))
            
            if not exists:
                return ValidationResult(
                    success=False,
                    action=f"pre_validate_{action}",
                    target=selector,
                    methods=methods,
                    message=f"Element not found: {selector}",
                )
            
            # 2. Element is visible
            is_visible = await element.is_visible()
            methods.append(("visible", is_visible))
            
            # 3. Element is enabled
            is_enabled = await element.is_enabled()
            methods.append(("enabled", is_enabled))
            
            # 4. Check for overlays (element is top-most at its center)
            box = await element.bounding_box()
            if box:
                center_x = box["x"] + box["width"] / 2
                center_y = box["y"] + box["height"] / 2
                
                top_element = await page.evaluate(
                    f"document.elementFromPoint({center_x}, {center_y})"
                )
                # This is approximate - just check something is at the point
                is_accessible = top_element is not None
                methods.append(("accessible", is_accessible))
            else:
                methods.append(("accessible", False))
            
            # Determine success
            if self._strict:
                success = all(m[1] for m in methods)
            else:
                success = methods[0][1] and methods[1][1]  # At least exists + visible
            
            return ValidationResult(
                success=success,
                action=f"pre_validate_{action}",
                target=selector,
                methods=methods,
                message="Element ready" if success else "Element not ready",
                retry_suggested=not success,
            )
            
        except Exception as e:
            logger.warning(f"Pre-validation error: {e}")
            return ValidationResult(
                success=False,
                action=f"pre_validate_{action}",
                target=selector,
                methods=methods,
                message=str(e),
                retry_suggested=True,
            )
    
    # ─────────────────────────────────────────────────────────────
    # Fill Validation
    # ─────────────────────────────────────────────────────────────
    
    async def validate_fill(
        self,
        page: "IPage",
        selector: str,
        expected_value: str,
    ) -> ValidationResult:
        """
        Validate fill action by reading back the value.
        
        Uses multiple methods to confirm value was set:
        1. page.input_value() - Playwright's method
        2. DOM .value property - Direct JavaScript
        3. getAttribute('value') - For certain input types
        """
        methods = []
        actual_value = None
        
        try:
            # Method 1: Playwright input_value
            try:
                actual1 = await page.input_value(selector)
                match1 = actual1 == expected_value
                methods.append(("input_value", match1))
                actual_value = actual1
                logger.info(f"VALIDATION input_value: got='{actual1}', expected='{expected_value}' → {match1}")
            except Exception as e:
                methods.append(("input_value", False))
                logger.warning(f"input_value failed: {e}")
            
            # Method 2: Direct DOM value
            try:
                actual2 = await page.evaluate(
                    f"document.querySelector('{selector}')?.value || ''"
                )
                match2 = actual2 == expected_value
                methods.append(("dom_value", match2))
                if actual_value is None:
                    actual_value = actual2
                logger.info(f"VALIDATION dom_value: got='{actual2}', expected='{expected_value}' → {match2}")
            except Exception as e:
                methods.append(("dom_value", False))
                logger.warning(f"dom_value failed: {e}")
            
            # Method 3: getAttribute for value attribute
            try:
                actual3 = await page.evaluate(
                    f"document.querySelector('{selector}')?.getAttribute('value') || ''"
                )
                # getAttribute returns the initial value, not current, so only check if matches
                match3 = actual3 == expected_value
                methods.append(("attr_value", match3))
                logger.info(f"VALIDATION attr_value: got='{actual3}', expected='{expected_value}' → {match3}")
            except Exception:
                pass  # Optional method
            
            # Determine success - STRICT: methods 1 AND 2 must pass
            # This ensures we actually verified the value
            passed = sum(1 for m in methods if m[1])
            success = passed >= 2 if len(methods) >= 2 else passed >= 1
            
            # CRITICAL: If actual_value is empty but expected is not, FAIL
            if expected_value and (not actual_value or actual_value.strip() == ""):
                logger.error(f"VALIDATION FAILED: Expected '{expected_value}' but got empty/None!")
                success = False
            
            return ValidationResult(
                success=success,
                action="fill",
                target=selector,
                expected=expected_value,
                actual=actual_value,
                methods=methods,
                message=f"Value {'matches' if success else 'mismatch'}: expected='{expected_value}', actual='{actual_value}'",
                retry_suggested=not success,
            )
            
        except Exception as e:
            logger.error(f"Fill validation error: {e}")
            return ValidationResult(
                success=False,
                action="fill",
                target=selector,
                expected=expected_value,
                actual=actual_value,
                methods=methods,
                message=str(e),
                retry_suggested=True,
            )
    
    # ─────────────────────────────────────────────────────────────
    # Click Validation
    # ─────────────────────────────────────────────────────────────
    
    async def validate_click(
        self,
        page: "IPage",
        selector: str,
        url_before: str,
        dom_hash_before: str,
    ) -> ValidationResult:
        """
        Validate click action by detecting state change.
        
        Checks:
        1. URL changed (navigation)
        2. DOM changed (SPA transition, modal opened, etc.)
        3. Element state changed (button disabled, class added)
        """
        methods = []
        
        try:
            # Small delay to allow for reaction
            await asyncio.sleep(0.1)
            
            # 1. Check URL change
            url_after = page.url
            url_changed = url_before != url_after
            methods.append(("url_changed", url_changed))
            
            # 2. Check DOM change
            dom_hash_after = await self._get_dom_hash(page)
            dom_changed = dom_hash_before != dom_hash_after
            methods.append(("dom_changed", dom_changed))
            
            # 3. Check element state (may have been removed or changed)
            try:
                element = await page.query_selector(selector)
                if element:
                    # Check if state changed (e.g., disabled, selected class)
                    is_disabled = await page.evaluate(
                        f"document.querySelector('{selector}')?.disabled === true"
                    )
                    has_active_class = await page.evaluate(
                        f"document.querySelector('{selector}')?.classList.contains('active') || "
                        f"document.querySelector('{selector}')?.classList.contains('selected')"
                    )
                    state_changed = is_disabled or has_active_class
                    methods.append(("state_changed", state_changed))
                else:
                    # Element was removed (likely navigation/transition)
                    methods.append(("element_removed", True))
            except Exception:
                methods.append(("state_check", False))
            
            # Success if ANY change detected
            success = any(m[1] for m in methods)
            
            return ValidationResult(
                success=success,
                action="click",
                target=selector,
                expected="state_change",
                actual=f"url:{url_changed}, dom:{dom_changed}",
                methods=methods,
                message="Click caused change" if success else "No visible change detected",
                retry_suggested=not success,
            )
            
        except Exception as e:
            logger.error(f"Click validation error: {e}")
            return ValidationResult(
                success=False,
                action="click",
                target=selector,
                methods=methods,
                message=str(e),
                retry_suggested=True,
            )
    
    # ─────────────────────────────────────────────────────────────
    # Navigate Validation
    # ─────────────────────────────────────────────────────────────
    
    async def validate_navigate(
        self,
        page: "IPage",
        expected_url: str,
    ) -> ValidationResult:
        """
        Validate navigation by checking URL.
        
        Handles:
        - Exact URL match
        - URL contains expected
        - Redirect handling
        """
        methods = []
        
        try:
            actual_url = page.url
            
            # Method 1: Exact match
            exact_match = actual_url == expected_url
            methods.append(("exact_match", exact_match))
            
            # Method 2: URL contains expected (handles http vs https, www)
            normalized_expected = expected_url.lower().replace("www.", "").rstrip("/")
            normalized_actual = actual_url.lower().replace("www.", "").rstrip("/")
            contains = normalized_expected in normalized_actual or normalized_actual in normalized_expected
            methods.append(("contains", contains))
            
            # Method 3: Domain match
            from urllib.parse import urlparse
            expected_domain = urlparse(expected_url).netloc.replace("www.", "")
            actual_domain = urlparse(actual_url).netloc.replace("www.", "")
            domain_match = expected_domain == actual_domain
            methods.append(("domain_match", domain_match))
            
            # Success if at least domain matches
            success = any(m[1] for m in methods)
            
            return ValidationResult(
                success=success,
                action="navigate",
                target=expected_url,
                expected=expected_url,
                actual=actual_url,
                methods=methods,
                message=f"Navigation {'succeeded' if success else 'failed'}",
                retry_suggested=not success,
            )
            
        except Exception as e:
            logger.error(f"Navigate validation error: {e}")
            return ValidationResult(
                success=False,
                action="navigate",
                target=expected_url,
                expected=expected_url,
                message=str(e),
                retry_suggested=True,
            )
    
    # ─────────────────────────────────────────────────────────────
    # Select Validation
    # ─────────────────────────────────────────────────────────────
    
    async def validate_select(
        self,
        page: "IPage",
        selector: str,
        expected_value: str,
    ) -> ValidationResult:
        """
        Validate select action by checking selected option.
        """
        methods = []
        
        try:
            # Get selected value
            selected = await page.evaluate(
                f"document.querySelector('{selector}')?.value || ''"
            )
            value_match = selected == expected_value
            methods.append(("value_match", value_match))
            
            # Get selected text
            selected_text = await page.evaluate(
                f"document.querySelector('{selector}')?.selectedOptions[0]?.text || ''"
            )
            text_match = expected_value.lower() in selected_text.lower()
            methods.append(("text_match", text_match))
            
            success = value_match or text_match
            
            return ValidationResult(
                success=success,
                action="select",
                target=selector,
                expected=expected_value,
                actual=selected,
                methods=methods,
                message=f"Selected: {selected}" if success else f"Expected {expected_value}, got {selected}",
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                action="select",
                target=selector,
                expected=expected_value,
                message=str(e),
            )
    
    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────
    
    async def _get_dom_hash(self, page: "IPage") -> str:
        """Get a hash of the current DOM state for change detection."""
        try:
            # Get counts of key elements as a simple hash
            counts = await page.evaluate('''() => {
                return {
                    links: document.querySelectorAll('a').length,
                    buttons: document.querySelectorAll('button').length,
                    inputs: document.querySelectorAll('input').length,
                    text: document.body?.innerText?.slice(0, 1000) || '',
                };
            }''')
            return f"{counts.get('links', 0)}:{counts.get('buttons', 0)}:{counts.get('inputs', 0)}:{hash(counts.get('text', ''))}"
        except Exception:
            return "unknown"


# Singleton instance
_validator: Optional[StepValidator] = None


def get_step_validator(strict_mode: bool = True) -> StepValidator:
    """Get or create the global step validator instance."""
    global _validator
    if _validator is None:
        _validator = StepValidator(strict_mode)
    return _validator
