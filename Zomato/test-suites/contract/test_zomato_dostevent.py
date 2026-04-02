"""
Contract tests for Zomato agent — validate dostEvent protocol compliance.

Tests the YAML config + response formatter produce valid dostEvent structures
that conform to the v00.01.01 spec.
"""
import pytest
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "custom"))

from dost.protocol import (
    validate_dost_event,
    create_dost_event,
    create_dost_message,
    extract_objects_from_categories,
    DOST_SPEC_VERSION,
)
from app.custom.registry import load_tools_from_config, get_tool
from app.llm.response_formatter import build_dost_categories, build_dost_object_from_item


@pytest.fixture
def zomato_config():
    config_path = str(Path(__file__).parent.parent.parent / "config.yaml")
    return load_tools_from_config(config_path)


@pytest.mark.contract
class TestZomatoResponseContract:
    """Verify Zomato produces spec-compliant dostEvents."""

    def test_simulated_search_response(self, zomato_config):
        """Simulate a search_food call and verify response structure."""
        tool = get_tool(zomato_config, "search_food")
        # Simulate API response
        api_response = {
            "meals": [
                {
                    "idMeal": "52771",
                    "strMeal": "Spicy Arrabiata Penne",
                    "strInstructions": "Bring a large pot of water to a boil...",
                    "strMealThumb": "https://www.themealdb.com/images/media/meals/ustsqw1468250014.jpg",
                },
                {
                    "idMeal": "52772",
                    "strMeal": "Teriyaki Chicken Casserole",
                    "strInstructions": "Preheat oven to 350...",
                    "strMealThumb": "https://www.themealdb.com/images/media/meals/wvpsxx1468256321.jpg",
                },
            ]
        }

        tool_results = [{
            "name": "search_food",
            "content": json.dumps(api_response),
            "is_error": False,
            "response_mapping": tool.response_mapping,
        }]

        cats = build_dost_categories(tool_results, currency="INR")
        event = create_dost_event(
            source_entity_id="agent.custom.zomato",
            destination_entity_id="hum.user.test",
            session_id="test-session",
            event_hint="food_list",
            is_ai_generated=True,
            message=create_dost_message(text="Here are some pasta options"),
            categories=cats,
        )

        # Validate full event
        errors = validate_dost_event(event)
        assert errors == [], f"Invalid dostEvent: {errors}"

        # Validate structure
        assert event["version"] == DOST_SPEC_VERSION
        assert event["sourceEntityId"] == "agent.custom.zomato"
        assert event["isAiGenerated"] is True

        # Validate categories
        assert event["categories"]["currency"] == "INR"
        objects = extract_objects_from_categories(event)
        assert len(objects) == 2
        assert objects[0]["title"] == "Spicy Arrabiata Penne"
        assert "media" in objects[0]

    def test_simulated_categories_response(self, zomato_config):
        """Simulate list_all_categories call."""
        tool = get_tool(zomato_config, "list_all_categories")
        api_response = {
            "categories": [
                {
                    "idCategory": "1",
                    "strCategory": "Beef",
                    "strCategoryDescription": "Beef is the culinary name...",
                    "strCategoryThumb": "https://www.themealdb.com/images/category/beef.png",
                },
            ]
        }

        tool_results = [{
            "name": "list_all_categories",
            "content": json.dumps(api_response),
            "is_error": False,
            "response_mapping": tool.response_mapping,
        }]

        cats = build_dost_categories(tool_results)
        assert cats is not None
        objects = cats["categories"][0]["objects"]
        assert len(objects) == 1
        assert objects[0]["title"] == "Beef"

    def test_simulated_null_meals_response(self, zomato_config):
        """TheMealDB returns {"meals": null} when no results found."""
        tool_results = [{
            "name": "search_food",
            "content": json.dumps({"meals": None}),
            "is_error": False,
            "response_mapping": {"items_path": "meals"},
        }]
        cats = build_dost_categories(tool_results)
        assert cats is None

    def test_dost_object_fields(self, zomato_config):
        """Verify individual dostObject has required fields."""
        item = {
            "idMeal": "12345",
            "strMeal": "Butter Chicken",
            "strInstructions": "Marinate chicken...",
            "strMealThumb": "https://example.com/butter-chicken.jpg",
        }
        mapping = get_tool(zomato_config, "search_food").response_mapping
        obj = build_dost_object_from_item(item, mapping, object_type="meal")

        assert "id" in obj
        assert "type" in obj
        assert obj["type"] == "meal"
        assert obj["title"] == "Butter Chicken"
        assert "description" in obj
        assert "media" in obj
        assert obj["media"]["images"][0]["data-type"] == "url"

    def test_metrics_structure(self):
        """Verify TalkMetrics produces correct format."""
        from dost.metrics import TalkMetrics
        m = TalkMetrics()
        m.add_llm("gpt-4o-mini", 500, 100)
        d = m.to_dict()
        assert "models" in d
        assert d["models"]["gpt-4o-mini"]["input_tokens"] == 500
        assert d["models"]["gpt-4o-mini"]["output_tokens"] == 100
        assert d["models"]["gpt-4o-mini"]["cached_tokens"] == 0
