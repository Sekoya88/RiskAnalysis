"""
Retry utilities — Exponential backoff with jitter for API rate limits.

Handles Gemini free-tier quota constraints by implementing intelligent
retry strategies with configurable delays.
"""

from __future__ import annotations

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimitError(Exception):
    """Raised when API rate limit is hit."""
    pass


async def retry_with_backoff(
    func: Callable,
    *args: Any,
    max_retries: int = 5,
    base_delay: float = 15.0,
    max_delay: float = 120.0,
    jitter: bool = True,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff retry on rate limit errors.

    Args:
        func: Async callable to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay cap in seconds.
        jitter: Add random jitter to prevent thundering herd.

    Returns:
        The result of the successful function call.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(
                keyword in error_str
                for keyword in ["429", "resource_exhausted", "rate limit", "quota"]
            )

            if not is_rate_limit or attempt >= max_retries:
                raise

            last_exception = e
            delay = min(base_delay * (2 ** attempt), max_delay)
            if jitter:
                delay += random.uniform(0, delay * 0.3)

            logger.warning(
                f"Rate limit hit (attempt {attempt + 1}/{max_retries + 1}). "
                f"Retrying in {delay:.1f}s..."
            )
            print(
                f"   ⏳ Rate limit hit — retrying in {delay:.1f}s "
                f"(attempt {attempt + 1}/{max_retries + 1})"
            )
            await asyncio.sleep(delay)

    raise last_exception  # type: ignore[misc]
