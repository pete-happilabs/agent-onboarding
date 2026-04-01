# ============================================================================
# FILE: app/core/__init__.py
# ============================================================================
"""
Core module - re-exports from shared dost package for backwards compatibility.
"""

from dost.protocol import (
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
)
from dost.metrics import TalkMetrics

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
    "TalkMetrics",
]
