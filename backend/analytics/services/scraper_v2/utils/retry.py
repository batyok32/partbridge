"""Retry decorator with exponential backoff."""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, Set, Type

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 6.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Set[Type[Exception]]] = None,
):
    """
    Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Set of exception types to retry on (None = all)

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = initial_delay

            while True:
                attempt += 1
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    # Check if we should retry this exception
                    if retryable_exceptions and not isinstance(exc, tuple(retryable_exceptions)):
                        raise

                    # Check if we've exhausted retries
                    if attempt >= max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {exc}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    sleep_time = min(delay, max_delay)

                    # Add jitter if enabled
                    if jitter:
                        jitter_amount = random.uniform(0, sleep_time * 0.25)
                        sleep_time += jitter_amount

                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {exc}. "
                        f"Retrying in {sleep_time:.2f}s..."
                    )

                    await asyncio.sleep(sleep_time)

                    # Increase delay for next attempt
                    delay *= exponential_base

        return wrapper

    return decorator


def should_retry_http_error(exc: Exception) -> bool:
    """
    Determine if an HTTP error should be retried.

    Args:
        exc: Exception to check

    Returns:
        True if the error should be retried
    """
    # Check for status code
    response = getattr(exc, "response", None)
    if response is None:
        return True  # Network errors should be retried

    status_code = getattr(response, "status_code", None)
    if status_code is None:
        return True

    # Server errors should be retried
    if status_code in {500, 502, 503, 504, 522, 524, 529}:
        return True

    # Other retryable statuses
    if status_code in {408, 409, 425, 429}:
        return True

    # Check for retry header
    headers = getattr(response, "headers", {})
    if isinstance(headers, dict):
        if headers.get("x-should-retry") == "true":
            return True

    return False
