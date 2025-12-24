"""
Action Interface - Abstract base classes for browser actions.

This module defines the contract for browser actions that can be executed
by the agent. Each action type (click, type, navigate, etc.) implements
this interface.

Example:
    >>> from llm_web_agent.actions import ClickAction
    >>> action = ClickAction()
    >>> result = await action.execute(page, selector="#submit-button")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage


class ActionType(Enum):
    """Types of actions that can be executed on a browser page."""
    # Navigation actions
    NAVIGATE = "navigate"
    RELOAD = "reload"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    
    # Interaction actions
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    FILL = "fill"
    CLEAR = "clear"
    SELECT = "select"
    HOVER = "hover"
    SCROLL = "scroll"
    DRAG_AND_DROP = "drag_and_drop"
    PRESS_KEY = "press_key"
    
    # Extraction actions
    GET_TEXT = "get_text"
    GET_ATTRIBUTE = "get_attribute"
    GET_VALUE = "get_value"
    GET_HTML = "get_html"
    SCREENSHOT = "screenshot"
    
    # Waiting actions
    WAIT_FOR_ELEMENT = "wait_for_element"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    WAIT_FOR_LOAD = "wait_for_load"
    WAIT = "wait"
    
    # Frame actions
    SWITCH_TO_FRAME = "switch_to_frame"
    SWITCH_TO_MAIN = "switch_to_main"
    
    # Tab/Window actions
    NEW_TAB = "new_tab"
    CLOSE_TAB = "close_tab"
    SWITCH_TAB = "switch_tab"


class ActionStatus(Enum):
    """Status of an action execution."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ActionResult:
    """
    Result of an action execution.
    
    Attributes:
        success: Whether the action succeeded
        action_type: The type of action that was executed
        status: Detailed status of the action
        data: Optional data returned by the action (e.g., extracted text)
        error: Error message if the action failed
        error_type: Type of error (e.g., 'ElementNotFound', 'Timeout')
        duration_ms: Time taken to execute the action in milliseconds
        screenshot: Optional screenshot taken after the action
        metadata: Additional action-specific metadata
    """
    success: bool
    action_type: ActionType
    status: ActionStatus = ActionStatus.SUCCESS
    data: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: float = 0.0
    screenshot: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        action_type: ActionType,
        data: Optional[Any] = None,
        duration_ms: float = 0.0,
        **metadata: Any,
    ) -> "ActionResult":
        """Create a successful action result."""
        return cls(
            success=True,
            action_type=action_type,
            status=ActionStatus.SUCCESS,
            data=data,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    @classmethod
    def failure_result(
        cls,
        action_type: ActionType,
        error: str,
        error_type: str = "ActionError",
        duration_ms: float = 0.0,
        **metadata: Any,
    ) -> "ActionResult":
        """Create a failed action result."""
        return cls(
            success=False,
            action_type=action_type,
            status=ActionStatus.FAILED,
            error=error,
            error_type=error_type,
            duration_ms=duration_ms,
            metadata=metadata,
        )


@dataclass
class ActionParams:
    """
    Parameters for an action.
    
    This is a flexible container for action parameters that can be
    validated and passed to action implementations.
    
    Attributes:
        selector: CSS selector for the target element (if applicable)
        value: Value for the action (e.g., text to type, URL to navigate to)
        options: Additional action-specific options
    """
    selector: Optional[str] = None
    value: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an option value."""
        return self.options.get(key, default)


class IAction(ABC):
    """
    Abstract interface for browser actions.
    
    Actions are the atomic units of browser automation. Each action
    implements a specific interaction with the browser page.
    """

    @property
    @abstractmethod
    def action_type(self) -> ActionType:
        """
        Get the type of this action.
        
        Returns:
            The ActionType enum value
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Get a human-readable description of this action.
        
        Returns:
            Description string
        """
        ...

    @property
    @abstractmethod
    def requires_selector(self) -> bool:
        """
        Check if this action requires an element selector.
        
        Returns:
            True if a selector is required
        """
        ...

    @abstractmethod
    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        """
        Validate the parameters for this action.
        
        Args:
            params: The parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        ...

    @abstractmethod
    async def execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        """
        Execute this action on the given page.
        
        Args:
            page: The browser page to execute the action on
            params: The parameters for the action
            
        Returns:
            The result of the action execution
        """
        ...


class BaseAction(IAction):
    """
    Base implementation of IAction with common functionality.
    
    Subclasses should override action_type, description, and _execute.
    """

    @property
    def requires_selector(self) -> bool:
        """Most actions require a selector by default."""
        return True

    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        """Default validation checks for required selector."""
        if self.requires_selector and not params.selector:
            return False, f"{self.action_type.value} requires a selector"
        return True, None

    async def execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        """
        Execute the action with timing and error handling.
        
        Subclasses should override _execute instead of this method.
        """
        # Validate parameters
        is_valid, error_msg = self.validate_params(params)
        if not is_valid:
            return ActionResult.failure_result(
                action_type=self.action_type,
                error=error_msg or "Invalid parameters",
                error_type="ValidationError",
            )

        # Execute with timing
        start_time = time.perf_counter()
        try:
            result = await self._execute(page, params)
            result.duration_ms = (time.perf_counter() - start_time) * 1000
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ActionResult.failure_result(
                action_type=self.action_type,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
            )

    @abstractmethod
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        """
        Execute the action implementation.
        
        Subclasses must implement this method.
        """
        ...
