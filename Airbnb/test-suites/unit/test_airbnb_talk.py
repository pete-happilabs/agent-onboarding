"""
Unit tests for Airbnb talk engine — MCP template's talk() with mocked client/agent.

Tests:
  - dostEvent input parsing
  - Response structure
  - TalkMetrics output
  - dostCategories from tool results
  - Edge cases (empty message, exceptions)
"""
import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp"))

from dost.protocol import (
    validate_dost_event,
    extract_query_text,
    DOST_SPEC_VERSION,
)


@dataclass
class MockAgentResult:
    """Mock ReActAgent.run() result."""
    text: str = "Found 3 apartments in Paris"
    model: str = "gpt-4o-mini"
    input_tokens: int = 500
    output_tokens: int = 150
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


def _mock_settings(entity_id="agent.mcp.airbnb", llm_enabled=True):
    settings = MagicMock()
    settings.agent.entity_id = entity_id
    settings.agent.name = "Airbnb"
    settings.llm.enabled = llm_enabled
    settings.llm.model = "gpt-4o-mini"
    settings.llm.api_key = "test-key"
    settings.llm.temperature = 0.0
    settings.mcp.transport = "stdio"
    settings.mcp.command = "echo test"
    settings.mcp.timeout = 30
    settings.mcp.get_effective_command.return_value = "echo test"
    return settings


def _patch_talk_deps(settings=None, agent_result=None, client_error=None):
    """Create context manager that patches all MCP talk dependencies."""
    if settings is None:
        settings = _mock_settings()
    if agent_result is None:
        agent_result = MockAgentResult()

    mock_agent_cls = MagicMock()
    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=agent_result)
    mock_agent_cls.return_value = mock_agent_instance

    mock_build_cats = MagicMock(return_value=None)
    if agent_result.tool_results:
        from app.llm.response_formatter import build_dost_categories as real_build
        mock_build_cats = real_build

    mock_infer = MagicMock(return_value="response")
    if agent_result.tool_results:
        from app.llm.response_formatter import infer_event_hint as real_infer
        mock_infer = real_infer

    patches = {
        "settings": patch("app.engine.talk.get_settings", return_value=settings),
        "mcp_client": patch(
            "app.engine.talk.initialize_mcp_client",
            new_callable=AsyncMock,
            **({"side_effect": client_error} if client_error else {}),
        ),
        # Patch the lazy imports in app.llm module
        "agent_cls": patch("app.llm.ReActAgent", mock_agent_cls, create=True),
        "build_cats": patch("app.llm.build_dost_categories", mock_build_cats, create=True),
        "infer_hint": patch("app.llm.infer_event_hint", mock_infer, create=True),
    }
    return patches


@pytest.mark.unit
class TestMCPTalkWithMocks:
    """Test MCP talk() with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_returns_tuple(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            result = await talk(airbnb_dostevent)
            assert isinstance(result, tuple)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_response_is_valid_dostevent(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            errors = validate_dost_event(resp)
            assert errors == [], f"Invalid: {errors}"

    @pytest.mark.asyncio
    async def test_entity_ids_swapped(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            assert resp["sourceEntityId"] == "agent.mcp.airbnb"
            assert resp["destinationEntityId"] == "hum.user.traveler1"

    @pytest.mark.asyncio
    async def test_session_preserved(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            assert resp["sessionId"] == "airbnb-session-001"

    @pytest.mark.asyncio
    async def test_is_ai_generated(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            assert resp["isAiGenerated"] is True

    @pytest.mark.asyncio
    async def test_metrics_format(self, airbnb_dostevent):
        p = _patch_talk_deps(agent_result=MockAgentResult(input_tokens=500, output_tokens=150))
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            _, metrics = await talk(airbnb_dostevent)
            assert "models" in metrics
            assert "gpt-4o-mini" in metrics["models"]
            assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 500

    @pytest.mark.asyncio
    async def test_empty_message(self, empty_message_event):
        p = _patch_talk_deps()
        with p["settings"]:
            from app.engine.talk import talk
            resp, metrics = await talk(empty_message_event)
            assert "didn't catch" in resp["message"]["text"]["data"].lower()
            assert metrics["models"] == {}

    @pytest.mark.asyncio
    async def test_exception_returns_error_event(self, airbnb_dostevent):
        p = _patch_talk_deps(client_error=RuntimeError("Connection failed"))
        with p["settings"], p["mcp_client"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            assert resp["eventHint"] == "error"
            assert "error" in resp["message"]["text"]["data"].lower()

    @pytest.mark.asyncio
    async def test_version_matches_spec(self, airbnb_dostevent):
        p = _patch_talk_deps()
        with p["settings"], p["mcp_client"], p["agent_cls"], p["build_cats"], p["infer_hint"]:
            from app.engine.talk import talk
            resp, _ = await talk(airbnb_dostevent)
            assert resp["version"] == DOST_SPEC_VERSION
