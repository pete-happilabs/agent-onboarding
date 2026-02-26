"""
Shared circuit breaker with optional Redis backend.

Falls back to in-process state when Redis is unavailable.
In multi-worker deployments, set REDIS_URL env var to share state.
"""
from __future__ import annotations

import json
import logging
import os
import time
from enum import Enum, auto
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL")


class CircuitState(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


class CircuitBreakerOpen(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Circuit '{name}' is OPEN — service unavailable. Try again shortly.")
        self.circuit_name = name


class SharedAsyncCircuitBreaker:
    """
    Circuit breaker that syncs state via Redis when available.
    Falls back to in-process state when Redis is not configured.

    In-process mode: same behavior as AsyncCircuitBreaker.
    Redis mode: state is shared across all workers and survives restarts.
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
        # In-process fallback state
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
            logger.warning("Redis unavailable for circuit breaker '%s': %s — using in-process fallback", self.name, exc)
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
                logger.warning("Circuit '%s' → OPEN after %d failures. Last: %s", self.name, failures, exc)
            await self._set_state(CircuitState.OPEN, failures, last_failure)
        else:
            logger.debug("Circuit '%s' failure %d/%d: %s", self.name, failures, self.failure_threshold, exc)
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

