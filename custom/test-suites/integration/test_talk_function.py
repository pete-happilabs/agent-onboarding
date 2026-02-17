"""
Integration tests for talk() function - Custom Agent
Tests the real talk() implementation with mocked CustomClient
"""
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

# Real imports from your code
import sys
from pathlib import Path

# Add custom root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.engine.talk import talk
from app.core.protocol import extract_query_text, DOST_SPEC_VERSION


@pytest.mark.integration
@pytest.mark.asyncio
class TestTalkFunctionCustom:
    """Integration tests for talk() - real implementation"""
    
    async def test_talk_with_valid_dostevent(self, base_dostevent, monkeypatch):
        """Test talk() with a valid dostEvent - happy path"""
        # Mock the CustomClient to avoid real API calls
        from app.custom.client import CustomClient
        
        mock_client = MagicMock()
        mock_client.get_agent_config.return_value = {
            "prompt_name": "default"
        }
        mock_client.get_available_tools.return_value = []
        
        monkeypatch.setattr("app.engine.talk.CustomClient", lambda config_path: mock_client)
        
        # Mock ReActAgent
        mock_agent_result = MagicMock()
        mock_agent_result.text = "Found 5 meals with chicken"
        mock_agent_result.tool_results = []
        mock_agent_result.model = "gpt-4o-mini"
        mock_agent_result.input_tokens = 100
        mock_agent_result.output_tokens = 50
        
        async def mock_run(message):
            return mock_agent_result
        
        mock_agent = MagicMock()
        mock_agent.run = mock_run
        
        monkeypatch.setattr("app.engine.talk.ReActAgent", lambda **kwargs: mock_agent)
        
        # Mock settings
        from app.config import Settings, AgentConfig, LLMConfig, CustomConfig
        
        mock_agent_cfg = AgentConfig(entity_id="agent.custom.test", name="Test Agent")
        mock_llm = LLMConfig(
            enabled=True,
            provider="openai",
            model="gpt-4o-mini",
            api_key="test-key",
            temperature=0.0
        )
        mock_custom = CustomConfig(
            config_path="configs/test.yaml",
            currency="INR"
        )
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent_cfg))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "custom", PropertyMock(return_value=mock_custom))
        
        # Call real talk()
        response, metrics = await talk(base_dostevent)
        
        # Validate response structure
        assert response["version"] == DOST_SPEC_VERSION
        assert response["sourceEntityId"] == "agent.custom.test"
        assert response["destinationEntityId"] == base_dostevent["sourceEntityId"]
        assert response["sessionId"] == base_dostevent["sessionId"]
        assert response["isAiGenerated"] is True
        assert "message" in response
        assert response["message"]["text"]["data"] == "Found 5 meals with chicken"
        
        # Validate metrics structure (DPA format)
        assert "models" in metrics
        assert isinstance(metrics["models"], dict)
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 50
        
        print(f"\n✓ talk() returned valid dostEvent response")
    
    async def test_talk_with_empty_message(self, base_dostevent, monkeypatch):
        """Test talk() handles empty message gracefully"""
        # Remove message
        base_dostevent["message"] = {"text": {"data": ""}}
        
        # Mock settings
        from app.config import Settings, AgentConfig, LLMConfig, CustomConfig
        
        mock_agent_cfg = AgentConfig(entity_id="agent.custom.test", name="Test Agent")
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
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent_cfg))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "custom", PropertyMock(return_value=mock_custom))
        
        # Call talk()
        response, metrics = await talk(base_dostevent)
        
        # Should return error response
        assert response["message"]["text"]["data"] == "I didn't catch that. Could you say something?"
        assert metrics["models"] == {}
        
        print(f"\n✓ talk() handled empty message correctly")
    
    async def test_talk_handles_client_error(self, base_dostevent, monkeypatch):
        """Test talk() handles CustomClient errors gracefully"""
        # Mock CustomClient that raises error
        def mock_failing_client(config_path):
            raise RuntimeError("Custom client initialization failed")
        
        monkeypatch.setattr("app.engine.talk.CustomClient", mock_failing_client)
        
        # Mock settings
        from app.config import Settings, AgentConfig, LLMConfig, CustomConfig
        
        mock_agent_cfg = AgentConfig(entity_id="agent.custom.test", name="Test Agent")
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
        
        monkeypatch.setattr(Settings, "agent", PropertyMock(return_value=mock_agent_cfg))
        monkeypatch.setattr(Settings, "llm", PropertyMock(return_value=mock_llm))
        monkeypatch.setattr(Settings, "custom", PropertyMock(return_value=mock_custom))
        
        # Call talk()
        response, metrics = await talk(base_dostevent)
        
        # Should return error response
        assert response["eventHint"] == "error"
        assert "error" in response["message"]["text"]["data"].lower() or "issue" in response["message"]["text"]["data"].lower()
        assert "models" in metrics
        
        print(f"\n✓ talk() handled client error gracefully")
