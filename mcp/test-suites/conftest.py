"""
Shared pytest fixtures and configuration for DOST agent tests.
This file is uniform across MCP, Generic, and Custom agents.
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
# DOSTEVENT FIXTURES (Universal across all agents)
# ============================================================================

@pytest.fixture
def base_dostevent() -> Dict[str, Any]:
    """Base dostEvent structure - uniform across all agents"""
    return {
        "version": "00.01.01",
        "sourceEntityId": "hum.user.test123",
        "destinationEntityId": "agent.test",
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
    event["message"]["text"]["data"] = "Find me restaurants in Bangalore"
    event["eventHint"] = "search_query"
    return event


@pytest.fixture
def booking_dostevent(base_dostevent) -> Dict[str, Any]:
    """dostEvent for booking queries"""
    event = base_dostevent.copy()
    event["message"]["text"]["data"] = "Book a table for 2 at 7 PM"
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
    """Expected dostEvent response structure - uniform validation"""
    return {
        "version": "00.01.01",
        "sourceEntityId": "agent.test",
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
    """Expected DPA format metrics - uniform across all agents"""
    return {
        "models": {
            "gpt-4o-mini": {
                "input_tokens": 0,
                "output_tokens": 0
            }
        }
    }


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
# RAGAS FIXTURES
# ============================================================================

@pytest.fixture
def ragas_evaluator_llm():
    """LLM for Ragas evaluation - can be mocked or real"""
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except ImportError:
        pytest.skip("langchain-openai not installed")


@pytest.fixture
def ragas_sample_interaction():
    """Sample multi-turn interaction for Ragas evaluation"""
    try:
        from ragas.messages import HumanMessage, AIMessage, ToolMessage, ToolCall
        
        return [
            HumanMessage(content="Find me restaurants in Bangalore"),
            AIMessage(
                content="Let me search for restaurants in Bangalore.",
                tool_calls=[
                    ToolCall(name="restaurant_search", args={"location": "Bangalore"})
                ]
            ),
            ToolMessage(content="Found 10 restaurants: 1. Biryani House, 2. South Indian Delight..."),
            AIMessage(content="I found 10 restaurants in Bangalore. Would you like details about any specific one?"),
        ]
    except ImportError:
        pytest.skip("ragas not installed")


# ============================================================================
# PERFORMANCE TEST FIXTURES
# ============================================================================

@pytest.fixture
def performance_thresholds():
    """Performance thresholds for latency and token usage tests"""
    return {
        "max_latency_seconds": 5.0,
        "max_tokens_per_request": 2000,
        "max_concurrent_requests": 10
    }


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
    # Allow pending tasks to complete
    await asyncio.sleep(0.1)


# ============================================================================
# MCP-SPECIFIC FIXTURES
# ============================================================================

@pytest.fixture
def mock_mcp_settings(monkeypatch):
    """Mock settings for MCP tests"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / ".." / "app"))
    
    try:
        from app.config import Settings, AgentConfig, LLMConfig, MCPConfig
        
        settings = Settings(
            agent=AgentConfig(entity_id="agent.mcp.test", name="Test Agent"),
            llm=LLMConfig(enabled=False, api_key="test-key", model="gpt-4o-mini"),
            mcp=MCPConfig(transport="stdio", command="test", timeout=30)
        )
        
        monkeypatch.setattr("app.config.get_settings", lambda *args: settings)
        return settings
    except ImportError:
        pytest.skip("MCP app not available")


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for testing"""
    from unittest.mock import AsyncMock, MagicMock
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / ".." / "app"))
    
    try:
        from app.client.mcp_client import MCPToolResult
        
        client = AsyncMock()
        client._connected = True
        
        # Mock tools
        tool1 = MagicMock()
        tool1.name = "search_restaurants"
        tool1.description = "Search for restaurants"
        tool1.input_schema = {"type": "object"}
        
        client.list_tools = AsyncMock(return_value=[tool1])
        client.send_message = AsyncMock(return_value="Mock response from MCP")
        client.call_tool = AsyncMock(return_value=MCPToolResult(
            content="Mock tool result",
            is_error=False
        ))
        
        return client
    except ImportError:
        pytest.skip("MCP app not available")
