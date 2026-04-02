"""
Shared pytest fixtures for Uber agent tests.
"""
import sys
import os
import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Add generic template to path (Uber delegates to generic)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GENERIC_DIR = os.path.join(os.path.dirname(_REPO_ROOT), "generic")
sys.path.insert(0, _GENERIC_DIR)

# Set Uber env defaults BEFORE any imports that read them
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("DOMAIN_CONFIG", "uber")
os.environ.setdefault("AGENT_ENTITY_ID", "com.uber.rides")
os.environ.setdefault("AGENT_NAME", "UberBot")
os.environ.setdefault("CURRENCY", "INR")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def uber_dostevent() -> Dict[str, Any]:
    """Standard Uber user dostEvent."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.rider1",
        "destinationEntityId": "com.uber.rides",
        "sessionId": "uber-session-001",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": "What rides are available?"
            }
        }
    }


@pytest.fixture
def empty_message_event() -> Dict[str, Any]:
    """dostEvent with empty message."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.rider1",
        "destinationEntityId": "com.uber.rides",
        "sessionId": "uber-session-002",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": ""
            }
        }
    }


@pytest.fixture
def no_message_event() -> Dict[str, Any]:
    """dostEvent with no message field."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.rider1",
        "destinationEntityId": "com.uber.rides",
        "sessionId": "uber-session-003",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {}
    }


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    yield
    await asyncio.sleep(0.01)
