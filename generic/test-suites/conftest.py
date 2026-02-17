"""
Shared pytest fixtures and configuration for Generic Agent tests.
"""
import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock


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
        "destinationEntityId": "agent.generic.test",
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
    event["message"]["text"]["data"] = "Find services in Bangalore"
    event["eventHint"] = "search_query"
    return event


@pytest.fixture
def booking_dostevent(base_dostevent) -> Dict[str, Any]:
    """dostEvent for booking queries"""
    event = base_dostevent.copy()
    event["message"]["text"]["data"] = "Book a salon service"
    event["eventHint"] = "booking_request"
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
        "sourceEntityId": "agent.generic.test",
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
# MOCK GENERIC AGENT FIXTURES
# ============================================================================

@pytest.fixture
def mock_domain_config():
    """Mock domain configuration"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    try:
        from app.config.domain_config import BaseDomainConfig
        
        config = BaseDomainConfig(
            domain_name="test_domain",
            entity_id="agent.generic.test",
            system_prompt="You are a test assistant",
            tools_module="app.domains.urban_company.tools",
            persistence_collection="test_collection"
        )
        return config
    except ImportError:
        pytest.skip("Generic app not available")


@pytest.fixture
def mock_generic_agent(mock_domain_config):
    """Mock GenericReActAgent"""
    from unittest.mock import MagicMock, AsyncMock
    
    agent = MagicMock()
    
    # Mock process_message to return expected structure
    async def mock_process_message(user_message, user_id, **kwargs):
        return {
            "response": "Mocked agent response",
            "state": {
                "selected_service_id": None,
                "booking_details": {},
                "details_shown": False
            }
        }
    
    agent.process_message = AsyncMock(side_effect=mock_process_message)
    agent.config = mock_domain_config
    
    return agent


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
