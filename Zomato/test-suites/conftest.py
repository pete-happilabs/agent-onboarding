"""
Shared pytest fixtures for Zomato agent tests.
"""
import sys
import os
import pytest
import asyncio
from typing import Dict, Any

# Add custom template to path (Zomato delegates to custom)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CUSTOM_DIR = os.path.join(os.path.dirname(_REPO_ROOT), "custom")
sys.path.insert(0, _CUSTOM_DIR)

# Set Zomato env defaults BEFORE any imports that read them
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("CUSTOM_CONFIG_PATH", os.path.join(_REPO_ROOT, "config.yaml"))
os.environ.setdefault("AGENT_ENTITY_ID", "agent.custom.zomato")
os.environ.setdefault("AGENT_NAME", "Zomato Food Assistant")
os.environ.setdefault("CUSTOM_CURRENCY", "INR")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def zomato_dostevent() -> Dict[str, Any]:
    """Standard Zomato user dostEvent."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.foodie1",
        "destinationEntityId": "agent.custom.zomato",
        "sessionId": "zomato-session-001",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": "Show me some pasta recipes"
            }
        }
    }


@pytest.fixture
def empty_message_event() -> Dict[str, Any]:
    """dostEvent with empty message."""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.foodie1",
        "destinationEntityId": "agent.custom.zomato",
        "sessionId": "zomato-session-002",
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
