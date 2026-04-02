"""
Contract tests for Airbnb agent — validate dostEvent protocol compliance.

Tests that simulated Airbnb responses conform to the dostEvent v00.01.01 spec.
"""
import pytest
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp"))

from dost.protocol import (
    validate_dost_event,
    create_dost_event,
    create_dost_message,
    extract_objects_from_categories,
    DOST_SPEC_VERSION,
)


@pytest.mark.contract
class TestAirbnbResponseContract:
    """Verify Airbnb responses conform to dostEvent spec."""

    def test_simulated_search_response(self):
        """Simulate an airbnb_search response and verify spec compliance."""
        from app.llm.response_formatter import build_dost_categories

        tool_results = [{
            "name": "airbnb_search",
            "content": json.dumps([
                {
                    "name": "Charming Studio in Le Marais",
                    "id": "listing_001",
                    "description": "Beautiful studio apartment in the heart of Paris",
                    "rating": "4.8",
                    "price": 120,
                },
                {
                    "name": "Modern Loft near Eiffel Tower",
                    "id": "listing_002",
                    "description": "Spacious loft with stunning tower views",
                    "rating": "4.9",
                    "price": 250,
                },
            ]),
            "is_error": False,
        }]

        cats = build_dost_categories(tool_results)
        event = create_dost_event(
            source_entity_id="agent.mcp.airbnb",
            destination_entity_id="hum.user.traveler",
            session_id="contract-test-session",
            event_hint="listing_list",
            is_ai_generated=True,
            message=create_dost_message(text="Here are apartments in Paris"),
            categories=cats,
        )

        errors = validate_dost_event(event)
        assert errors == [], f"Invalid: {errors}"
        assert event["version"] == DOST_SPEC_VERSION
        assert event["sourceEntityId"] == "agent.mcp.airbnb"
        assert event["isAiGenerated"] is True

        objects = extract_objects_from_categories(event)
        assert len(objects) == 2
        assert objects[0]["title"] == "Charming Studio in Le Marais"

    def test_response_without_tool_results(self):
        """Agent responds with text only (no tools called)."""
        event = create_dost_event(
            source_entity_id="agent.mcp.airbnb",
            destination_entity_id="hum.user.test",
            session_id="no-tools-session",
            event_hint="response",
            is_ai_generated=True,
            message=create_dost_message(text="I can help you find stays. Where would you like to go?"),
        )
        errors = validate_dost_event(event)
        assert errors == []
        assert event.get("categories") is None

    def test_error_response(self):
        """Agent returns error response."""
        event = create_dost_event(
            source_entity_id="agent.mcp.airbnb",
            destination_entity_id="hum.user.test",
            session_id="error-session",
            event_hint="error",
            is_ai_generated=True,
            message=create_dost_message(text="Sorry, I encountered an error."),
        )
        errors = validate_dost_event(event)
        assert errors == []
        assert event["eventHint"] == "error"

    def test_metrics_contract(self):
        from dost.metrics import TalkMetrics
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", 9120, 350)
        d = m.to_dict()
        assert d["models"]["gpt-4o-mini"]["input_tokens"] == 9120
        assert d["models"]["gpt-4o-mini"]["output_tokens"] == 350
        assert d["models"]["gpt-4o-mini"]["cached_tokens"] == 0

    def test_empty_metrics(self):
        from dost.metrics import TalkMetrics
        m = TalkMetrics()
        d = m.to_dict()
        assert d == {"models": {}}
