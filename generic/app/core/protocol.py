"""Compatibility shim - delegates to shared.protocol."""
import sys as _sys, os as _os
_repo_root = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "../../.."))
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

from shared.protocol import (
    DOST_SPEC_VERSION,
    VALID_DURATION_TYPES,
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

__all__ = [
    "DOST_SPEC_VERSION", "VALID_DURATION_TYPES", "create_dost_event",
    "create_dost_message", "create_dost_categories", "create_dost_category",
    "create_dost_object", "create_dost_pricing", "create_dost_action",
    "create_dost_location", "create_dost_data", "create_response_event",
    "extract_query_text", "extract_objects_from_categories", "validate_dost_event",
]
