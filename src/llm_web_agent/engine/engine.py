"""
Engine - Main orchestrator that ties all components together.

This is the primary entry point for the NL-to-actions pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import time
import uuid
import logging

from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.task_graph import TaskGraph, TaskStep, StepStatus
from llm_web_agent.engine.instruction_parser import InstructionParser
from llm_web_agent.engine.target_resolver import TargetResolver
from llm_web_agent.engine.batch_executor import BatchExecutor, BatchResult
from llm_web_agent.engine.state_manager import StateManager

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


@dataclass
class EngineResult:
    """
    Result of engine execution.
    
    Attributes:
        success: Whether the task completed successfully
        run_id: Unique run identifier
        task: Original task description
        steps_total: Total number of steps
        steps_completed: Successfully completed steps
        steps_failed: Failed steps
        duration_seconds: Total execution time
        extracted_data: Any extracted data (copy operations)
        error: Error message if failed
        context: The run context with full history
    """
    success: bool
    run_id: str
    task: str
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    duration_seconds: float = 0
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    context: Optional[RunContext] = None


class Engine:
    """
    Main execution engine for NL-to-actions.
    
    Orchestrates the full pipeline:
    1. Parse instruction into TaskGraph
    2. Group steps into batches
    3. Execute batches with optimization
    4. Handle errors and retries
    5. Return results with extracted data
    
    Example:
        >>> engine = Engine(llm_provider=llm)
        >>> result = await engine.run(page, "Go to google and search for cats")
        >>> print(f"Success: {result.success}")
        >>> print(f"Data: {result.extracted_data}")
    """
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        max_retries: int = 2,
        step_timeout_ms: int = 30000,
        navigation_timeout_ms: int = 60000,
        step_delay_ms: int = 0,
        max_steps: int = 50,
    ):
        """
        Initialize the engine.
        
        Args:
            llm_provider: LLM for complex parsing/resolution
            max_retries: Maximum retries per step
            step_timeout_ms: Timeout for each step
            navigation_timeout_ms: Timeout for page navigation (page.goto)
            step_delay_ms: Delay between steps in milliseconds
            max_steps: Maximum number of steps per task
        """
        self._llm = llm_provider
        self._max_retries = max_retries
        self._step_timeout = step_timeout_ms
        self._navigation_timeout = navigation_timeout_ms
        self._step_delay_ms = step_delay_ms
        self._max_steps = max_steps
        
        # Initialize components
        self._parser = InstructionParser(llm_provider)
        self._resolver = TargetResolver(llm_provider)
        self._state_manager = StateManager()
        self._executor = BatchExecutor(
            resolver=self._resolver,
            state_manager=self._state_manager,
            llm_provider=llm_provider,
            navigation_timeout_ms=navigation_timeout_ms,
            step_timeout_ms=step_timeout_ms,
            max_attempts=max_retries + 1,  # max_retries + 1 initial attempt
            step_delay_ms=step_delay_ms,
        )
    
    async def run(
        self,
        page: "IPage",
        task: str,
        context: Optional[RunContext] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> EngineResult:
        """
        Execute a natural language task.
        
        Args:
            page: Browser page to operate on
            task: Natural language task description
            context: Optional existing context (for chaining tasks)
            variables: Optional variables to pre-populate
            
        Returns:
            EngineResult with execution details
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        
        # Initialize context
        ctx = context or RunContext()
        ctx.run_id = run_id
        
        # Pre-populate variables
        if variables:
            for key, value in variables.items():
                ctx.store(key, value, source="variable")
        
        logger.info(f"[{run_id}] Starting task: {task}")
        
        try:
            # Step 1: Parse instruction
            graph = await self._parser.parse(task)
            
            if not graph.steps:
                logger.warning(f"[{run_id}] No steps parsed from instruction")
                return EngineResult(
                    success=False,
                    run_id=run_id,
                    task=task,
                    error="Could not parse instruction into executable steps",
                    context=ctx,
                )
            
            logger.info(f"[{run_id}] Parsed {len(graph.steps)} steps")
            logger.debug(f"[{run_id}] {graph.to_summary()}")
            
            # Step 2: Get execution batches
            batches = graph.get_execution_batches()
            logger.info(f"[{run_id}] Organized into {len(batches)} batches")
            
            # Step 3: Execute batches
            for batch_idx, batch in enumerate(batches):
                logger.debug(f"[{run_id}] Executing batch {batch_idx + 1}/{len(batches)}")
                
                batch_result = await self._executor.execute_batch(page, batch, ctx)
                
                # Check for failures
                if not batch_result.all_success:
                    failed_steps = [
                        r.step for r in batch_result.results
                        if not r.success and not r.step.optional
                    ]
                    
                    if failed_steps:
                        # Retry failed steps
                        for step in failed_steps:
                            retried = await self._retry_step(page, step, ctx)
                            if not retried:
                                # Critical failure
                                duration = time.time() - start_time
                                return EngineResult(
                                    success=False,
                                    run_id=run_id,
                                    task=task,
                                    steps_total=len(graph.steps),
                                    steps_completed=len(graph.get_completed_steps()),
                                    steps_failed=len([s for s in graph.steps if s.status == StepStatus.FAILED]),
                                    duration_seconds=duration,
                                    extracted_data=ctx.clipboard.copy(),
                                    error=f"Step failed: {step.error}",
                                    context=ctx,
                                )
            
            # All batches complete
            duration = time.time() - start_time
            
            return EngineResult(
                success=True,
                run_id=run_id,
                task=task,
                steps_total=len(graph.steps),
                steps_completed=len([s for s in graph.steps if s.status == StepStatus.SUCCESS]),
                steps_failed=len([s for s in graph.steps if s.status == StepStatus.FAILED]),
                duration_seconds=duration,
                extracted_data=ctx.clipboard.copy(),
                context=ctx,
            )
        
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"[{run_id}] Task failed with exception")
            
            return EngineResult(
                success=False,
                run_id=run_id,
                task=task,
                duration_seconds=duration,
                error=str(e),
                context=ctx,
            )
    
    async def run_steps(
        self,
        page: "IPage",
        steps: List[TaskStep],
        context: Optional[RunContext] = None,
    ) -> EngineResult:
        """
        Execute pre-built steps directly.
        
        Useful for Record & Replay or programmatic task building.
        
        Args:
            page: Browser page
            steps: Pre-built TaskSteps
            context: Optional context
            
        Returns:
            EngineResult
        """
        run_id = str(uuid.uuid4())[:8]
        ctx = context or RunContext()
        ctx.run_id = run_id
        start_time = time.time()
        
        # Build graph from steps
        graph = TaskGraph(steps=steps)
        batches = graph.get_execution_batches()
        
        for batch in batches:
            await self._executor.execute_batch(page, batch, ctx)
        
        duration = time.time() - start_time
        
        return EngineResult(
            success=not graph.has_failures(),
            run_id=run_id,
            task="Custom steps",
            steps_total=len(steps),
            steps_completed=len([s for s in steps if s.status == StepStatus.SUCCESS]),
            steps_failed=len([s for s in steps if s.status == StepStatus.FAILED]),
            duration_seconds=duration,
            extracted_data=ctx.clipboard.copy(),
            context=ctx,
        )
    
    async def _retry_step(
        self,
        page: "IPage",
        step: TaskStep,
        context: RunContext,
    ) -> bool:
        """
        Retry a failed step with LLM-assisted recovery.
        
        Args:
            page: Browser page
            step: Failed step to retry
            context: Run context
            
        Returns:
            True if retry succeeded
        """
        for attempt in range(self._max_retries):
            logger.info(f"Retrying step {step.id} (attempt {attempt + 1}/{self._max_retries})")
            
            # Wait for page stability
            await self._state_manager.wait_for_stable(page)
            
            # On second attempt, try LLM-assisted recovery
            if attempt > 0 and self._llm:
                recovery = await self._get_llm_recovery(page, step, context)
                if recovery:
                    # Try recovery steps instead
                    for recovery_step in recovery:
                        recovery_step.status = StepStatus.PENDING
                        result = await self._executor.execute_batch(page, [recovery_step], context)
                        if result.all_success:
                            # Mark original step as success
                            step.status = StepStatus.SUCCESS
                            step.error = None
                            return True
            
            # Reset step status and try again
            step.status = StepStatus.PENDING
            step.error = None
            
            result = await self._executor.execute_batch(page, [step], context)
            
            if result.all_success:
                return True
        
        return False
    
    async def _get_llm_recovery(
        self,
        page: "IPage",
        step: TaskStep,
        context: RunContext,
    ) -> Optional[List[TaskStep]]:
        """Get LLM-suggested recovery steps."""
        if not self._llm:
            return None
        
        from llm_web_agent.engine.llm.strategy import LLMStrategy
        from llm_web_agent.engine.task_graph import StepIntent
        
        try:
            strategy = LLMStrategy(self._llm)
            
            failed_action = f"{step.intent.value} on '{step.target}'"
            if step.value:
                failed_action += f" with value '{step.value}'"
            
            recovery = await strategy.suggest_recovery(
                page=page,
                failed_action=failed_action,
                error=step.error or "Unknown error",
                context=context,
            )
            
            if not recovery.recovery_steps:
                return None
            
            # Convert recovery steps to TaskSteps
            result = []
            for rec_step in recovery.recovery_steps:
                try:
                    intent = StepIntent(rec_step.intent)
                except ValueError:
                    intent = StepIntent.CUSTOM
                
                result.append(TaskStep(
                    intent=intent,
                    target=rec_step.target,
                    value=rec_step.value,
                ))
            
            logger.info(f"LLM suggested {len(result)} recovery steps: {recovery.diagnosis}")
            return result
        
        except Exception as e:
            logger.debug(f"LLM recovery failed: {e}")
            return None
    
    def parse_instruction(self, instruction: str) -> TaskGraph:
        """
        Parse an instruction synchronously (pattern matching only).
        
        Useful for previewing what steps would be generated.
        
        Args:
            instruction: Natural language instruction
            
        Returns:
            TaskGraph with parsed steps
        """
        return self._parser.parse_sync(instruction)
