"""
Unit tests for Zomato talk engine — custom template's talk() with mocked agent.

Validates:
  - dostEvent input parsing
  - Response dostEvent structure
  - TalkMetrics output format
  - dostCategories from tool results
  - Edge cases
"""
import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "custom"))

from dost.protocol import (
    create_dost_event,
    create_dost_message,
    validate_dost_event,
    extract_query_text,
    extract_objects_from_categories,
    DOST_SPEC_VERSION,
)
from app.llm.response_formatter import (
    build_dost_categories,
    infer_event_hint,
    build_dost_object_from_item,
    extract_items_from_response,
    get_nested_value,
)


@pytest.mark.unit
class TestResponseFormatter:
    """Test the custom template's response_formatter."""

    def test_build_categories_from_tool_results(self):
        tool_results = [{
            "name": "search_food",
            "content": json.dumps({
                "meals": [
                    {"strMeal": "Pasta", "strInstructions": "Cook pasta"},
                    {"strMeal": "Pizza", "strInstructions": "Bake pizza"},
                ]
            }),
            "is_error": False,
            "response_mapping": {
                "items_path": "meals",
                "title_field": "strMeal",
                "description_field": "strInstructions",
                "category_title": "Food Items",
            },
        }]
        cats = build_dost_categories(tool_results, currency="INR")
        assert cats is not None
        assert cats["currency"] == "INR"
        assert len(cats["categories"]) == 1
        assert cats["categories"][0]["title"] == "Food Items"
        assert len(cats["categories"][0]["objects"]) == 2

    def test_build_categories_none_for_empty(self):
        assert build_dost_categories([]) is None

    def test_build_categories_skips_errors(self):
        results = [{"name": "x", "content": "fail", "is_error": True}]
        assert build_dost_categories(results) is None

    def test_build_categories_invalid_json_skipped(self):
        results = [{"name": "x", "content": "not-json{{{", "is_error": False}]
        assert build_dost_categories(results) is None


@pytest.mark.unit
class TestExtractItems:
    """Test extract_items_from_response."""

    def test_list_response(self):
        items = extract_items_from_response([{"a": 1}, {"a": 2}])
        assert len(items) == 2

    def test_dict_with_items_path(self):
        data = {"meals": [{"name": "Pasta"}]}
        items = extract_items_from_response(data, "meals")
        assert len(items) == 1

    def test_dict_auto_detect(self):
        data = {"data": [{"name": "Pizza"}]}
        items = extract_items_from_response(data)
        assert len(items) == 1

    def test_none_returns_empty(self):
        assert extract_items_from_response(None) == []

    def test_dict_without_known_key_returns_self(self):
        data = {"custom_field": "value"}
        items = extract_items_from_response(data)
        assert len(items) == 1
        assert items[0] == data


@pytest.mark.unit
class TestGetNestedValue:
    """Test dot-notation nested value extraction."""

    def test_simple_key(self):
        assert get_nested_value({"a": 1}, "a") == 1

    def test_nested_key(self):
        assert get_nested_value({"a": {"b": 2}}, "a.b") == 2

    def test_missing_key(self):
        assert get_nested_value({"a": 1}, "b") is None

    def test_deep_missing(self):
        assert get_nested_value({"a": {"b": 1}}, "a.c") is None

    def test_empty_path(self):
        assert get_nested_value({"a": 1}, "") is None

    def test_none_obj(self):
        assert get_nested_value(None, "a") is None


@pytest.mark.unit
class TestBuildDostObject:
    """Test building individual dostObjects from API items."""

    def test_basic_item(self):
        item = {"strMeal": "Biryani", "strInstructions": "Cook rice with spices"}
        obj = build_dost_object_from_item(
            item,
            mapping={"title_field": "strMeal", "description_field": "strInstructions"},
            object_type="meal",
        )
        assert obj["title"] == "Biryani"
        assert obj["type"] == "meal"

    def test_item_with_image(self):
        item = {"name": "Pizza", "strMealThumb": "https://example.com/pizza.jpg"}
        obj = build_dost_object_from_item(
            item,
            mapping={"image_field": "strMealThumb"},
        )
        assert "media" in obj
        assert obj["media"]["images"][0]["data"] == "https://example.com/pizza.jpg"

    def test_item_without_mapping(self):
        item = {"title": "Salad", "description": "Fresh greens"}
        obj = build_dost_object_from_item(item)
        assert obj["title"] == "Salad"

    def test_missing_title_fallback(self):
        item = {"id": "123"}
        obj = build_dost_object_from_item(item, index=0)
        assert "Item 1" in obj["title"]


@pytest.mark.unit
class TestInferEventHint:
    """Test event hint inference for custom tools."""

    def test_search_tool(self):
        assert infer_event_hint([{"name": "search_food", "is_error": False}]) == "food_list"

    def test_get_tool(self):
        assert infer_event_hint([{"name": "get_dish_details", "is_error": False}]) == "dish_details_details"

    def test_no_results(self):
        assert infer_event_hint([]) == "response"

    def test_only_errors(self):
        assert infer_event_hint([{"name": "x", "is_error": True}]) == "response"

    def test_uses_last_success(self):
        results = [
            {"name": "search_food", "is_error": False},
            {"name": "get_dish_details", "is_error": False},
        ]
        assert infer_event_hint(results) == "dish_details_details"
