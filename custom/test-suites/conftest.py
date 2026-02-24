"""
Shared pytest fixtures and configuration for Custom Agent tests.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# ↑ Adds custom/ to sys.path → makes 'app' importable as custom/app/

import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio for all async tests"""
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for the test session"""
    return asyncio.get_event_loop_policy()


# ============================================================================
# DOSTEVENT FIXTURES (Universal)
# ============================================================================

@pytest.fixture
def base_dostevent() -> Dict[str, Any]:
    """Base dostEvent structure"""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.test123",
        "destinationEntityId": "agent.custom.test",
        "sessionId": "session-test-uuid-123",
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {
            "text": {
                "data": "test query"
            }
        }
    }


@pytest.fixture
def search_dostevent(base_dostevent) -> Dict[str, Any]:
    """dostEvent for search queries"""
    event = base_dostevent.copy()
    event["message"]["text"]["data"] = "Find me meals with chicken"
    event["eventHint"] = "search_query"
    return event


@pytest.fixture
def multi_turn_session() -> str:
    """Session ID for multi-turn conversation tests"""
    return "session-multi-turn-test-456"


# ============================================================================
# EXPECTED RESPONSE FIXTURES
# ============================================================================

@pytest.fixture
def expected_dostevent_response() -> Dict[str, Any]:
    """Expected dostEvent response structure"""
    return {
        "version": "00.01.01",
        "sourceEntityId": "agent.custom.test",
        "destinationEntityId": "hum.user.test123",
        "sessionId": "session-test-uuid-123",
        "isAiGenerated": True,
        "eventHint": "response",
        "message": {
            "text": {
                "data": "Sample response text"
            }
        }
    }


@pytest.fixture
def expected_metrics() -> Dict[str, Any]:
    """Expected DPA format metrics"""
    return {
        "models": {
            "gpt-4o-mini": {
                "input_tokens": 0,
                "output_tokens": 0
            }
        }
    }


# ============================================================================
# MOCK CUSTOM CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def mock_custom_client():
    """Mock CustomClient for testing"""
    from unittest.mock import AsyncMock, MagicMock
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    client = MagicMock()
    
    # Mock tools
    client.get_available_tools.return_value = [
        {
            "name": "search_meals",
            "description": "Search for meals",
            "parameters": {"type": "object"}
        }
    ]
    
    # Mock agent config
    client.get_agent_config.return_value = {
        "prompt_name": "default",
        "entity_id": "agent.custom.mealdb"
    }
    
    # Mock tool execution
    async def mock_execute_tool(tool_name, **kwargs):
        return {
            "meals": [
                {"id": "1", "name": "Chicken Curry", "category": "Chicken"}
            ]
        }
    
    client.execute_tool = AsyncMock(side_effect=mock_execute_tool)
    
    return client


@pytest.fixture
def mock_custom_settings(monkeypatch):
    """Mock settings for Custom tests"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    try:
        from app.config import Settings, AgentConfig, LLMConfig, CustomConfig
        
        mock_agent = AgentConfig(
            entity_id="agent.custom.test",
            name="Test Agent"
        )
        mock_llm = LLMConfig(
            enabled=False,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key",
            temperature=0.0
        )
        mock_custom = CustomConfig(
            config_path="configs/test.yaml",
            currency="INR"
        )
        
        # Patch the Settings properties
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "custom", PropertyMock(return_value=mock_custom))
        
        return Settings()
    except ImportError:
        pytest.skip("Custom app not available")


# ============================================================================
# MOCK LLM FIXTURES
# ============================================================================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing without API calls"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="Mocked response from agent",
                tool_calls=None
            )
        )
    ]
    mock_response.usage = MagicMock(
        prompt_tokens=100,
        completion_tokens=50
    )
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def dostevent_builder():
    """Builder pattern for creating test dostEvents"""
    class DostEventBuilder:
        def __init__(self):
            self.event = {
                "version": "00.01.01",
                "isAiGenerated": False,
                "eventHint": "user_message"
            }
        
        def with_message(self, text: str):
            self.event["message"] = {"text": {"data": text}}
            return self
        
        def with_source(self, entity_id: str):
            self.event["sourceEntityId"] = entity_id
            return self
        
        def with_destination(self, entity_id: str):
            self.event["destinationEntityId"] = entity_id
            return self
        
        def with_session(self, session_id: str):
            self.event["sessionId"] = session_id
            return self
        
        def with_hint(self, hint: str):
            self.event["eventHint"] = hint
            return self
        
        def build(self):
            return self.event.copy()
    
    return DostEventBuilder


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Cleanup after each test"""
    yield
    await asyncio.sleep(0.1)
