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
    ):
        """
        Initialize the executor.
        
        Args:
            resolver: Target resolver instance
            state_manager: State manager instance
            llm_provider: Optional LLM for complex cases
        """
        self._resolver = resolver or TargetResolver()
        self._state = state_manager or StateManager()
        self._llm = llm_provider
    
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
        """Execute a single step."""
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
            
            return StepResult(step=step, success=True, duration_ms=duration)
        
        except Exception as e:
            duration = (time.time() - start) * 1000
            error = str(e)
            step.mark_failed(error, duration_ms=duration)
            logger.error(f"Step failed: {step.intent.value} → {error}")
            
            return StepResult(step=step, success=False, duration_ms=duration, error=error)
    
    async def _execute_batch_fill(
        self,
        page: "IPage",
        steps: List[TaskStep],
        context: RunContext,
    ) -> List[StepResult]:
        """Execute multiple fill operations efficiently."""
        results = []
        
        # Resolve all targets first
        targets: Dict[str, Tuple[TaskStep, ResolvedTarget]] = {}
        for step in steps:
            resolved = await self._resolver.resolve(page, step.target, "fill")
            if resolved.is_resolved:
                targets[step.id] = (step, resolved)
            else:
                # Can't resolve, will fail this step
                step.mark_failed(f"Could not find element: {step.target}")
                results.append(StepResult(step=step, success=False, error="Element not found"))
        
        # Build fill data
        fill_data: Dict[str, str] = {}
        for step_id, (step, resolved) in targets.items():
            value = step.value or ""
            if context.has_references(value):
                value = context.resolve(value)
            fill_data[resolved.selector] = value
        
        # Try JavaScript batch fill (fastest)
        if fill_data:
            try:
                await page.evaluate("""
                    (data) => {
                        for (const [selector, value] of Object.entries(data)) {
                            const el = document.querySelector(selector);
                            if (el) {
                                el.value = value;
                                el.dispatchEvent(new Event('input', {bubbles: true}));
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                            }
                        }
                    }
                """, fill_data)
                
                # Mark all as success
                for step_id, (step, resolved) in targets.items():
                    step.mark_success()
                    results.append(StepResult(step=step, success=True))
                    
            except Exception as e:
                logger.warning(f"Batch fill via JS failed, falling back: {e}")
                # Fall back to individual fills
                for step_id, (step, resolved) in targets.items():
                    try:
                        value = step.value or ""
                        if context.has_references(value):
                            value = context.resolve(value)
                        await page.fill(resolved.selector, value)
                        step.mark_success()
                        results.append(StepResult(step=step, success=True))
                    except Exception as fill_error:
                        step.mark_failed(str(fill_error))
                        results.append(StepResult(step=step, success=False, error=str(fill_error)))
        
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
        
        await page.goto(url)
        await self._state.wait_for_stable(page)
    
    async def _execute_click(
        self,
        page: "IPage",
        target: str,
        context: RunContext,
    ) -> None:
        """Click an element."""
        resolved = await self._resolver.resolve(page, target, "click")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.click(resolved.selector)
    
    async def _execute_fill(
        self,
        page: "IPage",
        target: str,
        value: str,
        context: RunContext,
    ) -> None:
        """Fill a form field."""
        resolved = await self._resolver.resolve(page, target, "fill")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.fill(resolved.selector, value or "")
    
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
        """Hover over an element."""
        resolved = await self._resolver.resolve(page, target, "hover")
        if not resolved.is_resolved:
            raise ValueError(f"Could not find element: {target}")
        
        await page.hover(resolved.selector)
    
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
