"""
Shared resilience utilities for all agents.

Includes:
- CircuitBreakerOpen        — exception raised when circuit is OPEN
- AsyncCircuitBreaker       — in-process circuit breaker (no Redis)
- SharedAsyncCircuitBreaker — circuit breaker with optional Redis backend
- with_timeout()            — hard async timeout wrapper
- llm_retry()               — retry decorator for async LLM calls
- sync_llm_retry()          — retry decorator for sync LLM calls (LangChain)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
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

_REDIS_URL = os.environ.get("REDIS_URL")


# =============================================================================
# Circuit State
# =============================================================================

class CircuitState(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


# =============================================================================
# Exception
# =============================================================================

class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Circuit '{name}' is OPEN — service unavailable. Try again shortly."
        )
        self.circuit_name = name


# =============================================================================
# In-process Circuit Breaker (no Redis)
# =============================================================================

class AsyncCircuitBreaker:
    """
    Async-safe in-process circuit breaker.
    Use this when you don't need cross-worker state sharing.

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
# Shared Circuit Breaker (Redis-backed with in-process fallback)
# =============================================================================

class SharedAsyncCircuitBreaker:
    """
    Circuit breaker that syncs state via Redis when available.
    Falls back to in-process state when Redis is not configured.

    In-process mode: same behavior as AsyncCircuitBreaker.
    Redis mode: state is shared across all workers and survives restarts.
    Set REDIS_URL env var to enable Redis mode.
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
        self._redis: Any = None
        self._redis_initialized = False
        self._local_state = CircuitState.CLOSED
        self._local_failure_count = 0
        self._local_last_failure_time: Optional[float] = None

    async def _get_redis(self) -> Optional[Any]:
        if self._redis_initialized:
            return self._redis
        self._redis_initialized = True
        if not _REDIS_URL:
            return None
        try:
            import aioredis
            self._redis = await aioredis.from_url(_REDIS_URL, decode_responses=True)
            logger.info("Circuit breaker '%s' using Redis backend: %s", self.name, _REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Redis unavailable for circuit breaker '%s': %s — using in-process fallback",
                self.name, exc,
            )
            self._redis = None
        return self._redis

    async def _get_state(self) -> Tuple[CircuitState, int, Optional[float]]:
        redis = await self._get_redis()
        if redis is None:
            return self._local_state, self._local_failure_count, self._local_last_failure_time
        try:
            raw = await redis.get(f"cb:{self.name}")
            if not raw:
                return CircuitState.CLOSED, 0, None
            data = json.loads(raw)
            return CircuitState(data["state"]), data["failures"], data.get("last_failure")
        except Exception as exc:
            logger.warning("Redis read failed for circuit '%s': %s", self.name, exc)
            return self._local_state, self._local_failure_count, self._local_last_failure_time

    async def _set_state(self, state: CircuitState, failures: int, last_failure: Optional[float]) -> None:
        self._local_state = state
        self._local_failure_count = failures
        self._local_last_failure_time = last_failure
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.set(
                f"cb:{self.name}",
                json.dumps({"state": state.value, "failures": failures, "last_failure": last_failure}),
                ex=int(self.recovery_timeout * 10),
            )
        except Exception as exc:
            logger.warning("Redis write failed for circuit '%s': %s", self.name, exc)

    async def get_state(self) -> CircuitState:
        state, failures, last_failure = await self._get_state()
        if (
            state == CircuitState.OPEN
            and last_failure is not None
            and time.monotonic() - last_failure >= self.recovery_timeout
        ):
            await self._set_state(CircuitState.HALF_OPEN, failures, last_failure)
            logger.info("Circuit '%s' → HALF_OPEN (probing)", self.name)
            return CircuitState.HALF_OPEN
        return state

    async def _on_success(self) -> None:
        state, _, _ = await self._get_state()
        if state != CircuitState.CLOSED:
            logger.info("Circuit '%s' → CLOSED (recovered)", self.name)
        await self._set_state(CircuitState.CLOSED, 0, None)

    async def _on_failure(self, exc: Exception) -> None:
        state, failures, _ = await self._get_state()
        failures += 1
        last_failure = time.monotonic()
        if failures >= self.failure_threshold:
            if state != CircuitState.OPEN:
                logger.warning(
                    "Circuit '%s' → OPEN after %d failures. Last: %s",
                    self.name, failures, exc,
                )
            await self._set_state(CircuitState.OPEN, failures, last_failure)
        else:
            logger.debug(
                "Circuit '%s' failure %d/%d: %s",
                self.name, failures, self.failure_threshold, exc,
            )
            await self._set_state(state, failures, last_failure)

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        current_state = await self.get_state()
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpen(self.name)
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure(e)
            raise


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
