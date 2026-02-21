"""
Integration tests for GenericReActAgent - Generic Agent
"""
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.generic_agent import GenericReActAgent
from app.core.protocol import DOST_SPEC_VERSION
from langchain_core.messages import AIMessage


def _make_mock_llm(response_text: str = "Mocked response", raise_error: Exception = None):
    """Helper: build a mock LLM that returns an AIMessage"""
    mock_llm = MagicMock()

    if raise_error:
        mock_llm.invoke = MagicMock(side_effect=raise_error)
    else:
        # LangGraph's tools_condition needs a real AIMessage with tool_calls=[]
        ai_response = AIMessage(content=response_text, tool_calls=[])
        mock_llm.invoke = MagicMock(return_value=ai_response)

    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    return mock_llm


@pytest.mark.integration
@pytest.mark.asyncio
class TestGenericReActAgent:

    async def test_process_message_valid_input(self, mock_domain_config, monkeypatch):
        """Test process_message with valid user input - happy path"""
        mock_llm = _make_mock_llm("Here are 3 services available in your area")
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)

        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda name: mock_tools_module)

        agent = GenericReActAgent(config=mock_domain_config)
        result = await agent.process_message(
            user_message="Find services near me",
            user_id="user123"
        )

        assert "response" in result
        assert "state" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0
        assert result["response"] == "Here are 3 services available in your area"

        print(f"\n✓ process_message returned valid response")

    async def test_process_message_with_metadata(self, mock_domain_config, monkeypatch):
        """Test process_message with metadata (location, category filters)"""
        mock_llm = _make_mock_llm("Found services in Bangalore")
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)

        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda name: mock_tools_module)

        agent = GenericReActAgent(config=mock_domain_config)
        result = await agent.process_message(
            user_message="Find services",
            user_id="user123",
            metadata={
                "category": "salon",
                "location": {
                    "city": "Bangalore",
                    "coordinates": {"lat": 12.9716, "lng": 77.5946}
                }
            }
        )

        assert "response" in result
        assert result["response"] == "Found services in Bangalore"

        print(f"\n✓ process_message handled metadata correctly")

    async def test_process_message_maintains_conversation_history(self, mock_domain_config, monkeypatch):
        """Test that agent maintains conversation history per user"""
        mock_llm = _make_mock_llm("Response")
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)

        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda name: mock_tools_module)

        agent = GenericReActAgent(config=mock_domain_config)
        user_id = "user123"

        await agent.process_message("Hello", user_id)
        assert user_id in agent.conversation_history
        first_count = len(agent.conversation_history[user_id])
        assert first_count > 0

        await agent.process_message("Find services", user_id)
        assert len(agent.conversation_history[user_id]) > first_count

        print(f"\n✓ Conversation history maintained correctly")

    async def test_process_message_error_handling(self, mock_domain_config, monkeypatch):
        """Test that agent handles LLM errors gracefully"""
        mock_llm = _make_mock_llm(raise_error=Exception("LLM API error"))
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)

        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda name: mock_tools_module)

        agent = GenericReActAgent(config=mock_domain_config)
        result = await agent.process_message("Find services", "user123")

        assert "response" in result
        assert (
            "error" in result["response"].lower()
            or "couldn't" in result["response"].lower()
        )
        assert "state" in result

        print(f"\n✓ Agent handled LLM error gracefully")
