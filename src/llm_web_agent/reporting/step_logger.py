"""
Step Logger - Detailed step-by-step logging for runs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import json

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log level for step entries."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class StepLog:
    """
    A single log entry for a step.
    
    Attributes:
        timestamp: When the log was created
        level: Log level
        step_number: Associated step number
        action: Action being performed
        message: Log message
        data: Additional data
        screenshot: Path to screenshot if captured
    """
    timestamp: datetime
    level: LogLevel
    step_number: int
    action: str
    message: str
    data: Optional[Dict[str, Any]] = None
    screenshot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "step_number": self.step_number,
            "action": self.action,
            "message": self.message,
            "data": self.data,
            "screenshot": self.screenshot,
        }


class StepLogger:
    """
    Logger for detailed step-by-step execution logging.
    
    Example:
        >>> step_logger = StepLogger(run_id="run_123")
        >>> step_logger.log_step_start(1, "click", "Clicking login button")
        >>> step_logger.log_step_complete(1, success=True)
        >>> logs = step_logger.get_logs()
    """
    
    def __init__(self, run_id: str):
        """
        Initialize the step logger.
        
        Args:
            run_id: Unique identifier for the run
        """
        self.run_id = run_id
        self._logs: List[StepLog] = []
        self._current_step = 0
    
    def log(
        self,
        level: LogLevel,
        step_number: int,
        action: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        screenshot: Optional[str] = None,
    ) -> None:
        """
        Add a log entry.
        
        Args:
            level: Log level
            step_number: Step number
            action: Action being performed
            message: Log message
            data: Additional data
            screenshot: Path to screenshot
        """
        entry = StepLog(
            timestamp=datetime.now(),
            level=level,
            step_number=step_number,
            action=action,
            message=message,
            data=data,
            screenshot=screenshot,
        )
        self._logs.append(entry)
        
        # Also log to standard logger
        log_method = getattr(logger, level.value)
        log_method(f"[Step {step_number}] {action}: {message}")
    
    def log_step_start(self, step_number: int, action: str, description: str) -> None:
        """Log the start of a step."""
        self._current_step = step_number
        self.log(LogLevel.INFO, step_number, action, f"Starting: {description}")
    
    def log_step_complete(
        self,
        step_number: int,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log the completion of a step."""
        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "completed successfully" if success else "failed"
        self.log(level, step_number, "complete", f"Step {status}", data=data)
    
    def log_error(self, step_number: int, action: str, error: str) -> None:
        """Log an error."""
        self.log(LogLevel.ERROR, step_number, action, f"Error: {error}")
    
    def log_warning(self, step_number: int, action: str, message: str) -> None:
        """Log a warning."""
        self.log(LogLevel.WARNING, step_number, action, message)
    
    def get_logs(self) -> List[StepLog]:
        """Get all log entries."""
        return self._logs.copy()
    
    def export_json(self, path: str) -> None:
        """Export logs to JSON file."""
        with open(path, "w") as f:
            json.dump([log.to_dict() for log in self._logs], f, indent=2)
