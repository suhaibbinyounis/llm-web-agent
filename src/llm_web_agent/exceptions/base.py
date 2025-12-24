"""
Base exceptions for LLM Web Agent.
"""


class LLMWebAgentError(Exception):
    """
    Base exception for all LLM Web Agent errors.
    
    All custom exceptions inherit from this class, making it easy
    to catch any error from the library.
    
    Attributes:
        message: Human-readable error message
        details: Optional additional error details
    """
    
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConfigurationError(LLMWebAgentError):
    """
    Error in configuration.
    
    Raised when there's an issue with settings, environment variables,
    or configuration files.
    """
    pass


class InitializationError(LLMWebAgentError):
    """
    Error during initialization.
    
    Raised when a component fails to initialize properly.
    """
    pass
