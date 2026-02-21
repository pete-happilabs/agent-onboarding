"""
Integration tests for talk() function - Custom Agent
"""
import pytest
import importlib
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the module correctly via importlib to avoid name collision
talk_module = importlib.import_module("app.engine.talk")
talk = talk_module.talk

from app.core.protocol import DOST_SPEC_VERSION


def _make_mock_settings(entity_id: str = "agent.custom.test"):
    """Helper: build a mock Settings object"""
    mock_settings = MagicMock()
    mock_settings.agent.entity_id = entity_id
    mock_settings.llm.api_key = "sk-test-key"
    mock_settings.llm.model = "gpt-4o-mini"
    mock_settings.llm.temperature = 0.0
    mock_settings.custom.config_path = "configs/test.yaml"
    mock_settings.custom.currency = "INR"
    return mock_settings


@pytest.mark.integration
@pytest.mark.asyncio
class TestTalkFunctionCustom:

    async def test_talk_with_valid_dostevent(self, base_dostevent, monkeypatch):
        """Test talk() with a valid dostEvent - happy path"""

        monkeypatch.setattr(talk_module, "get_settings", lambda: _make_mock_settings())

        mock_client = MagicMock()
        mock_client.get_agent_config.return_value = {"prompt_name": "default"}
        mock_client.get_available_tools.return_value = []
        monkeypatch.setattr(talk_module, "CustomClient", lambda config_path: mock_client)

        mock_result = MagicMock()
        mock_result.text = "Found 5 meals with chicken"
        mock_result.tool_results = []
        mock_result.model = "gpt-4o-mini"
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        monkeypatch.setattr(talk_module, "ReActAgent", lambda **kwargs: mock_agent)

        response, metrics = await talk(base_dostevent)

        assert response["version"] == DOST_SPEC_VERSION
        assert response["sourceEntityId"] == "agent.custom.test"
        assert response["destinationEntityId"] == base_dostevent["sourceEntityId"]
        assert response["sessionId"] == base_dostevent["sessionId"]
        assert response["isAiGenerated"] is True
        assert response["message"]["text"]["data"] == "Found 5 meals with chicken"

        assert "models" in metrics
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 50

        print(f"\n✓ talk() returned valid dostEvent response")

    async def test_talk_with_empty_message(self, base_dostevent, monkeypatch):
        """Test talk() handles empty message gracefully"""

        monkeypatch.setattr(talk_module, "get_settings", lambda: _make_mock_settings())

        base_dostevent["message"]["text"]["data"] = ""

        response, metrics = await talk(base_dostevent)

        assert response["message"]["text"]["data"] == "I didn't catch that. Could you say something?"
        assert metrics["models"] == {}

        print(f"\n✓ talk() handled empty message correctly")

    async def test_talk_handles_client_error(self, base_dostevent, monkeypatch):
        """Test talk() handles CustomClient errors gracefully"""

        monkeypatch.setattr(talk_module, "get_settings", lambda: _make_mock_settings())

        def mock_failing_client(config_path):
            raise RuntimeError("Custom client initialization failed")

        monkeypatch.setattr(talk_module, "CustomClient", mock_failing_client)

        response, metrics = await talk(base_dostevent)

        assert response["eventHint"] == "error"
        assert (
            "issue" in response["message"]["text"]["data"].lower()
            or "error" in response["message"]["text"]["data"].lower()
        )
        assert "models" in metrics

        print(f"\n✓ talk() handled client error gracefully")
