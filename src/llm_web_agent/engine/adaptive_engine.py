"""
Adaptive Engine - New execution engine with learning and parallel processing.

This engine replaces the old regex-based pipeline with:
1. LLM-first planning (ONE call for complete task)
2. Site profiling (detect framework, learn selectors)
3. Accessibility-first resolution (Playwright a11y methods)
4. Pattern learning (remember what works)
5. Speculative pre-resolution (lookahead for speed)
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from llm_web_agent.engine.task_planner import (
    TaskPlanner,
    ExecutionPlan,
    PlannedStep,
    ActionType,
    Locator,
    LocatorType,
)
from llm_web_agent.engine.site_profiler import SiteProfiler, SiteProfile, get_site_profiler
from llm_web_agent.engine.accessibility_resolver import (
    AccessibilityResolver,
    ResolutionResult,
    get_accessibility_resolver,
)
from llm_web_agent.engine.selector_pattern_tracker import (
    SelectorPatternTracker,
    get_pattern_tracker,
)
from llm_web_agent.engine.run_context import RunContext

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single step."""
    step: PlannedStep
    success: bool
    duration_ms: float = 0
    error: Optional[str] = None
    selector_used: Optional[str] = None
    locator_type: Optional[LocatorType] = None


@dataclass
class AdaptiveEngineResult:
    """Result of adaptive engine execution."""
    success: bool
    run_id: str
    goal: str
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    duration_seconds: float = 0
    framework_detected: Optional[str] = None
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    step_results: List[StepResult] = field(default_factory=list)


