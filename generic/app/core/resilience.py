"""Resilience utilities: circuit breakers, retry logic, and timeouts.

Circuit Breaker states:
  CLOSED   → calls pass through. N consecutive failures → OPEN.
  OPEN     → calls raise CircuitBreakerOpen immediately.
             After recovery_timeout seconds → HALF_OPEN.
  HALF_OPEN → one probe call. Success → CLOSED. Failure → OPEN.
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum, auto
from typing import Any, Callable, Optional, Tuple, Type

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitState(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Circuit '{name}' is OPEN — service unavailable. Try again shortly."
        )
        self.circuit_name = name


class AsyncCircuitBreaker:
    """
    Async-safe circuit breaker for protecting external service calls.

    Args:
        name:               Human-readable identifier used in logs/exceptions.
        failure_threshold:  Consecutive failures before opening (default: 5).
        recovery_timeout:   Seconds before probing in HALF_OPEN (default: 30).
        expected_exception: Exception types that count as failures.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Current state — auto-transitions OPEN → HALF_OPEN after timeout."""
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info("Circuit '%s' → HALF_OPEN (probing)", self.name)
        return self._state

    def _on_success(self) -> None:
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit '%s' → CLOSED (recovered)", self.name)
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.warning(
                    "Circuit '%s' → OPEN after %d failures. Last: %s",
                    self.name, self._failure_count, exc,
                )
            self._state = CircuitState.OPEN
        else:
            logger.debug(
                "Circuit '%s' failure %d/%d: %s",
                self.name, self._failure_count, self.failure_threshold, exc,
            )

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute an async callable through the circuit breaker."""
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpen(self.name)
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as exc:
            self._on_failure(exc)
            raise


# =============================================================================
# Retry Decorators
# =============================================================================

def llm_retry(max_attempts: int = 3, min_wait: float = 1.0, max_wait: float = 8.0):
    """Retry decorator for async LLM API calls with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def sync_llm_retry(max_attempts: int = 3, min_wait: float = 1.0, max_wait: float = 8.0):
    """Retry decorator for synchronous LLM calls (e.g. LangChain invoke)."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# =============================================================================
# Timeout Wrapper
# =============================================================================

async def with_timeout(coro: Any, timeout: float, operation: str = "operation") -> Any:
    """
    Execute a coroutine with a hard timeout.

    Raises:
        TimeoutError: if the coroutine exceeds `timeout` seconds.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"{operation} timed out after {timeout:.1f}s")
