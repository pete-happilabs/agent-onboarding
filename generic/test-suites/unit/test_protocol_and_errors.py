"""
Unit tests for protocol error handling - Generic agent
Tests error cases in real protocol.py
"""
import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add generic root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.protocol import (
    create_dost_event,
    create_dost_message,
    create_dost_object,
    create_dost_pricing,
    create_dost_location,
    extract_query_text,
    DOST_SPEC_VERSION,
    VALID_DURATION_TYPES,
)
