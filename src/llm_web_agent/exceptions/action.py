"""
Action-related exceptions.
"""

from llm_web_agent.exceptions.base import LLMWebAgentError


class ActionError(LLMWebAgentError):
    """Base exception for action-related errors."""
    pass


class ActionValidationError(ActionError):
    """
    Action parameters are invalid.
    
    Raised when action parameters fail validation.
    """
    
    def __init__(self, message: str, action_type: str, invalid_params: dict | None = None):
        super().__init__(message, {"action_type": action_type, "invalid_params": invalid_params})
        self.action_type = action_type
        self.invalid_params = invalid_params


class ActionExecutionError(ActionError):
    """
    Error during action execution.
    
    Raised when an action fails to execute properly.
    """
    
    def __init__(self, message: str, action_type: str, selector: str | None = None):
        super().__init__(message, {"action_type": action_type, "selector": selector})
        self.action_type = action_type
        self.selector = selector


class ActionTimeoutError(ActionError):
    """
    Action timed out.
    
    Raised when an action exceeds its timeout.
    """
    
    def __init__(self, message: str, action_type: str, timeout_ms: int):
        super().__init__(message, {"action_type": action_type, "timeout_ms": timeout_ms})
        self.action_type = action_type
        self.timeout_ms = timeout_ms
