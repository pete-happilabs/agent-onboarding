"""
Integration tests for GenericReActAgent - Generic Agent
Tests the real GenericReActAgent.process_message() implementation
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

# Real imports from your code
import sys
from pathlib import Path

# Add generic root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.generic_agent import GenericReActAgent
from app.config.domain_config import BaseDomainConfig
from app.core.protocol import extract_query_text, DOST_SPEC_VERSION


@pytest.mark.integration
@pytest.mark.asyncio
class TestGenericReActAgent:
    """Integration tests for GenericReActAgent"""
    
    async def test_process_message_valid_input(self, mock_domain_config, monkeypatch):
        """Test process_message with valid user input"""
        # Mock LLM
        mock_llm_response = MagicMock()
        mock_llm_response.content = "Here are 3 services available in your area"
        mock_llm_response.tool_calls = None
        
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value=mock_llm_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        
        # Mock ChatOpenAI
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)
        
        # Mock tools module
        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda module_name: mock_tools_module)
        
        # Create agent
        agent = GenericReActAgent(config=mock_domain_config)
        
        # Process message
        result = await agent.process_message(
            user_message="Find services near me",
            user_id="user123"
        )
        
        # Validate response structure
        assert "response" in result
        assert "state" in result
        assert isinstance(result["response"], str)
        assert isinstance(result["state"], dict)
        assert len(result["response"]) > 0
        
        print(f"\n✓ process_message returned valid response structure")
    
    async def test_process_message_with_metadata(self, mock_domain_config, monkeypatch):
        """Test process_message with metadata (location, category filters)"""
        # Mock LLM
        mock_llm_response = MagicMock()
        mock_llm_response.content = "Found services in Bangalore"
        mock_llm_response.tool_calls = None
        
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value=mock_llm_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)
        
        # Mock tools
        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda module_name: mock_tools_module)
        
        # Create agent
        agent = GenericReActAgent(config=mock_domain_config)
        
        # Process with metadata
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
        # Mock LLM
        mock_llm_response = MagicMock()
        mock_llm_response.content = "Response 1"
        mock_llm_response.tool_calls = None
        
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value=mock_llm_response)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)
        
        # Mock tools
        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda module_name: mock_tools_module)
        
        # Create agent
        agent = GenericReActAgent(config=mock_domain_config)
        
        user_id = "user123"
        
        # First message
        await agent.process_message("Hello", user_id)
        assert user_id in agent.conversation_history
        assert len(agent.conversation_history[user_id]) > 0
        
        # Second message
        await agent.process_message("Find services", user_id)
        assert len(agent.conversation_history[user_id]) > 1
        
        print(f"\n✓ Conversation history maintained correctly")
    
    async def test_process_message_error_handling(self, mock_domain_config, monkeypatch):
        """Test that agent handles LLM errors gracefully"""
        # Mock LLM that raises error
        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(side_effect=Exception("LLM API error"))
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        
        monkeypatch.setattr("app.core.generic_agent.ChatOpenAI", lambda **kwargs: mock_llm)
        
        # Mock tools
        mock_tools_module = MagicMock()
        mock_tools_module.TOOLS = []
        monkeypatch.setattr("importlib.import_module", lambda module_name: mock_tools_module)
        
        # Create agent
        agent = GenericReActAgent(config=mock_domain_config)
        
        # Process message (should not raise, should return error message)
        result = await agent.process_message("Find services", "user123")
        
        assert "response" in result
        assert "error" in result["response"].lower() or "couldn't" in result["response"].lower()
        assert "state" in result
        
        print(f"\n✓ Agent handled error gracefully")
