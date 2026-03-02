"""Compatibility shim - delegates to shared.shared_breaker."""
import sys as _sys, os as _os
_repo_root = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "../../.."))
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

from shared.shared_breaker import (
    CircuitState,
    CircuitBreakerOpen,
    AsyncCircuitBreaker,
    SharedAsyncCircuitBreaker,
    with_timeout,
    llm_retry,
    sync_llm_retry,
)

__all__ = [
    "CircuitState", "CircuitBreakerOpen", "AsyncCircuitBreaker",
    "SharedAsyncCircuitBreaker", "with_timeout", "llm_retry", "sync_llm_retry",
]
