"""
LLM-related exceptions.
"""

from llm_web_agent.exceptions.base import LLMWebAgentError


class LLMError(LLMWebAgentError):
    """Base exception for LLM-related errors."""
    pass


class LLMConnectionError(LLMError):
    """
    Error connecting to the LLM provider.
    
    Raised when the connection to the LLM API fails.
    """
    pass


class LLMAuthenticationError(LLMError):
    """
    Authentication error with LLM provider.
    
    Raised when API key is invalid or missing.
    """
    pass


class RateLimitError(LLMError):
    """
    Rate limit exceeded.
    
    Raised when the LLM provider's rate limit is exceeded.
    
    Attributes:
        retry_after: Suggested wait time in seconds before retrying
    """
    
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after


class TokenLimitError(LLMError):
    """
    Token limit exceeded.
    
    Raised when the request exceeds the model's token limit.
    
    Attributes:
        token_count: Number of tokens in the request
        max_tokens: Maximum allowed tokens
    """
    
    def __init__(self, message: str, token_count: int | None = None, max_tokens: int | None = None):
        super().__init__(message, {"token_count": token_count, "max_tokens": max_tokens})
        self.token_count = token_count
        self.max_tokens = max_tokens


class InvalidResponseError(LLMError):
    """
    Invalid response from LLM.
    
    Raised when the LLM response cannot be parsed or is malformed.
    """
    
    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message, {"raw_response": raw_response[:500] if raw_response else None})
        self.raw_response = raw_response