class AdaptiveEngine:
    """
    Adaptive execution engine with learning and parallel processing.
    
    Architecture:
    1. TaskPlanner: ONE LLM call to plan complete task with locators
    2. SiteProfiler: Detect framework and optimal selector strategy
    3. AccessibilityResolver: Use Playwright a11y methods for resolution
    4. SelectorPatternTracker: Learn what works for future tasks
    5. Speculative resolution: Pre-resolve next steps in background
    
    Usage:
        engine = AdaptiveEngine(llm_provider=llm)
        result = await engine.run(page, "Login with user@example.com")
    """
    
    def __init__(
        self,
        llm_provider: "ILLMProvider",
        lookahead_steps: int = 2,
        step_timeout_ms: int = 30000,
    ):
        self._llm = llm_provider
        self._lookahead = lookahead_steps
        self._step_timeout = step_timeout_ms
        
        # Initialize components
        self._planner = TaskPlanner(llm_provider)
        self._profiler = get_site_profiler()
        self._resolver = get_accessibility_resolver()
        self._pattern_tracker = get_pattern_tracker()
        
        # Speculative resolution cache
        self._resolution_futures: Dict[str, asyncio.Task] = {}
    
    async def run(
        self,
        page: "IPage",
        goal: str,
        context: Optional[RunContext] = None,
    ) -> AdaptiveEngineResult:
        """
        Execute a natural language goal with adaptive resolution.
        
        Args:
            page: Browser page
            goal: Natural language goal
            context: Optional run context
            
        Returns:
            AdaptiveEngineResult with execution details
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        ctx = context or RunContext()
        ctx.run_id = run_id
        
        logger.info(f"[{run_id}] Starting adaptive execution: {goal}")
        
        try:
            # Step 1: Detect site profile (framework, selector priorities)
            profile = await self._profiler.get_profile(page)
            logger.info(f"[{run_id}] Site profile: {profile.framework}, priorities: {profile.selector_priorities[:3]}")
            
            # Step 2: Plan complete task with ONE LLM call
            plan = await self._planner.plan(page, goal, context=None)
            logger.info(f"[{run_id}] Planned {len(plan)} steps")
            
            if not plan.steps:
                return AdaptiveEngineResult(
                    success=False,
                    run_id=run_id,
                    goal=goal,
                    framework_detected=profile.framework,
                    error="Could not plan any steps for this goal",
                )
            
            # Step 3: Execute with speculative pre-resolution
            step_results = await self._execute_with_lookahead(
                page, plan, profile, ctx
            )
            
            # Calculate stats
            completed = sum(1 for r in step_results if r.success)
            failed = sum(1 for r in step_results if not r.success)
            duration = time.time() - start_time
            
            success = failed == 0 or (completed > 0 and failed < len(step_results))
            
            return AdaptiveEngineResult(
                success=success,
                run_id=run_id,
                goal=goal,
                steps_total=len(plan.steps),
                steps_completed=completed,
                steps_failed=failed,
                duration_seconds=duration,
                framework_detected=profile.framework,
                extracted_data=ctx.clipboard.copy() if hasattr(ctx, 'clipboard') else {},
                step_results=step_results,
            )
            
        except Exception as e:
            logger.exception(f"[{run_id}] Execution failed")
            return AdaptiveEngineResult(
                success=False,
                run_id=run_id,
                goal=goal,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )
    
    async def _execute_with_lookahead(
        self,
        page: "IPage",
        plan: ExecutionPlan,
        profile: SiteProfile,
        ctx: RunContext,
    ) -> List[StepResult]:
        """Execute steps with speculative pre-resolution."""
        
        results: List[StepResult] = []
        domain = urlparse(page.url).netloc
        
        # Start pre-resolving first N steps
        for i in range(min(self._lookahead, len(plan.steps))):
            self._start_speculative_resolution(page, plan.steps[i], profile)
        
        for i, step in enumerate(plan.steps):
            step_start = time.time()
            logger.debug(f"Executing step {i + 1}/{len(plan)}: {step.action.value} on '{step.target}'")
            
            try:
                # Get resolution (likely already done via lookahead)
                resolution = await self._get_resolution(page, step, profile)
                
                if not resolution.success:
                    logger.warning(f"Could not resolve '{step.target}'")
                    results.append(StepResult(
                        step=step,
                        success=False,
                        duration_ms=(time.time() - step_start) * 1000,
                        error=f"Could not find element: {step.target}",
                    ))
                    
                    if not step.optional:
                        break  # Stop on required step failure
                    continue
                
                # Execute the action
                await self._execute_action(page, step, resolution, ctx)
                
                # Record success for learning
                self._pattern_tracker.record_success(
                    domain=domain,
                    target=step.target,
                    locator_type=resolution.locator_type.value if resolution.locator_type else 'unknown',
                    selector=resolution.selector_used or '',
                )
                
                # Update site profile based on what worked
                if resolution.locator_type:
                    self._profiler.update_priority(
                        domain, resolution.locator_type.value, success=True
                    )
                
                results.append(StepResult(
                    step=step,
                    success=True,
                    duration_ms=(time.time() - step_start) * 1000,
                    selector_used=resolution.selector_used,
                    locator_type=resolution.locator_type,
                ))
                
                # Handle post-action waiting
                await self._wait_after_action(page, step, profile)
                
                # Start pre-resolving future steps
                if i + self._lookahead < len(plan.steps):
                    self._start_speculative_resolution(
                        page, plan.steps[i + self._lookahead], profile
                    )
                
            except Exception as e:
                logger.error(f"Step failed: {e}")
                results.append(StepResult(
                    step=step,
                    success=False,
                    duration_ms=(time.time() - step_start) * 1000,
                    error=str(e),
                ))
                
                if not step.optional:
                    break
        
        return results
    
    def _start_speculative_resolution(
        self,
        page: "IPage",
        step: PlannedStep,
        profile: SiteProfile,
    ) -> None:
        """Start resolving a step in background."""
        if step.id in self._resolution_futures:
            return
        
        if step.action == ActionType.NAVIGATE:
            return  # No resolution needed for navigation
        
        async def resolve():
            # Check pattern tracker for instant match first
            domain = urlparse(page.url).netloc
            cached = self._pattern_tracker.get_exact_match(domain, step.target)
            if cached:
                try:
                    locator = page.locator(cached)
                    if await locator.count() > 0:
                        element = locator.first
                        if await element.is_visible():
                            return ResolutionResult(
                                success=True,
                                locator=element,
                                selector_used=cached,
                                confidence=0.99,  # Cached match
                            )
                except:
                    pass
            
            # Fall back to normal resolution
            return await self._resolver.resolve(
                page, step.locators, profile, step.target
            )
        
        self._resolution_futures[step.id] = asyncio.create_task(resolve())
    
    async def _get_resolution(
        self,
        page: "IPage",
        step: PlannedStep,
        profile: SiteProfile,
    ) -> ResolutionResult:
        """Get resolution for step, using cached if available."""
        
        if step.action == ActionType.NAVIGATE:
            # Navigation doesn't need resolution
            return ResolutionResult(success=True)
        
        if step.id in self._resolution_futures:
            try:
                result = await asyncio.wait_for(
                    self._resolution_futures.pop(step.id),
                    timeout=self._step_timeout / 1000,
                )
                if result.success:
                    return result
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.debug(f"Speculative resolution failed: {e}")
        
        # Fallback: resolve now
        return await self._resolver.resolve_with_fallback(page, step, profile)
    
    async def _execute_action(
        self,
        page: "IPage",
        step: PlannedStep,
        resolution: ResolutionResult,
        ctx: RunContext,
    ) -> None:
        """Execute the action on the resolved element."""
        
        action = step.action
        locator = resolution.locator
        
        if action == ActionType.NAVIGATE:
            url = step.value or step.target
            if not url.startswith('http'):
                url = 'https://' + url
            await page.goto(url)
            logger.info(f"Navigated to {url}")
            
        elif action == ActionType.CLICK:
            await locator.click()
            logger.info(f"Clicked '{step.target}'")
            
        elif action == ActionType.FILL:
            await locator.fill(step.value or '')
            logger.info(f"Filled '{step.target}' with value")
            
        elif action == ActionType.TYPE:
            await locator.type(step.value or '')
            logger.info(f"Typed into '{step.target}'")
            
        elif action == ActionType.SELECT:
            await locator.select_option(step.value or '')
            logger.info(f"Selected '{step.value}' from '{step.target}'")
            
        elif action == ActionType.HOVER:
            await locator.hover()
            logger.info(f"Hovered over '{step.target}'")
            
        elif action == ActionType.SCROLL:
            target = step.target.lower()
            if 'down' in target:
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
            elif 'up' in target:
                await page.evaluate('window.scrollBy(0, -window.innerHeight)')
            elif 'top' in target:
                await page.evaluate('window.scrollTo(0, 0)')
            elif 'bottom' in target:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            else:
                await locator.scroll_into_view_if_needed()
            logger.info(f"Scrolled: {target}")
            
        elif action == ActionType.WAIT:
            if step.value:
                try:
                    wait_time = float(step.value)
                    await asyncio.sleep(wait_time)
                except ValueError:
                    await locator.wait_for(state="visible", timeout=5000)
            logger.info(f"Waited: {step.target}")
            
        elif action == ActionType.PRESS_KEY:
            key = step.value or step.target
            await page.keyboard.press(key.capitalize())
            logger.info(f"Pressed key: {key}")
            
        elif action == ActionType.EXTRACT:
            text = await locator.text_content()
            if step.value:  # store_as
                ctx.store(step.value, text, source="extract")
            logger.info(f"Extracted from '{step.target}': {text[:50] if text else 'empty'}")
    
    async def _wait_after_action(
        self,
        page: "IPage",
        step: PlannedStep,
        profile: SiteProfile,
    ) -> None:
        """Handle post-action waiting based on step and profile."""
        
        wait_spec = step.wait_after
        
        if not wait_spec:
            # Default: brief stability wait
            await asyncio.sleep(0.1)
            return
        
        try:
            if wait_spec == 'navigation':
                await page.wait_for_load_state('networkidle', timeout=10000)
            elif wait_spec == 'network_idle':
                await page.wait_for_load_state('networkidle', timeout=5000)
            elif wait_spec.startswith('selector:'):
                selector = wait_spec.split(':', 1)[1]
                await page.wait_for_selector(selector, timeout=5000)
            elif wait_spec.startswith('time:'):
                seconds = float(wait_spec.split(':', 1)[1])
                await asyncio.sleep(seconds)
            else:
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.debug(f"Wait condition '{wait_spec}' failed: {e}")
    
    async def plan_only(self, page: "IPage", goal: str) -> ExecutionPlan:
        """
        Plan task without executing (for preview/debugging).
        
        Returns:
            ExecutionPlan with all steps and locators
        """
        return await self._planner.plan(page, goal)
    
    async def run_with_report(
        self,
        page: "IPage",
        goal: str,
        output_dir: str = "./reports",
        formats: List[str] = None,
        capture_screenshots: bool = True,
        generate_ai_summary: bool = True,
        context: Optional[RunContext] = None,
    ) -> "AdaptiveEngineResult":
        """
        Execute goal with comprehensive documentation generation.
        
        Captures screenshots at each step and generates reports in multiple formats.
        
        Args:
            page: Browser page
            goal: Natural language goal
            output_dir: Directory for reports
            formats: Report formats ['json', 'md', 'html', 'pdf', 'docx']
            capture_screenshots: Whether to capture screenshots
            generate_ai_summary: Whether to generate AI summary
            context: Optional run context
            
        Returns:
            AdaptiveEngineResult with execution details
        """
        from pathlib import Path
        from llm_web_agent.reporting.execution_report import (
            ExecutionReportGenerator,
            ExecutionReport,
            StepDetail,
        )
        from llm_web_agent.reporting.screenshot_manager import ScreenshotManager
        
        formats = formats or ['json', 'md', 'html']
        
        # Generate run ID
        run_id = str(uuid.uuid4())[:8]
        
        # Initialize screenshot manager if needed
        screenshot_mgr = None
        screenshots: Dict[int, str] = {}
        
        if capture_screenshots:
            screenshot_mgr = ScreenshotManager(
                output_dir=output_dir,
                run_id=run_id,
            )
        
        # Override _execute_with_lookahead to capture screenshots
        original_execute = self._execute_with_lookahead
        
        async def execute_with_screenshots(
            page, plan, profile, ctx
        ) -> List[StepResult]:
            results = []
            domain = urlparse(page.url).netloc
            
            # Start pre-resolving first N steps
            for i in range(min(self._lookahead, len(plan.steps))):
                self._start_speculative_resolution(page, plan.steps[i], profile)
            
            for i, step in enumerate(plan.steps):
                step_number = i + 1
                step_start = time.time()
                
                # Capture screenshot BEFORE action
                if screenshot_mgr:
                    try:
                        await screenshot_mgr.capture(
                            page, step_number,
                            description=f"Before: {step.action.value} on '{step.target}'"
                        )
                    except Exception as e:
                        logger.debug(f"Screenshot failed: {e}")
                
                try:
                    resolution = await self._get_resolution(page, step, profile)
                    
                    if not resolution.success:
                        # Capture error screenshot
                        if screenshot_mgr:
                            await screenshot_mgr.capture_on_error(
                                page, step_number, f"Could not find: {step.target}"
                            )
                        
                        results.append(StepResult(
                            step=step,
                            success=False,
                            duration_ms=(time.time() - step_start) * 1000,
                            error=f"Could not find element: {step.target}",
                        ))
                        
                        if not step.optional:
                            break
                        continue
                    
                    # Execute action
                    await self._execute_action(page, step, resolution, ctx)
                    
                    # Record success
                    self._pattern_tracker.record_success(
                        domain=domain,
                        target=step.target,
                        locator_type=resolution.locator_type.value if resolution.locator_type else 'unknown',
                        selector=resolution.selector_used or '',
                    )
                    
                    if resolution.locator_type:
                        self._profiler.update_priority(
                            domain, resolution.locator_type.value, success=True
                        )
                    
                    # Capture screenshot AFTER action
                    if screenshot_mgr:
                        try:
                            ss = await screenshot_mgr.capture(
                                page, step_number,
                                description=f"After: {step.action.value}"
                            )
                            screenshots[step_number] = str(ss.path)
                        except Exception as e:
                            logger.debug(f"Post-action screenshot failed: {e}")
                    
                    results.append(StepResult(
                        step=step,
                        success=True,
                        duration_ms=(time.time() - step_start) * 1000,
                        selector_used=resolution.selector_used,
                        locator_type=resolution.locator_type,
                    ))
                    
                    await self._wait_after_action(page, step, profile)
                    
                    if i + self._lookahead < len(plan.steps):
                        self._start_speculative_resolution(
                            page, plan.steps[i + self._lookahead], profile
                        )
                    
                except Exception as e:
                    logger.error(f"Step failed: {e}")
                    if screenshot_mgr:
                        await screenshot_mgr.capture_on_error(page, step_number, str(e))
                    
                    results.append(StepResult(
                        step=step,
                        success=False,
                        duration_ms=(time.time() - step_start) * 1000,
                        error=str(e),
                    ))
                    
                    if not step.optional:
                        break
            
            return results
        
        # Temporarily replace the method
        self._execute_with_lookahead = execute_with_screenshots
        
        try:
            # Run the execution
            result = await self.run(page, goal, context)
            
            # Create report generator
            report_gen = ExecutionReportGenerator(
                output_dir=output_dir,
                include_screenshots=capture_screenshots,
            )
            
            # Create execution report
            report = report_gen.create_report(
                run_id=result.run_id,
                goal=goal,
                success=result.success,
                step_results=result.step_results,
                duration_seconds=result.duration_seconds,
                framework_detected=result.framework_detected,
                screenshots=screenshots,
            )
            
            # Generate AI summary
            if generate_ai_summary:
                await report_gen.generate_ai_content(report, self._llm)
            
            # Export to all formats
            exported = report_gen.export_all(report, formats)
            
            logger.info(f"Generated reports: {list(exported.keys())}")
            
            return result
            
        finally:
            # Restore original method
            self._execute_with_lookahead = original_execute

