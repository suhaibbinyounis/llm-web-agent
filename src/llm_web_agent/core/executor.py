"""
Executor - Step execution with error handling and retries.

This module executes individual steps from the planner, handling
errors, retries, and maintaining execution context.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging
import time

if TYPE_CHECKING:
    from llm_web_agent.config.settings import Settings
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.action import ActionResult
    from llm_web_agent.core.planner import TaskStep

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """
    Context for step execution.
    
    Maintains state across step executions, including history,
    extracted data, and error information.
    
    Attributes:
        page: Current browser page
        step_history: History of executed steps
        extracted_data: Data extracted during execution
        variables: Variables that can be used in steps
        current_url: Current page URL
        screenshots: Screenshots taken during execution
    """
    page: "IPage"
    step_history: List[Dict[str, Any]] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    current_url: str = ""
    screenshots: List[bytes] = field(default_factory=list)
    
    def add_step_result(
        self,
        step: "TaskStep",
        result: "ActionResult",
        duration_ms: float,
    ) -> None:
        """Record a step execution result."""
        self.step_history.append({
            "step_number": step.step_number,
            "step_type": step.step_type.value,
            "description": step.description,
            "success": result.success,
            "error": result.error,
            "duration_ms": duration_ms,
        })
    
    def set_variable(self, name: str, value: str) -> None:
        """Set a context variable."""
        self.variables[name] = value
    
    def get_variable(self, name: str, default: str = "") -> str:
        """Get a context variable."""
        return self.variables.get(name, default)


@dataclass
class ExecutionResult:
    """
    Result of executing a step or sequence of steps.
    
    Attributes:
        success: Whether execution was successful
        steps_executed: Number of steps executed
        last_step: The last step that was executed
        error: Error message if execution failed
        duration_ms: Total execution time in milliseconds
        context: The execution context after execution
    """
    success: bool
    steps_executed: int = 0
    last_step: Optional["TaskStep"] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    context: Optional[ExecutionContext] = None


class Executor:
    """
    Step executor with error handling and retry logic.
    
    The Executor takes steps from the Planner and executes them
    on the browser page, handling errors and implementing retries.
    
    Example:
        >>> executor = Executor(settings)
        >>> context = ExecutionContext(page=page)
        >>> result = await executor.execute_step(step, context)
    """
    
    def __init__(self, settings: "Settings"):
        """
        Initialize the Executor.
        
        Args:
            settings: Configuration settings
        """
        self._settings = settings
    
    async def execute_step(
        self,
        step: "TaskStep",
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute a single step.
        
        Args:
            step: The step to execute
            context: Execution context
            
        Returns:
            ExecutionResult with the outcome
        """
        # TODO: Implement step execution
        # 1. Get the appropriate action for the step type
        # 2. Execute the action with retries
        # 3. Update context with result
        # 4. Take screenshot if configured
        
        logger.info(f"Executing step {step.step_number}: {step.description}")
        
        start_time = time.perf_counter()
        
        # Placeholder - actual implementation will use registry to get actions
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        return ExecutionResult(
            success=False,
            steps_executed=1,
            last_step=step,
            error="Step execution not yet implemented",
            duration_ms=duration_ms,
            context=context,
        )
    
    async def execute_steps(
        self,
        steps: List["TaskStep"],
        context: ExecutionContext,
        stop_on_error: bool = True,
    ) -> ExecutionResult:
        """
        Execute a sequence of steps.
        
        Args:
            steps: List of steps to execute
            context: Execution context
            stop_on_error: Whether to stop on first error
            
        Returns:
            ExecutionResult with the outcome
        """
        start_time = time.perf_counter()
        steps_executed = 0
        last_step = None
        
        for step in steps:
            result = await self.execute_step(step, context)
            steps_executed += 1
            last_step = step
            
            if not result.success and stop_on_error:
                return ExecutionResult(
                    success=False,
                    steps_executed=steps_executed,
                    last_step=last_step,
                    error=result.error,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    context=context,
                )
            
            # Add delay between steps
            if self._settings.agent.step_delay_ms > 0:
                await self._delay(self._settings.agent.step_delay_ms)
        
        return ExecutionResult(
            success=True,
            steps_executed=steps_executed,
            last_step=last_step,
            duration_ms=(time.perf_counter() - start_time) * 1000,
            context=context,
        )
    
    async def _delay(self, ms: int) -> None:
        """Wait for specified milliseconds."""
        import asyncio
        await asyncio.sleep(ms / 1000)
    
    async def _retry_step(
        self,
        step: "TaskStep",
        context: ExecutionContext,
        max_attempts: int,
    ) -> ExecutionResult:
        """
        Execute a step with retries.
        
        Args:
            step: The step to execute
            context: Execution context
            max_attempts: Maximum retry attempts
            
        Returns:
            ExecutionResult with the outcome
        """
        last_error = None
        
        for attempt in range(max_attempts):
            result = await self.execute_step(step, context)
            
            if result.success:
                return result
            
            last_error = result.error
            logger.warning(
                f"Step {step.step_number} failed (attempt {attempt + 1}/{max_attempts}): {last_error}"
            )
            
            if attempt < max_attempts - 1:
                # Exponential backoff
                await self._delay(1000 * (2 ** attempt))
        
        return ExecutionResult(
            success=False,
            steps_executed=1,
            last_step=step,
            error=f"Step failed after {max_attempts} attempts: {last_error}",
            context=context,
        )
