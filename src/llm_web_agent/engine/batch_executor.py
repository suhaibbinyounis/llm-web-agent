"""
Batch Executor - Execute multiple actions efficiently.

Handles:
- Batching actions on same DOM
- Parallel target resolution
- Sequential action execution
- Result aggregation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import asyncio
import time
import logging

from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.task_graph import TaskGraph, TaskStep, StepIntent, StepStatus
from llm_web_agent.engine.target_resolver import TargetResolver, ResolvedTarget
from llm_web_agent.engine.state_manager import StateManager

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Status of a batch execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"   # Some steps succeeded
    FAILED = "failed"


@dataclass
class StepResult:
    """Result of executing a single step."""
    step: TaskStep
    success: bool
    duration_ms: float = 0
    error: Optional[str] = None
    data: Optional[Any] = None


@dataclass
class BatchResult:
    """Result of executing a batch of steps."""
    steps: List[TaskStep]
    results: List[StepResult]
    status: BatchStatus = BatchStatus.SUCCESS
    total_duration_ms: float = 0
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)
    
    @property
    def all_success(self) -> bool:
        return all(r.success for r in self.results)


class BatchExecutor:
    """
    Execute batches of actions efficiently.
    
    Optimizes execution by:
    1. Parsing DOM once for the batch
    2. Resolving all targets upfront
    3. Executing actions sequentially
    4. Batching form fills via JavaScript
    
    Example:
        >>> executor = BatchExecutor(resolver, state_manager)
        >>> result = await executor.execute_batch(page, steps, context)
    """
    
    def __init__(
        self,
        resolver: Optional[TargetResolver] = None,
        state_manager: Optional[StateManager] = None,
        llm_provider: Optional["ILLMProvider"] = None,
        navigation_timeout_ms: int = 60000,
        step_timeout_ms: int = 30000,
        max_attempts: int = 4,
        step_delay_ms: int = 0,
    ):
        """
        Initialize the executor.
        
        Args:
            resolver: Target resolver instance
            state_manager: State manager instance
            llm_provider: Optional LLM for complex cases
            navigation_timeout_ms: Timeout for page navigation (page.goto)
            step_timeout_ms: Timeout for individual steps
            max_attempts: Maximum retry attempts per step
            step_delay_ms: Delay between steps in milliseconds
        """
        self._resolver = resolver or TargetResolver()
        self._state = state_manager or StateManager()
        self._llm = llm_provider
        self._navigation_timeout_ms = navigation_timeout_ms
        self._step_timeout_ms = step_timeout_ms
        self._max_attempts = max_attempts
        self._step_delay_ms = step_delay_ms
    
    async def execute_batch(
        self,
        page: "IPage",
        steps: List[TaskStep],
        context: RunContext,
    ) -> BatchResult:
        """
        Execute a batch of steps on the current page.
        
        Args:
            page: Browser page
            steps: Steps to execute
            context: Run context for memory/state
            
        Returns:
            BatchResult with all step results
        """
        if not steps:
            return BatchResult(steps=[], results=[], status=BatchStatus.SUCCESS)
        
        batch_start = time.time()
        results: List[StepResult] = []
        
        # Update context with current page state
        await self._state.update_context(page, context)
        
        # Check for form fill optimization
        fill_steps = [s for s in steps if s.intent == StepIntent.FILL]
        other_steps = [s for s in steps if s.intent != StepIntent.FILL]
        
        # If we have multiple fills, batch them
        if len(fill_steps) > 1:
            fill_result = await self._execute_batch_fill(page, fill_steps, context)
            results.extend(fill_result)
        elif fill_steps:
            # Single fill, execute normally
            other_steps = steps
        
        # Execute other steps sequentially
        for step in (other_steps if len(fill_steps) > 1 else steps):
            if step.intent == StepIntent.FILL and len(fill_steps) > 1:
                continue  # Already handled in batch fill
            
            result = await self._execute_step(page, step, context)
            results.append(result)
            
            # Apply step delay if configured
            if self._step_delay_ms > 0:
                await asyncio.sleep(self._step_delay_ms / 1000)
            
            # Record in context
            context.record_action(
                step_id=step.id,
                action_type=step.intent.value,
                target=step.target,
                value=step.value,
                success=result.success,
                duration_ms=result.duration_ms,
                error=result.error,
            )
            
            # If step causes navigation, wait and update context
            if step.wait_for_navigation and result.success:
                previous_url = context.current_url
                await self._state.wait_for_navigation(page, previous_url)
                await self._state.wait_for_stable(page)
                await self._state.update_context(page, context)
        
        # Determine batch status
        batch_duration = (time.time() - batch_start) * 1000
        
        if all(r.success for r in results):
            status = BatchStatus.SUCCESS
        elif any(r.success for r in results):
            status = BatchStatus.PARTIAL
        else:
            status = BatchStatus.FAILED
        
        return BatchResult(
            steps=steps,
            results=results,
            status=status,
            total_duration_ms=batch_duration,
        )
    
    async def _execute_step(
        self,
        page: "IPage",
        step: TaskStep,
        context: RunContext,
    ) -> StepResult:
        """Execute a single step with automatic error recovery."""
        from llm_web_agent.engine.error_recovery import get_error_recovery
        
        recovery = get_error_recovery()
        max_attempts = self._max_attempts  # Configurable retry attempts
        timeout_ms = self._step_timeout_ms  # Configurable step timeout
        
        for attempt in range(max_attempts):
            start = time.time()
            step.status = StepStatus.RUNNING
            
            try:
                # Resolve value references
                value = step.value
                if value and context.has_references(value):
                    value = context.resolve(value)
                
                # Execute based on intent
                if step.intent == StepIntent.NAVIGATE:
                    await self._execute_navigate(page, step.target, context)
                
                elif step.intent == StepIntent.CLICK:
                    await self._execute_click(page, step.target, context)
                
                elif step.intent == StepIntent.FILL:
                    await self._execute_fill(page, step.target, value, context)
                
                elif step.intent == StepIntent.TYPE:
                    await self._execute_type(page, step.target, value, context)
                
                elif step.intent == StepIntent.SELECT:
                    await self._execute_select(page, step.target, value, context)
                
                elif step.intent == StepIntent.EXTRACT:
                    extracted = await self._execute_extract(page, step.target, context)
                    if step.store_as:
                        context.store(step.store_as, extracted)
                    step.result = extracted
                
                elif step.intent == StepIntent.HOVER:
                    await self._execute_hover(page, step.target, context)
                
                elif step.intent == StepIntent.SCROLL:
                    await self._execute_scroll(page, step.target, context)
                
                elif step.intent == StepIntent.WAIT:
                    await self._execute_wait(page, step.target, step.value, context)
                
                elif step.intent == StepIntent.PRESS_KEY:
                    await self._execute_press_key(page, step.value, context)
                
                elif step.intent == StepIntent.SUBMIT:
                    await self._execute_submit(page, step.target, context)
                
                elif step.intent == StepIntent.SCREENSHOT:
                    await self._execute_screenshot(page, step.target, context)
                
                else:
                    raise ValueError(f"Unknown intent: {step.intent}")
                
                duration = (time.time() - start) * 1000
                step.mark_success(duration_ms=duration)
                
                # Reset recovery attempts on success
                recovery.reset_attempts(step.id)
                
                return StepResult(step=step, success=True, duration_ms=duration)
            
            except Exception as e:
                duration = (time.time() - start) * 1000
                error_str = str(e)
                
                # Attempt recovery
                recovery_context = {
                    "step_id": step.id,
                    "target": step.target,
                    "timeout": timeout_ms,
                }
                
                recovery_result = await recovery.recover(e, page, recovery_context)
                
                if recovery_result.should_retry:
                    logger.info(f"Recovery: {recovery_result.action_taken} → retrying step")
                    
                    # Update timeout if recovery suggests it
                    if recovery_result.new_timeout:
                        timeout_ms = recovery_result.new_timeout
                    
                    continue  # Retry the step
                
                # No more recovery options, fail the step
                step.mark_failed(error_str, duration_ms=duration)
                logger.error(f"Step failed (after recovery): {step.intent.value} → {error_str}")
                
                return StepResult(step=step, success=False, duration_ms=duration, error=error_str)
        
        # Should never reach here, but safety fallback
        return StepResult(step=step, success=False, error="Max attempts exceeded")
    
    async def _execute_batch_fill(
        self,
        page: "IPage",
        steps: List[TaskStep],
        context: RunContext,
    ) -> List[StepResult]:
        """
        Execute multiple fill operations using FormFiller.
        
        Uses smart field matching to ensure each field is filled correctly.
        """
        results = []
        
        # NEW: Try FormFiller for smart multi-field filling
        try:
            from llm_web_agent.engine.form_handler import FormFiller, FormValidator
            
            filler = FormFiller(page)
            
            # Build field_values dict from steps
            field_values = {}
            for step in steps:
                value = step.value or ""
                if context.has_references(value):
                    value = context.resolve(value)
                field_values[step.target] = value
            
            # Fill all fields using smart matching
            fill_results = await filler.fill_fields(field_values)
            
            # Map results back to steps
            result_map = {target: (success, error) for target, success, error in fill_results}
            
            for step in steps:
                success, error = result_map.get(step.target, (False, "Field not matched"))
                
                if success:
                    step.mark_success()
                    results.append(StepResult(step=step, success=True))
                else:
                    step.mark_failed(error or "Unknown error")
                    results.append(StepResult(step=step, success=False, error=error))
            
            # Check for form validation errors
            validator = FormValidator(page)
            has_errors, errors = await validator.check_errors()
            if has_errors:
                logger.warning(f"Form validation errors: {errors}")
            
            return results
            
        except Exception as e:
            logger.warning(f"FormFiller failed, falling back to smart field matching: {e}")
        
        # FALLBACK: Use FormFieldAnalyzer for unique field matching
        # This ensures we find the RIGHT field, not just ANY matching input
        try:
            from llm_web_agent.engine.form_handler import FormFieldAnalyzer
            
            analyzer = FormFieldAnalyzer()
            form_context = await analyzer.analyze(page)
            
            if not form_context.fields:
                logger.warning("No form fields found on page for fallback")
                for step in steps:
                    if not any(r.step.id == step.id for r in results):
                        step.mark_failed("No form fields found on page")
                        results.append(StepResult(step=step, success=False, error="No form fields found"))
                return results
            
            logger.info(f"Analyzed form: {len(form_context.fields)} fields found")
            
            for step in steps:
                # Skip if already processed
                if any(r.step.id == step.id for r in results):
                    continue
                
                target = step.target
                value = step.value or ""
                if context.has_references(value):
                    value = context.resolve(value)
                
                # Find best matching field using FormField.matches()
                best_field = None
                best_score = 0.6  # Minimum threshold for a match
                
                for field in form_context.get_input_fields():
                    if not field.is_visible or field.is_disabled:
                        continue
                    score = field.matches(target)
                    if score > best_score:
                        best_score = score
                        best_field = field
                
                if best_field:
                    # Build unique selector from field attributes (ID > name > selector)
                    if best_field.id:
                        selector = f"#{best_field.id}"
                    elif best_field.name:
                        selector = f"[name='{best_field.name}']"
                    else:
                        selector = best_field.selector
                    
                    try:
                        await page.fill(selector, value)
                        step.mark_success()
                        results.append(StepResult(step=step, success=True))
                        logger.info(f"Filled '{best_field.get_best_identifier()}' via fallback (score: {best_score:.2f})")
                    except Exception as fill_error:
                        step.mark_failed(str(fill_error))
                        results.append(StepResult(step=step, success=False, error=str(fill_error)))
                else:
                    # No unique match found - fail explicitly instead of guessing
                    error = f"No unique field match for '{target}' (best score < 0.6)"
                    step.mark_failed(error)
                    results.append(StepResult(step=step, success=False, error=error))
                    logger.warning(error)
                    
        except Exception as fallback_error:
            logger.error(f"Fallback field matching failed: {fallback_error}")
            # Mark remaining steps as failed
            for step in steps:
                if not any(r.step.id == step.id for r in results):
                    step.mark_failed(f"Fallback failed: {fallback_error}")
                    results.append(StepResult(step=step, success=False, error=str(fallback_error)))
        
        return results
    
    # Individual action implementations
    
    async def _execute_navigate(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> None:
        """Navigate to a URL."""
        # Ensure URL has protocol
        url = target
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        await page.goto(url, timeout=self._navigation_timeout_ms)
        await self._state.wait_for_stable(page)
    
    async def _execute_click(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> None:
        """Click an element with multi-strategy validation."""
        from llm_web_agent.engine.step_validator import get_step_validator
        
        validator = get_step_validator()
        
        # If there was a recent hover, re-apply it to keep dropdown open
        last_hover_selector = context.extracted.get("_last_hover_selector")
        if last_hover_selector:
            try:
                logger.info(f"Re-hovering on '{last_hover_selector}' to keep dropdown open")
                await page.hover(last_hover_selector)
                await asyncio.sleep(0.3)  # Let menu fully appear
                
                # Try to click by text match while hovering (for dropdown items)
                # This is more reliable than going through resolver
                try:
                    # Look for visible element with target text in dropdown
                    elements = await page.query_selector_all(f'text="{target}"')
                    for el in elements:
                        if await el.is_visible():
                            logger.info(f"Found visible '{target}' in dropdown, clicking directly")
                            await el.click()
                            await asyncio.sleep(0.3)
                            logger.info(f"✓ Click completed on dropdown item: {target}")
                            context.extracted.pop("_last_hover_selector", None)
                            return
                except Exception as e:
                    logger.debug(f"Direct dropdown click failed: {e}")
            except Exception as e:
                logger.debug(f"Re-hover failed: {e}")
            # Clear after use
            context.extracted.pop("_last_hover_selector", None)
        
        resolved = await self._resolver.resolve(page, target, "click")
        
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        selector = resolved.selector
        
        # IMPORTANT: Scroll element into view first to ensure we're clicking the right one
        try:
            escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
            await page.evaluate(f'''
                (() => {{
                    const el = document.querySelector('{escaped_selector}');
                    if (el) {{
                        el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                    }}
                }})()
            ''')
            await asyncio.sleep(0.3)  # Wait for scroll to complete
        except Exception as e:
            logger.debug(f"scrollIntoView failed: {e}")
        
        # Capture state before click
        url_before = page.url
        dom_hash_before = await validator._get_dom_hash(page)
        
        # Strategy 1: Normal click
        logger.debug(f"Click strategy 1: normal click on '{target}'")
        await page.click(selector)
        await asyncio.sleep(0.3)  # Wait for UI reaction
        
        result = await validator.validate_click(page, selector, url_before, dom_hash_before)
        if result.success:
            logger.info(f"✓ Click validated: {target}")
            return
        
        # Check if URL changed or new tab opened - if so, click worked, don't retry!
        if page.url != url_before:
            logger.info(f"✓ Click caused navigation to {page.url}")
            return
        
        # Check for new tabs - don't click again if a new tab opened
        try:
            all_pages = page.get_all_pages()
            if len(all_pages) > 1:
                logger.info(f"✓ Click opened new tab - not retrying")
                return
        except Exception:
            pass
        
        logger.warning(f"Click may not have worked on '{target}', trying alternative strategies")
        
        # Strategy 2: Force click (bypass actionability checks)
        logger.debug(f"Click strategy 2: force click on '{target}'")
        try:
            url_before = page.url
            dom_hash_before = await validator._get_dom_hash(page)
            await page.click(selector, force=True)
            await asyncio.sleep(0.3)
            
            # Check if click caused navigation
            if page.url != url_before:
                logger.info(f"✓ Click (force) caused navigation to {page.url}")
                return
            
            result = await validator.validate_click(page, selector, url_before, dom_hash_before)
            if result.success:
                logger.info(f"✓ Click validated (force): {target}")
                return
        except Exception as e:
            logger.debug(f"Force click failed: {e}")
        
        # Strategy 3: JavaScript click
        logger.debug(f"Click strategy 3: JS click on '{target}'")
        try:
            escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
            url_before = page.url
            dom_hash_before = await validator._get_dom_hash(page)
            
            await page.evaluate(f'''
                (() => {{
                    const el = document.querySelector('{escaped_selector}');
                    if (el) {{
                        el.scrollIntoView({{block: 'center'}});
                        el.click();
                    }}
                }})()
            ''')
            await asyncio.sleep(0.3)
            
            # Check if click caused navigation
            if page.url != url_before:
                logger.info(f"✓ Click (JS) caused navigation to {page.url}")
                return
            
            result = await validator.validate_click(page, selector, url_before, dom_hash_before)
            if result.success:
                logger.info(f"✓ Click validated (JS): {target}")
                return
        except Exception as e:
            logger.debug(f"JS click failed: {e}")
        
        # Don't fail hard for clicks - UI may have changed in a way we can't detect
        logger.warning(f"Click validation uncertain for '{target}' - continuing")
    
    async def _execute_fill(
        self,
        page: "IPage",
        target: str,
        value: str,
        context: RunContext,
    ) -> None:
        """
        Fill a form field with multi-layer validation and retry.
        
        Enterprise-grade reliability:
        1. Resolve element
        2. Pre-validate (visible, enabled)
        3. Attempt fill with Strategy 1: page.fill()
        4. Validate (read back value)
        5. If failed: Strategy 2: click + type with delay
        6. If failed: Strategy 3: JavaScript direct assignment
        7. Fail hard if all strategies fail
        """
        from llm_web_agent.engine.step_validator import get_step_validator
        
        validator = get_step_validator()
        resolved = await self._resolver.resolve(page, target, "fill")
        
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        fill_value = value or ""
        selector = resolved.selector
        
        # Skip empty values
        if not fill_value:
            logger.debug(f"Skipping fill for '{target}': no value provided")
            return
        
        logger.info(f"Filling '{target}' with value: '{fill_value}'")
        
        # Pre-validation: ensure element is ready
        pre_result = await validator.pre_validate(page, selector, "fill")
        if not pre_result.success:
            logger.warning(f"Pre-validation failed: {pre_result.message}")
            # Try to scroll into view
            try:
                await page.evaluate(
                    f"document.querySelector('{selector}')?.scrollIntoView({{behavior: 'instant', block: 'center'}})"
                )
                await asyncio.sleep(0.2)
            except Exception:
                pass
        
        # Strategy 1: Playwright fill()
        logger.debug("Strategy 1: page.fill()")
        try:
            await page.click(selector)  # Focus first
            await page.fill(selector, "")  # Clear
            await page.fill(selector, fill_value)
            await asyncio.sleep(0.2)  # Wait for value to settle
            
            result = await validator.validate_fill(page, selector, fill_value)
            if result.success:
                logger.info(f"✓ Fill validated (strategy 1): {target} = '{fill_value}'")
                return
            logger.warning(f"Strategy 1 failed: {result.message}")
        except Exception as e:
            logger.warning(f"Strategy 1 error: {e}")
        
        # Strategy 2: Click + Type with delay
        logger.debug("Strategy 2: page.click() + page.type() with delay")
        try:
            await page.click(selector, click_count=3)  # Triple-click to select all
            await asyncio.sleep(0.1)
            await page.keyboard.press("Backspace")  # Clear selection
            await page.type(selector, fill_value, delay=30)
            
            result = await validator.validate_fill(page, selector, fill_value)
            if result.success:
                logger.info(f"✓ Fill validated (strategy 2): {target} = '{fill_value}'")
                return
            logger.warning(f"Strategy 2 failed: {result.message}")
        except Exception as e:
            logger.warning(f"Strategy 2 error: {e}")
        
        # Strategy 3: JavaScript direct assignment + events
        logger.debug("Strategy 3: JavaScript direct assignment")
        try:
            # Escape selector for JS - use CSS.escape if available
            escaped_value = fill_value.replace("\\", "\\\\").replace("'", "\\'")
            escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
            
            await page.evaluate(f'''
                (() => {{
                    const el = document.querySelector('{escaped_selector}');
                    if (el) {{
                        el.focus();
                        el.value = '{escaped_value}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }})()
            ''')
            await asyncio.sleep(0.1)
            
            result = await validator.validate_fill(page, selector, fill_value)
            if result.success:
                logger.info(f"✓ Fill validated (strategy 3): {target} = '{fill_value}'")
                return
            logger.warning(f"Strategy 3 failed: {result.message}")
        except Exception as e:
            logger.warning(f"Strategy 3 error: {e}")
        
        # Strategy 4: Use getElementById for id-based selectors
        logger.debug("Strategy 4: getElementById direct")
        try:
            # Extract ID from selector like 'input[id="first-name"]' or '#first-name'
            import re
            id_match = re.search(r'id=["\']([^"\']+)["\']|#([^\s\[]+)', selector)
            if id_match:
                element_id = id_match.group(1) or id_match.group(2)
                escaped_value = fill_value.replace("\\", "\\\\").replace("'", "\\'")
                
                await page.evaluate(f'''
                    (() => {{
                        const el = document.getElementById('{element_id}');
                        if (el) {{
                            el.focus();
                            el.select();
                            el.value = '{escaped_value}';
                            el.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: '{escaped_value}' }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            // Also set attribute for frameworks that read it
                            el.setAttribute('value', '{escaped_value}');
                        }}
                    }})()
                ''')
                await asyncio.sleep(0.2)
                
                # Verify using getElementById
                actual = await page.evaluate(f"document.getElementById('{element_id}')?.value || ''")
                if actual == fill_value:
                    logger.info(f"✓ Fill validated (strategy 4): {target} = '{fill_value}'")
                    return
                logger.warning(f"Strategy 4 failed: got '{actual}' expected '{fill_value}'")
        except Exception as e:
            logger.warning(f"Strategy 4 error: {e}")
        
        # All strategies failed - this is an enterprise failure
        raise ValueError(
            f"FILL VALIDATION FAILED after all strategies for '{target}'. "
            f"Expected: '{fill_value}', Selector: '{selector}'"
        )
    
    async def _execute_type(
        self,
        page: "IPage",
        target: str,
        value: str,
        context: RunContext,
    ) -> None:
        """Type into a field (key by key)."""
        resolved = await self._resolver.resolve(page, target, "fill")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.type(resolved.selector, value or "")
    
    async def _execute_select(
        self,
        page: "IPage",
        target: str,
        value: str,
        context: RunContext,
    ) -> None:
        """Select an option from a dropdown."""
        resolved = await self._resolver.resolve(page, target, "select")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.select_option(resolved.selector, value or "")
    
    async def _execute_extract(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> str:
        """Extract text from an element."""
        resolved = await self._resolver.resolve(page, target, "extract")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        element = await page.query_selector(resolved.selector)
        if element:
            # Try to get value (for inputs) first
            value = await element.get_attribute("value")
            if value:
                return value.strip()
            
            # Fall back to text content
            text = await element.text_content()
            return text.strip() if text else ""
        
        return ""
    
    async def _execute_hover(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> None:
        """Hover over an element (for dropdown menus etc)."""
        resolved = await self._resolver.resolve(page, target, "hover")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.hover(resolved.selector)
        # Important: Store the hover selector so click can re-hover on dropdown items
        context.extracted["_last_hover_selector"] = resolved.selector
        # Keep the mouse there briefly for menu to appear
        await asyncio.sleep(0.5)
        logger.info(f"✓ Hover completed on '{target}' - dropdown should be visible")
    
    async def _execute_scroll(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> None:
        """Scroll the page or to an element."""
        target_lower = target.lower() if target else ""
        
        if target_lower in ("down", "page down"):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
        elif target_lower in ("up", "page up"):
            await page.evaluate("window.scrollBy(0, -window.innerHeight)")
        elif target_lower in ("top", "to top"):
            await page.evaluate("window.scrollTo(0, 0)")
        elif target_lower in ("bottom", "to bottom"):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            # Scroll to element
            resolved = await self._resolver.resolve(page, target, "scroll")
            if resolved.is_resolved:
                await page.evaluate(
                    f"document.querySelector('{resolved.selector}')?.scrollIntoView({{behavior: 'smooth'}})"
                )
    
    async def _execute_wait(
        self,
        page: "IPage",
        target: Optional[str],
        value: Optional[str],
        context: RunContext,
    ) -> None:
        """Wait for duration or element."""
        import asyncio
        
        if value and value.isdigit():
            # Wait for duration
            await asyncio.sleep(int(value))
        elif target:
            # Wait for element
            resolved = await self._resolver.resolve(page, target, "wait")
            if resolved.is_resolved:
                await page.wait_for_selector(resolved.selector, state="visible")
    
    async def _execute_press_key(
        self,
        page: "IPage",
        key: str,
        context: RunContext,
    ) -> None:
        """Press a keyboard key."""
        key_map = {
            "enter": "Enter",
            "tab": "Tab",
            "escape": "Escape",
            "esc": "Escape",
            "backspace": "Backspace",
            "delete": "Delete",
        }
        actual_key = key_map.get(key.lower(), key)
        await page.keyboard.press(actual_key)
    
    async def _execute_submit(
        self,
        page: "IPage",
        target: Optional[str],
        context: RunContext,
    ) -> None:
        """Submit a form."""
        if target:
            # Click submit button
            resolved = await self._resolver.resolve(page, target, "click")
            if resolved.is_resolved:
                await page.click(resolved.selector)
                return
        
        # Try to find and click submit button
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
        ]
        
        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await page.click(selector)
                    return
            except Exception:
                continue
        
        # Last resort: press Enter
        await page.keyboard.press("Enter")
    
    async def _execute_screenshot(
        self,
        page: "IPage",
        target: Optional[str],
        context: RunContext,
    ) -> None:
        """Take a screenshot."""
        from pathlib import Path
        
        filename = target or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=Path(filename))
