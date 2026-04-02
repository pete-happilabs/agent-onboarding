"""
Unit tests for Uber talk engine — generic template's talk() with dostCategories.

Tests the talk() pipeline with mocked agent to avoid real LLM calls.
Validates:
  - dostEvent input parsing
  - Response dostEvent structure
  - TalkMetrics output format
  - dostCategories construction from tool results
  - Event hint inference
  - Edge cases (empty message, no agent, long message)
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "generic"))

from dost.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
    validate_dost_event,
)
from app.engine.talk import (
    talk,
    set_agent,
    get_agent,
    _build_response,
    _build_categories_from_tools,
    _infer_event_hint,
    _format_tool_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_agent(response="Mock ride response", tool_results=None, model="gpt-4o-mini",
                     input_tokens=100, output_tokens=50):
    """Create a mock agent with controlled outputs."""
    agent = MagicMock()

    async def mock_process(user_message, user_id, **kwargs):
        return {
            "response": response,
            "state": {"selected_service_id": None, "booking_details": {}, "details_shown": False},
            "tool_results": tool_results or [],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
        }

    agent.process_message = AsyncMock(side_effect=mock_process)
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTalkResponseStructure:
    """Verify talk() returns valid dostEvent + metrics."""

    @pytest.fixture(autouse=True)
    def _setup_agent(self):
        set_agent(_make_mock_agent())
        yield
        set_agent(None)

    @pytest.mark.asyncio
    async def test_returns_tuple(self, uber_dostevent):
        result = await talk(uber_dostevent)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_response_is_valid_dostevent(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        errors = validate_dost_event(resp)
        assert errors == [], f"Invalid dostEvent: {errors}"

    @pytest.mark.asyncio
    async def test_response_entity_ids_swapped(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["sourceEntityId"] == "com.uber.rides"
        assert resp["destinationEntityId"] == "hum.user.rider1"

    @pytest.mark.asyncio
    async def test_response_session_preserved(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["sessionId"] == "uber-session-001"

    @pytest.mark.asyncio
    async def test_response_is_ai_generated(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["isAiGenerated"] is True

    @pytest.mark.asyncio
    async def test_response_has_message(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["message"] is not None
        assert resp["message"]["text"]["data"] == "Mock ride response"

    @pytest.mark.asyncio
    async def test_metrics_format(self, uber_dostevent):
        _, metrics = await talk(uber_dostevent)
        assert "models" in metrics
        assert "gpt-4o-mini" in metrics["models"]
        assert metrics["models"]["gpt-4o-mini"]["input_tokens"] == 100
        assert metrics["models"]["gpt-4o-mini"]["output_tokens"] == 50


@pytest.mark.unit
class TestTalkEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def _setup_agent(self):
        set_agent(_make_mock_agent())
        yield
        set_agent(None)

    @pytest.mark.asyncio
    async def test_empty_message_returns_prompt(self, empty_message_event):
        resp, metrics = await talk(empty_message_event)
        assert "didn't catch" in resp["message"]["text"]["data"].lower()
        assert metrics["models"] == {}

    @pytest.mark.asyncio
    async def test_no_message_returns_prompt(self, no_message_event):
        resp, _ = await talk(no_message_event)
        assert "didn't catch" in resp["message"]["text"]["data"].lower()

    @pytest.mark.asyncio
    async def test_no_agent_returns_error(self, uber_dostevent):
        set_agent(None)
        resp, _ = await talk(uber_dostevent)
        assert "not initialized" in resp["message"]["text"]["data"].lower()
        assert resp["eventHint"] == "error"

    @pytest.mark.asyncio
    async def test_long_message_truncated(self, uber_dostevent):
        uber_dostevent["message"]["text"]["data"] = "x" * 15_000
        agent = _make_mock_agent()
        set_agent(agent)
        await talk(uber_dostevent)
        call_args = agent.process_message.call_args
        actual_msg = call_args.kwargs.get("user_message") or call_args[0][0]
        assert len(actual_msg) <= 10_000

    @pytest.mark.asyncio
    async def test_agent_exception_returns_error(self, uber_dostevent):
        agent = MagicMock()
        agent.process_message = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        set_agent(agent)
        resp, metrics = await talk(uber_dostevent)
        assert resp["eventHint"] == "error"
        assert "issue" in resp["message"]["text"]["data"].lower()


@pytest.mark.unit
class TestDostCategories:
    """Test dostCategories construction from tool results."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        yield
        set_agent(None)

    @pytest.mark.asyncio
    async def test_no_tool_results_no_categories(self, uber_dostevent):
        set_agent(_make_mock_agent(tool_results=[]))
        resp, _ = await talk(uber_dostevent)
        assert resp.get("categories") is None

    @pytest.mark.asyncio
    async def test_text_tool_results_create_categories(self, uber_dostevent):
        tool_results = [{
            "name": "list_ride_types",
            "content": "UberGo\n  Starting at Rs.80\nUber Premier\n  Starting at Rs.150",
            "is_error": False,
        }]
        set_agent(_make_mock_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        cats = resp.get("categories")
        assert cats is not None
        assert cats["currency"] == "INR"
        assert len(cats["categories"]) == 1
        assert cats["categories"][0]["title"] == "List Ride Types"

    @pytest.mark.asyncio
    async def test_json_tool_results_create_objects(self, uber_dostevent):
        import json
        data = [
            {"id": "uber_go", "name": "UberGo", "description": "Affordable rides"},
            {"id": "uber_xl", "name": "UberXL", "description": "Spacious SUVs"},
        ]
        tool_results = [{
            "name": "search_rides",
            "content": json.dumps(data),
            "is_error": False,
        }]
        set_agent(_make_mock_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        cats = resp.get("categories")
        assert cats is not None
        objects = cats["categories"][0]["objects"]
        assert len(objects) == 2
        assert objects[0]["title"] == "UberGo"

    @pytest.mark.asyncio
    async def test_error_tool_results_skipped(self, uber_dostevent):
        tool_results = [{
            "name": "search_rides",
            "content": "Something went wrong",
            "is_error": True,
        }]
        set_agent(_make_mock_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        assert resp.get("categories") is None

    @pytest.mark.asyncio
    async def test_event_hint_inferred(self, uber_dostevent):
        tool_results = [{
            "name": "list_ride_types",
            "content": "Rides list",
            "is_error": False,
        }]
        set_agent(_make_mock_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        assert resp["eventHint"] == "ride_types_list"


@pytest.mark.unit
class TestInferEventHint:
    """Test event hint inference from tool names."""

    def test_search_prefix(self):
        assert _infer_event_hint([{"name": "search_rides", "is_error": False}]) == "rides_list"

    def test_book_prefix(self):
        assert _infer_event_hint([{"name": "book_ride", "is_error": False}]) == "ride_booked"

    def test_get_prefix(self):
        assert _infer_event_hint([{"name": "get_ride_details", "is_error": False}]) == "ride_details_details"

    def test_list_prefix(self):
        assert _infer_event_hint([{"name": "list_ride_types", "is_error": False}]) == "ride_types_list"

    def test_unknown_prefix(self):
        assert _infer_event_hint([{"name": "cancel_ride", "is_error": False}]) == "cancel_ride_response"

    def test_empty_results(self):
        assert _infer_event_hint([]) == "response"

    def test_all_errors_returns_response(self):
        assert _infer_event_hint([{"name": "search", "is_error": True}]) == "response"

    def test_uses_last_non_error(self):
        results = [
            {"name": "search_rides", "is_error": False},
            {"name": "book_ride", "is_error": False},
        ]
        assert _infer_event_hint(results) == "ride_booked"


@pytest.mark.unit
class TestFormatToolName:
    """Test tool name formatting."""

    def test_snake_case(self):
        assert _format_tool_name("search_rides") == "Search Rides"

    def test_single_word(self):
        assert _format_tool_name("search") == "Search"

    def test_triple_underscore(self):
        assert _format_tool_name("list_ride_types") == "List Ride Types"


@pytest.mark.unit
class TestBuildCategoriesFromTools:
    """Test _build_categories_from_tools directly."""

    def _mock_settings(self):
        settings = MagicMock()
        settings.generic.currency = "INR"
        return settings

    def test_none_for_empty_list(self):
        assert _build_categories_from_tools([], self._mock_settings()) is None

    def test_none_for_all_errors(self):
        results = [{"name": "x", "content": "fail", "is_error": True}]
        assert _build_categories_from_tools(results, self._mock_settings()) is None

    def test_text_content_becomes_object(self):
        results = [{"name": "list_ride_types", "content": "UberGo starting at Rs.80", "is_error": False}]
        cats = _build_categories_from_tools(results, self._mock_settings())
        assert cats is not None
        assert cats["currency"] == "INR"
        assert len(cats["categories"]) == 1
        obj = cats["categories"][0]["objects"][0]
        assert obj["type"] == "list_ride_types"
        assert "Rs.80" in obj["description"]

    def test_json_list_creates_multiple_objects(self):
        import json
        data = [{"id": "a", "name": "A", "description": "Desc A"}, {"id": "b", "name": "B", "description": "Desc B"}]
        results = [{"name": "search", "content": json.dumps(data), "is_error": False}]
        cats = _build_categories_from_tools(results, self._mock_settings())
        assert len(cats["categories"][0]["objects"]) == 2

    def test_json_object_creates_single_object(self):
        import json
        data = {"id": "x", "name": "X item", "description": "One item"}
        results = [{"name": "get", "content": json.dumps(data), "is_error": False}]
        cats = _build_categories_from_tools(results, self._mock_settings())
        assert len(cats["categories"][0]["objects"]) == 1
        assert cats["categories"][0]["objects"][0]["title"] == "X item"

    def test_empty_string_content_skipped(self):
        results = [{"name": "x", "content": "   ", "is_error": False}]
        assert _build_categories_from_tools(results, self._mock_settings()) is None

    def test_multiple_tools_create_multiple_categories(self):
        results = [
            {"name": "search_rides", "content": "Rides available", "is_error": False},
            {"name": "get_ride_details", "content": "UberGo details", "is_error": False},
        ]
        cats = _build_categories_from_tools(results, self._mock_settings())
        assert len(cats["categories"]) == 2
