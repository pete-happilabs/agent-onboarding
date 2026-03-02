# ============================================================================
# FILE: app/core/__init__.py
# ============================================================================
"""
Core module — re-exports from shared package.
protocol.py and resilience.py have moved to shared/ at the repo root.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "../../..")))

from shared.protocol import (
    DOST_SPEC_VERSION,
    create_dost_event,
    create_dost_message,
    create_dost_categories,
    create_dost_category,
    create_dost_object,
    create_dost_pricing,
    create_dost_action,
    create_dost_location,
    create_dost_data,
    create_response_event,
    extract_query_text,
    extract_objects_from_categories,
    validate_dost_event,
)
from shared.shared_breaker import (
    CircuitState,
    CircuitBreakerOpen,
    AsyncCircuitBreaker,
    SharedAsyncCircuitBreaker,
    with_timeout,
    llm_retry,
    sync_llm_retry,
)
from .metrics import TalkMetrics

__all__ = [
    "DOST_SPEC_VERSION",
    "create_dost_event",
    "create_dost_message",
    "create_dost_categories",
    "create_dost_category",
    "create_dost_object",
    "create_dost_pricing",
    "create_dost_action",
    "create_dost_location",
    "create_dost_data",
    "create_response_event",
    "extract_query_text",
    "extract_objects_from_categories",
    "validate_dost_event",
    "CircuitState",
    "CircuitBreakerOpen",
    "AsyncCircuitBreaker",
    "SharedAsyncCircuitBreaker",
    "with_timeout",
    "llm_retry",
    "sync_llm_retry",
    "TalkMetrics",
]
