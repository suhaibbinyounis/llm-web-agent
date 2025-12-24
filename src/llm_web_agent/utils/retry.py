"""
Retry utilities with exponential backoff.
"""

import asyncio
import functools
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum number of attempts
        initial_delay_ms: Initial delay before first retry
        max_delay_ms: Maximum delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        retry_on: Exception types to retry on
        on_retry: Callback function called on each retry
    """
    max_attempts: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception], None]] = None


def retry(
    max_attempts: int = 3,
    initial_delay_ms: int = 1000,
    max_delay_ms: int = 30000,
    backoff_multiplier: float = 2.0,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay_ms: Initial delay before first retry
        max_delay_ms: Maximum delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        retry_on: Exception types to retry on
        
    Returns:
        Decorator function
        
    Example:
        >>> @retry(max_attempts=3, retry_on=(TimeoutError,))
        ... async def fetch_data():
        ...     ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay_ms=initial_delay_ms,
        max_delay_ms=max_delay_ms,
        backoff_multiplier=backoff_multiplier,
        retry_on=retry_on,
    )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_async(func, config, *args, **kwargs)
        return wrapper
    
    return decorator


async def retry_async(
    func: Callable[..., T],
    config: RetryConfig,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Execute a function with retry logic.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        The last exception if all retries fail
    """
    last_exception: Optional[Exception] = None
    delay_ms = config.initial_delay_ms
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except config.retry_on as e:
            last_exception = e
            
            if attempt == config.max_attempts - 1:
                # Last attempt, don't retry
                break
            
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay_ms}ms..."
            )
            
            if config.on_retry:
                config.on_retry(attempt + 1, e)
            
            await asyncio.sleep(delay_ms / 1000)
            
            # Exponential backoff
            delay_ms = min(
                delay_ms * config.backoff_multiplier,
                config.max_delay_ms,
            )
    
    raise last_exception  # type: ignore


async def with_timeout(
    coro: Any,
    timeout_seconds: float,
    error_message: str = "Operation timed out",
) -> Any:
    """
    Execute a coroutine with a timeout.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        error_message: Message for timeout error
        
    Returns:
        Coroutine result
        
    Raises:
        asyncio.TimeoutError if timeout is exceeded
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(error_message)
