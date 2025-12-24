"""
Base Mode - Abstract interface for interaction modes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider


class ModeType(Enum):
    """Types of interaction modes."""
    NATURAL_LANGUAGE = "natural_language"
    RECORD_REPLAY = "record_replay"
    GUIDED = "guided"


@dataclass
class ModeConfig:
    """
    Configuration for an interaction mode.
    
    Attributes:
        mode_type: Type of mode
        options: Mode-specific options
    """
    mode_type: ModeType
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModeResult:
    """
    Result from running a mode.
    
    Attributes:
        success: Whether the task completed successfully
        steps_executed: Number of steps executed
        data: Any extracted or returned data
        error: Error message if failed
        recording: For record mode, the recorded actions
    """
    success: bool
    steps_executed: int = 0
    data: Optional[Any] = None
    error: Optional[str] = None
    recording: Optional["Recording"] = None


@dataclass
class Recording:
    """
    A recorded sequence of user actions.
    
    Attributes:
        name: Recording name
        actions: List of recorded actions
        metadata: Recording metadata
    """
    name: str
    actions: List["RecordedAction"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Recording":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            actions=[RecordedAction.from_dict(a) for a in data["actions"]],
            metadata=data.get("metadata", {}),
        )


@dataclass
class RecordedAction:
    """
    A single recorded user action.
    
    Attributes:
        action_type: Type of action (click, type, navigate, etc.)
        selector: CSS selector of target element
        value: Value for the action (text typed, URL navigated, etc.)
        timestamp_ms: When the action occurred
        element_info: Information about the target element
        screenshot: Optional screenshot before/after action
    """
    action_type: str
    selector: Optional[str] = None
    value: Optional[str] = None
    timestamp_ms: int = 0
    element_info: Dict[str, Any] = field(default_factory=dict)
    screenshot: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type,
            "selector": self.selector,
            "value": self.value,
            "timestamp_ms": self.timestamp_ms,
            "element_info": self.element_info,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordedAction":
        """Create from dictionary."""
        return cls(
            action_type=data["action_type"],
            selector=data.get("selector"),
            value=data.get("value"),
            timestamp_ms=data.get("timestamp_ms", 0),
            element_info=data.get("element_info", {}),
        )


class IInteractionMode(ABC):
    """
    Abstract interface for interaction modes.
    
    Each mode represents a different way of using the agent.
    """
    
    @property
    @abstractmethod
    def mode_type(self) -> ModeType:
        """The type of this mode."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the mode."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of how this mode works."""
        ...
    
    @abstractmethod
    async def start(
        self,
        page: "IPage",
        config: ModeConfig,
        **kwargs: Any,
    ) -> None:
        """
        Start the mode.
        
        Args:
            page: Browser page to operate on
            config: Mode configuration
            **kwargs: Additional mode-specific arguments
        """
        ...
    
    @abstractmethod
    async def execute(self, input_data: Any) -> ModeResult:
        """
        Execute the mode with given input.
        
        Args:
            input_data: Mode-specific input (task text, recording, hints)
            
        Returns:
            Result of execution
        """
        ...
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the mode and cleanup."""
        ...
