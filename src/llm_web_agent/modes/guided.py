"""
Guided Mode - Natural language + explicit locator hints.

User provides both a natural language description AND specific hints
about elements (selectors, element names, etc.) to help the agent
be more accurate.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from llm_web_agent.modes.base import (
    IInteractionMode,
    ModeType,
    ModeConfig,
    ModeResult,
)

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


@dataclass
class LocatorHint:
    """
    A hint about an element's location.
    
    Attributes:
        name: Friendly name for reference in task (e.g., "login_button")
        selector: CSS selector
        xpath: XPath selector (alternative)
        text: Text content to match
        role: ARIA role
        description: Description of the element
    """
    name: str
    selector: Optional[str] = None
    xpath: Optional[str] = None
    text: Optional[str] = None
    role: Optional[str] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "selector": self.selector,
            "xpath": self.xpath,
            "text": self.text,
            "role": self.role,
            "description": self.description,
        }


@dataclass
class GuidedTaskInput:
    """
    Input for guided mode execution.
    
    Attributes:
        task: Natural language task description
        hints: List of locator hints for elements
        data: Data to use in form filling (key-value pairs)
        options: Additional execution options
    """
    task: str
    hints: List[LocatorHint] = field(default_factory=list)
    data: Dict[str, str] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    
    def get_hint(self, name: str) -> Optional[LocatorHint]:
        """Get a hint by name."""
        for hint in self.hints:
            if hint.name == name:
                return hint
        return None
    
    def get_selector(self, name: str) -> Optional[str]:
        """Get selector for a named element."""
        hint = self.get_hint(name)
        return hint.selector if hint else None


class GuidedMode(IInteractionMode):
    """
    Guided interaction mode.
    
    Combines natural language with explicit hints about element locations.
    This provides the best of both worlds - natural task description with
    guaranteed accuracy of known selectors.
    
    Example:
        >>> mode = GuidedMode(llm_provider)
        >>> await mode.start(page, config)
        >>> 
        >>> task_input = GuidedTaskInput(
        ...     task="Login to the application",
        ...     hints=[
        ...         LocatorHint(name="username", selector="#email"),
        ...         LocatorHint(name="password", selector="#password"),
        ...         LocatorHint(name="submit", selector="button[type='submit']"),
        ...     ],
        ...     data={
        ...         "username": "user@example.com",
        ...         "password": "secret123",
        ...     },
        ... )
        >>> result = await mode.execute(task_input)
    """
    
    @property
    def mode_type(self) -> ModeType:
        return ModeType.GUIDED
    
    @property
    def name(self) -> str:
        return "Guided"
    
    @property
    def description(self) -> str:
        return "Natural language tasks with explicit element hints for accuracy"
    
    def __init__(self, llm_provider: Optional["ILLMProvider"] = None):
        """
        Initialize the mode.
        
        Args:
            llm_provider: Optional LLM for task understanding
        """
        self._llm = llm_provider
        self._page: Optional["IPage"] = None
        self._config: Optional[ModeConfig] = None
        self._is_running = False
    
    async def start(
        self,
        page: "IPage",
        config: ModeConfig,
        **kwargs: Any,
    ) -> None:
        """Start the guided mode."""
        self._page = page
        self._config = config
        self._is_running = True
        logger.info("Guided mode started")
    
    async def execute(self, input_data: Any) -> ModeResult:
        """
        Execute a guided task.
        
        Args:
            input_data: GuidedTaskInput with task and hints
            
        Returns:
            Execution result
        """
        if not self._page or not self._is_running:
            return ModeResult(
                success=False,
                error="Mode not started. Call start() first.",
            )
        
        # Parse input
        if isinstance(input_data, GuidedTaskInput):
            task_input = input_data
        elif isinstance(input_data, dict):
            task_input = self._parse_dict_input(input_data)
        else:
            return ModeResult(success=False, error="Invalid input type")
        
        logger.info(f"Executing guided task: {task_input.task}")
        logger.info(f"  Hints: {len(task_input.hints)}, Data fields: {len(task_input.data)}")
        
        steps_executed = 0
        
        try:
            # If we have hints and data, try to use them directly
            if task_input.hints and task_input.data:
                steps_executed = await self._execute_with_hints(task_input)
            else:
                # Fall back to LLM-based execution with hint context
                steps_executed = await self._execute_with_llm(task_input)
            
            return ModeResult(
                success=True,
                steps_executed=steps_executed,
            )
        except Exception as e:
            return ModeResult(
                success=False,
                steps_executed=steps_executed,
                error=str(e),
            )
    
    async def _execute_with_hints(self, task_input: GuidedTaskInput) -> int:
        """Execute using provided hints directly."""
        if not self._page:
            return 0
        
        steps = 0
        
        # For each data field, find matching hint and fill
        for field_name, value in task_input.data.items():
            hint = task_input.get_hint(field_name)
            if hint and hint.selector:
                # Wait for element
                await self._page.wait_for_selector(hint.selector, timeout=5000)
                
                # Fill or click based on element type
                element = await self._page.query_selector(hint.selector)
                if element:
                    tag = await element.get_attribute("tagName")
                    if tag and tag.lower() in ("input", "textarea"):
                        await self._page.fill(hint.selector, value)
                    else:
                        await self._page.click(hint.selector)
                    steps += 1
        
        # Handle submit hint if present
        submit_hint = task_input.get_hint("submit")
        if submit_hint and submit_hint.selector:
            await self._page.click(submit_hint.selector)
            steps += 1
        
        return steps
    
    async def _execute_with_llm(self, task_input: GuidedTaskInput) -> int:
        """Execute using LLM with hint context."""
        if not self._llm:
            raise RuntimeError("LLM provider required for this task")
        
        # TODO: Implement LLM-based execution with hints as context
        raise NotImplementedError("LLM-guided execution not yet implemented")
    
    def _parse_dict_input(self, data: Dict[str, Any]) -> GuidedTaskInput:
        """Parse dictionary input to GuidedTaskInput."""
        hints = [
            LocatorHint(
                name=h.get("name", ""),
                selector=h.get("selector"),
                xpath=h.get("xpath"),
                text=h.get("text"),
                role=h.get("role"),
                description=h.get("description", ""),
            )
            for h in data.get("hints", [])
        ]
        
        return GuidedTaskInput(
            task=data.get("task", ""),
            hints=hints,
            data=data.get("data", {}),
            options=data.get("options", {}),
        )
    
    async def stop(self) -> None:
        """Stop the mode."""
        self._is_running = False
        self._page = None
        logger.info("Guided mode stopped")
