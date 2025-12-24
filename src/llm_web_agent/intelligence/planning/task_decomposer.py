"""
Task Decomposer - Break complex tasks into executable steps.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider
    from llm_web_agent.intelligence.nlp.intent_parser import Intent


class StepDependency(Enum):
    """Dependency types between steps."""
    NONE = "none"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class PlannedStep:
    """
    A planned step in a task.
    
    Attributes:
        step_id: Unique step identifier
        action: Action to perform
        target: Target element or URL
        value: Value for the action
        description: Human-readable description
        dependency: Dependency on previous steps
        depends_on: IDs of steps this depends on
        fallback: Alternative action if this fails
    """
    step_id: str
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    description: str = ""
    dependency: StepDependency = StepDependency.SEQUENTIAL
    depends_on: List[str] = field(default_factory=list)
    fallback: Optional["PlannedStep"] = None


@dataclass
class TaskPlan:
    """
    A complete plan for a task.
    
    Attributes:
        task: Original task description
        steps: Planned steps
        estimated_duration_sec: Estimated execution time
        confidence: Confidence in the plan
        metadata: Additional plan metadata
    """
    task: str
    steps: List[PlannedStep]
    estimated_duration_sec: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskDecomposer:
    """
    Decompose complex tasks into executable steps.
    
    Uses LLM to break down natural language tasks into
    a sequence of browser actions.
    
    Example:
        >>> decomposer = TaskDecomposer(llm_provider)
        >>> plan = await decomposer.decompose("Login to Gmail and send an email")
        >>> for step in plan.steps:
        ...     print(f"{step.step_id}: {step.action} - {step.description}")
    """
    
    def __init__(self, llm_provider: "ILLMProvider"):
        """
        Initialize the decomposer.
        
        Args:
            llm_provider: LLM provider for planning
        """
        self._llm = llm_provider
    
    async def decompose(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskPlan:
        """
        Decompose a task into steps.
        
        Args:
            task: Natural language task description
            context: Additional context (current page state, etc.)
            
        Returns:
            Task plan with steps
        """
        # TODO: Implement LLM-based task decomposition
        raise NotImplementedError("Task decomposition not yet implemented")
    
    async def decompose_from_intent(
        self,
        intent: "Intent",
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskPlan:
        """
        Decompose from a parsed intent.
        
        Args:
            intent: Parsed user intent
            context: Additional context
            
        Returns:
            Task plan
        """
        # TODO: Implement intent-based decomposition
        raise NotImplementedError("Intent decomposition not yet implemented")
    
    def validate_plan(self, plan: TaskPlan) -> tuple[bool, List[str]]:
        """
        Validate a task plan.
        
        Args:
            plan: Plan to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if not plan.steps:
            errors.append("Plan has no steps")
        
        # Check for missing dependencies
        step_ids = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step {step.step_id} depends on unknown step {dep}")
        
        return len(errors) == 0, errors
