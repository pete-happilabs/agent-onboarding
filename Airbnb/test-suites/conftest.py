"""
Shared pytest fixtures for Airbnb agent tests.
"""
import sys
import os
import pytest
import asyncio
from typing import Dict, Any

# Add MCP template to path (Airbnb delegates to MCP)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MCP_DIR = os.path.join(os.path.dirname(_REPO_ROOT), "mcp")
sys.path.insert(0, _MCP_DIR)

# Set Airbnb env defaults BEFORE any imports that read them
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("MCP_CONFIG_PATH", os.path.join(_REPO_ROOT, "config.yaml"))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def airbnb_dostevent() -> Dict[str, Any]:
    """Standard Airbnb user dostEvent."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.traveler1",
        "destinationEntityId": "agent.mcp.airbnb",
        "sessionId": "airbnb-session-001",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": "Find apartments in Paris"
            }
        }
    }


@pytest.fixture
def empty_message_event() -> Dict[str, Any]:
    """dostEvent with empty message."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.traveler1",
        "destinationEntityId": "agent.mcp.airbnb",
        "sessionId": "airbnb-session-002",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": ""
            }
        }
    }


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    yield
    await asyncio.sleep(0.01)
