"""
Task Graph - Represent parsed instructions as executable steps.

Handles:
- TaskStep definition with dependencies
- TaskGraph for managing step execution order
- Batching of steps that can run on same DOM
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class StepStatus(Enum):
    """Status of a task step."""
    PENDING = "pending"
    READY = "ready"        # Dependencies met, can execute
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepIntent(Enum):
    """Types of step intents."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    HOVER = "hover"
    SCROLL = "scroll"
    WAIT = "wait"
    EXTRACT = "extract"     # Copy/read a value
    SUBMIT = "submit"
    PRESS_KEY = "press_key"
    SCREENSHOT = "screenshot"
    CUSTOM = "custom"


@dataclass
class TaskStep:
    """
    A single executable step in a task.
    
    Attributes:
        id: Unique step identifier
        intent: Type of action (click, fill, navigate, etc.)
        target: Element selector, text description, or URL
        value: Value for input actions
        store_as: If extracting, key to store result
        depends_on: Step IDs that must complete first
        wait_for_navigation: Whether this step causes page load
        optional: Whether step failure should halt execution
        metadata: Additional step-specific data
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    intent: StepIntent = StepIntent.CUSTOM
    target: Optional[str] = None
    value: Optional[str] = None
    store_as: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    wait_for_navigation: bool = False
    optional: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0
    
    # Batching hint - steps with same batch_group execute together
    batch_group: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if step has finished (success or failure)."""
        return self.status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SKIPPED)
    
    def is_ready(self, completed_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_ids for dep in self.depends_on)
    
    def mark_success(self, result: Any = None, duration_ms: float = 0) -> None:
        """Mark step as successful."""
        self.status = StepStatus.SUCCESS
        self.result = result
        self.duration_ms = duration_ms
    
    def mark_failed(self, error: str, duration_ms: float = 0) -> None:
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.error = error
        self.duration_ms = duration_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "intent": self.intent.value,
            "target": self.target,
            "value": self.value,
            "store_as": self.store_as,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class TaskGraph:
    """
    A graph of task steps with dependencies.
    
    Manages execution order, batching, and progress tracking.
    
    Example:
        >>> graph = TaskGraph()
        >>> step1 = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        >>> step2 = graph.add_step(StepIntent.FILL, target="search", value="hello",
        ...                        depends_on=[step1.id])
        >>> batches = graph.get_execution_batches()
    """
    
    steps: List[TaskStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Original instruction for reference
    original_instruction: str = ""
    
    def add_step(
        self,
        intent: StepIntent,
        target: Optional[str] = None,
        value: Optional[str] = None,
        store_as: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        wait_for_navigation: bool = False,
        **kwargs: Any,
    ) -> TaskStep:
        """
        Add a new step to the graph.
        
        Args:
            intent: Type of action
            target: Target element or URL
            value: Value for input
            store_as: Key to store extracted value
            depends_on: Step IDs this depends on
            wait_for_navigation: Whether step causes navigation
            **kwargs: Additional step metadata
            
        Returns:
            Created TaskStep
        """
        step = TaskStep(
            intent=intent,
            target=target,
            value=value,
            store_as=store_as,
            depends_on=depends_on or [],
            wait_for_navigation=wait_for_navigation,
            metadata=kwargs,
        )
        
        # Auto-detect navigation from intent
        if intent == StepIntent.NAVIGATE:
            step.wait_for_navigation = True
        elif intent == StepIntent.SUBMIT:
            step.wait_for_navigation = True
        
        self.steps.append(step)
        return step
    
    def get_step(self, step_id: str) -> Optional[TaskStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_ready_steps(self) -> List[TaskStep]:
        """Get all steps that are ready to execute."""
        completed = {s.id for s in self.steps if s.is_complete()}
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING and s.is_ready(completed)
        ]
    
    def get_pending_steps(self) -> List[TaskStep]:
        """Get all pending steps."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]
    
    def get_completed_steps(self) -> List[TaskStep]:
        """Get all completed steps."""
        return [s for s in self.steps if s.is_complete()]
    
    def is_complete(self) -> bool:
        """Check if all steps are complete."""
        return all(s.is_complete() for s in self.steps)
    
    def has_failures(self) -> bool:
        """Check if any required step failed."""
        return any(
            s.status == StepStatus.FAILED and not s.optional
            for s in self.steps
        )
    
    def get_execution_batches(self) -> List[List[TaskStep]]:
        """
        Get steps grouped into execution batches.
        
        Steps in the same batch can potentially execute on the same DOM.
        Respects dependencies - later batches depend on earlier ones.
        
        Returns:
            List of batches, each containing steps to execute together
        """
        batches: List[List[TaskStep]] = []
        completed: Set[str] = set()
        remaining = list(self.steps)
        
        while remaining:
            # Find all steps that can execute now
            batch = []
            for step in remaining[:]:
                if step.is_ready(completed):
                    batch.append(step)
            
            if not batch:
                # No progress possible - circular dependency or all complete
                break
            
            # Group by navigation requirement
            # Steps before a navigation go together
            # The navigation step is alone or at the end
            nav_idx = None
            for i, step in enumerate(batch):
                if step.wait_for_navigation:
                    nav_idx = i
                    break
            
            if nav_idx is not None:
                # Split at navigation
                pre_nav = batch[:nav_idx + 1]
                batches.append(pre_nav)
                for step in pre_nav:
                    remaining.remove(step)
                    completed.add(step.id)
            else:
                # All non-navigation, batch them
                batches.append(batch)
                for step in batch:
                    remaining.remove(step)
                    completed.add(step.id)
        
        return batches
    
    def get_same_page_groups(self) -> List[List[TaskStep]]:
        """
        Group steps that operate on the same page.
        
        Uses batch_group hints and navigation detection.
        
        Returns:
            Groups of steps, each group on same page
        """
        if not self.steps:
            return []
        
        groups: List[List[TaskStep]] = []
        current_group: List[TaskStep] = []
        
        for step in self.steps:
            if step.wait_for_navigation and current_group:
                # This step causes navigation
                current_group.append(step)
                groups.append(current_group)
                current_group = []
            else:
                current_group.append(step)
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def to_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [f"TaskGraph: {len(self.steps)} steps"]
        for i, step in enumerate(self.steps):
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.READY: "🔵",
                StepStatus.RUNNING: "🔄",
                StepStatus.SUCCESS: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "?")
            
            target_str = f" → {step.target[:30]}" if step.target else ""
            value_str = f" = '{step.value[:20]}'" if step.value else ""
            
            lines.append(f"  {status_icon} {i+1}. {step.intent.value}{target_str}{value_str}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_instruction": self.original_instruction,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }
