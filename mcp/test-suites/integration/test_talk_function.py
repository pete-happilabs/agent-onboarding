"""
Integration tests for talk() function - MCP Agent
Tests the real talk() implementation with mocked MCP client
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

# Real imports from your code
import sys
from pathlib import Path

# Add mcp root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.engine.talk import talk
from app.core.protocol import extract_query_text, DOST_SPEC_VERSION


@pytest.mark.integration
@pytest.mark.asyncio
class TestTalkFunctionMCP:
    """Integration tests for talk() - real implementation"""
    
    async def test_talk_with_valid_dostevent(self, base_dostevent, monkeypatch):
        """Test talk() with a valid dostEvent - happy path"""
        # Mock the MCP client to avoid real connections
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.send_message = AsyncMock(return_value="Found 5 restaurants in Bangalore")
        
        async def mock_init_client():
            return mock_client
        
        monkeypatch.setattr("app.engine.talk.initialize_mcp_client", mock_init_client)
        
        # Mock settings by creating config objects and patching properties
        from app.config import Settings, AgentConfig, LLMConfig, MCPConfig
        
        mock_agent = AgentConfig(entity_id="agent.mcp.test", name="Test Agent")
        mock_llm = LLMConfig(
            enabled=False,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key"
        )
        mock_mcp = MCPConfig(
            transport="stdio",
            command="test",
            url="http://localhost:3000",
            timeout=30
        )
        
        # Patch the Settings properties
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "mcp", PropertyMock(return_value=mock_mcp))
        
        # Call real talk()
        response, metrics = await talk(base_dostevent)
        
        # Validate response structure
        assert response["version"] == DOST_SPEC_VERSION
        assert response["sourceEntityId"] == "agent.mcp.test"
        assert response["destinationEntityId"] == base_dostevent["sourceEntityId"]
        assert response["sessionId"] == base_dostevent["sessionId"]
        assert response["isAiGenerated"] is True
        assert "message" in response
        assert response["message"]["text"]["data"] == "Found 5 restaurants in Bangalore"
        
        # Validate metrics structure (DPA format)
        assert "models" in metrics
        assert isinstance(metrics["models"], dict)
        
        print(f"\n✓ talk() returned valid dostEvent response")
    
    async def test_talk_with_empty_message(self, base_dostevent, monkeypatch):
        """Test talk() handles empty message gracefully"""
        # Remove message
        base_dostevent["message"] = {"text": {"data": ""}}
        
        # Mock settings
        from app.config import Settings, AgentConfig, LLMConfig, MCPConfig
        
        mock_agent = AgentConfig(entity_id="agent.mcp.test", name="Test Agent")
        mock_llm = LLMConfig(
            enabled=False,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key"
        )
        mock_mcp = MCPConfig(
            transport="stdio",
            command="test",
            url="http://localhost:3000",
            timeout=30
        )
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "mcp", PropertyMock(return_value=mock_mcp))
        
        # Call talk()
        response, metrics = await talk(base_dostevent)
        
        # Should return error response
        assert response["message"]["text"]["data"] == "I didn't catch that. Could you say something?"
        assert metrics["models"] == {}
        
        print(f"\n✓ talk() handled empty message correctly")
    
    async def test_talk_with_llm_enabled(self, search_dostevent, monkeypatch):
        """Test talk() with LLM agent enabled"""
        # Mock MCP client
        mock_client = AsyncMock()
        mock_tool = MagicMock()
        mock_tool.name = "search_restaurants"
        mock_tool.description = "Search for restaurants"
        mock_tool.input_schema = {}
        mock_client.list_tools = AsyncMock(return_value=[mock_tool])
        
        # Mock tool result
        from app.client.mcp_client import MCPToolResult
        mock_client.call_tool = AsyncMock(return_value=MCPToolResult(
            content="Found 3 restaurants: Pizza Hut, Dominos, Papa Johns",
            is_error=False
        ))
        
        async def mock_init_client():
            return mock_client
        
        monkeypatch.setattr("app.engine.talk.initialize_mcp_client", mock_init_client)
        
        # Mock settings with LLM enabled
        from app.config import Settings, AgentConfig, LLMConfig, MCPConfig
        
        mock_agent = AgentConfig(entity_id="agent.mcp.test", name="Test Agent")
        mock_llm = LLMConfig(
            enabled=True,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key"
        )
        mock_mcp = MCPConfig(
            transport="stdio",
            command="test",
            url="http://localhost:3000",
            timeout=30
        )
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "mcp", PropertyMock(return_value=mock_mcp))
        
        # Mock OpenAI client
        mock_openai_response = MagicMock()
        mock_openai_response.choices = [MagicMock()]
        mock_openai_response.choices[0].message.content = "Here are 3 pizza places."
        mock_openai_response.choices[0].message.tool_calls = None
        mock_openai_response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
        
        with patch("app.llm.agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            
            # Call talk() with LLM enabled
            response, metrics = await talk(search_dostevent)
        
        # Validate response
        assert response["isAiGenerated"] is True
        assert "message" in response
        
        # Validate metrics contain token usage
        assert "models" in metrics
        
        print(f"\n✓ talk() with LLM returned valid response")
    
    async def test_talk_handles_mcp_error(self, base_dostevent, monkeypatch):
        """Test talk() handles MCP client errors gracefully"""
        # Mock MCP client that raises error
        async def mock_failing_init():
            raise RuntimeError("MCP server connection failed")
        
        monkeypatch.setattr("app.engine.talk.initialize_mcp_client", mock_failing_init)
        
        # Mock settings
        from app.config import Settings, AgentConfig, LLMConfig, MCPConfig
        
        mock_agent = AgentConfig(entity_id="agent.mcp.test", name="Test Agent")
        mock_llm = LLMConfig(
            enabled=False,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key"
        )
        mock_mcp = MCPConfig(
            transport="stdio",
            command="test",
            url="http://localhost:3000",
            timeout=30
        )
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "mcp", PropertyMock(return_value=mock_mcp))
        
        # Call talk()
        response, metrics = await talk(base_dostevent)
        
        # Should return error response
        assert response["eventHint"] == "error"
        assert "error" in response["message"]["text"]["data"].lower()
        assert "models" in metrics
        
        print(f"\n✓ talk() handled MCP error gracefully")
