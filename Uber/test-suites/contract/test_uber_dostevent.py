"""
Contract tests for Uber agent — validate dostEvent protocol compliance.

Ensures response events produced by the Uber agent conform to the
dostEvent v00.01.01 specification.
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "generic"))

from dost.protocol import (
    create_dost_event,
    create_dost_message,
    validate_dost_event,
    extract_query_text,
    extract_objects_from_categories,
    DOST_SPEC_VERSION,
)
from app.engine.talk import talk, set_agent


def _make_agent(response="Here are the rides", tool_results=None):
    agent = MagicMock()

    async def _process(user_message, user_id, **kw):
        return {
            "response": response,
            "state": {},
            "tool_results": tool_results or [],
            "input_tokens": 200,
            "output_tokens": 80,
            "model": "gpt-4o-mini",
        }

    agent.process_message = AsyncMock(side_effect=_process)
    return agent


@pytest.mark.contract
class TestUberDostEventContract:
    """Verify Uber's response dostEvent conforms to spec."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        set_agent(_make_agent())
        yield
        set_agent(None)

    @pytest.mark.asyncio
    async def test_version_matches_spec(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["version"] == DOST_SPEC_VERSION

    @pytest.mark.asyncio
    async def test_has_required_fields(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        required = ["version", "timestamp", "eventId", "sessionId", "sourceEntityId", "message"]
        for field in required:
            assert field in resp, f"Missing {field}"

    @pytest.mark.asyncio
    async def test_timestamp_is_iso8601(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        ts = resp["timestamp"]
        assert "T" in ts
        assert ts.endswith("Z")

    @pytest.mark.asyncio
    async def test_event_id_is_uuid(self, uber_dostevent):
        import uuid
        resp, _ = await talk(uber_dostevent)
        uuid.UUID(resp["eventId"])  # Raises if not valid UUID

    @pytest.mark.asyncio
    async def test_validate_passes(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        errors = validate_dost_event(resp)
        assert errors == []

    @pytest.mark.asyncio
    async def test_message_text_data_structure(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        msg = resp["message"]
        assert "text" in msg
        assert "data" in msg["text"]
        assert isinstance(msg["text"]["data"], str)
        assert len(msg["text"]["data"]) > 0

    @pytest.mark.asyncio
    async def test_source_entity_is_uber(self, uber_dostevent):
        resp, _ = await talk(uber_dostevent)
        assert resp["sourceEntityId"] == "com.uber.rides"

    @pytest.mark.asyncio
    async def test_categories_structure_when_tools_used(self, uber_dostevent):
        import json
        tool_results = [{
            "name": "search_rides",
            "content": json.dumps([
                {"id": "uber_go", "name": "UberGo", "description": "Affordable"},
            ]),
            "is_error": False,
        }]
        set_agent(_make_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        cats = resp.get("categories")
        assert cats is not None
        assert "currency" in cats
        assert "categories" in cats
        assert isinstance(cats["categories"], list)
        assert len(cats["categories"]) > 0
        cat = cats["categories"][0]
        assert "title" in cat
        assert "objects" in cat
        assert isinstance(cat["objects"], list)

    @pytest.mark.asyncio
    async def test_dost_objects_have_required_fields(self, uber_dostevent):
        import json
        tool_results = [{
            "name": "search_rides",
            "content": json.dumps([
                {"id": "uber_go", "name": "UberGo", "description": "Affordable rides"},
            ]),
            "is_error": False,
        }]
        set_agent(_make_agent(tool_results=tool_results))
        resp, _ = await talk(uber_dostevent)
        objects = extract_objects_from_categories(resp)
        assert len(objects) > 0
        obj = objects[0]
        assert "id" in obj
        assert "type" in obj
        assert "title" in obj

    @pytest.mark.asyncio
    async def test_metrics_contract(self, uber_dostevent):
        _, metrics = await talk(uber_dostevent)
        assert "models" in metrics
        for model_name, usage in metrics["models"].items():
            assert isinstance(model_name, str)
            assert "input_tokens" in usage
            assert "output_tokens" in usage
            assert isinstance(usage["input_tokens"], int)
            assert isinstance(usage["output_tokens"], int)
            assert usage["input_tokens"] >= 0
            assert usage["output_tokens"] >= 0
