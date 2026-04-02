"""
Unit tests for Zomato agent configuration and YAML tool registry.

Tests:
  - YAML config parsing via registry.py
  - ServiceConfig structure
  - Tool definitions (6 tools)
  - Response mappings
  - Path validation security
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "custom"))

from app.custom.registry import (
    load_tools_from_config,
    _parse_tool,
    list_tools,
    get_tool,
    ServiceConfig,
    RESTTool,
    RESTParameter,
)


@pytest.fixture
def zomato_config_path():
    return str(Path(__file__).parent.parent.parent / "config.yaml")


@pytest.fixture
def service_config(zomato_config_path):
    return load_tools_from_config(zomato_config_path)


@pytest.mark.unit
class TestLoadZomatoConfig:
    """Test loading Zomato YAML config."""

    def test_load_succeeds(self, zomato_config_path):
        config = load_tools_from_config(zomato_config_path)
        assert isinstance(config, ServiceConfig)

    def test_service_name(self, service_config):
        assert service_config.name == "zomato"

    def test_base_url(self, service_config):
        assert "themealdb.com" in service_config.base_url
        assert not service_config.base_url.endswith("/")

    def test_auth_type_none(self, service_config):
        assert service_config.auth.get("type") == "none"

    def test_agent_config(self, service_config):
        assert service_config.agent.get("prompt_name") == "food_delivery"


@pytest.mark.unit
class TestZomatoToolDefinitions:
    """Test that all 6 Zomato tools are correctly defined."""

    def test_six_tools_loaded(self, service_config):
        assert len(service_config.tools) == 6

    def test_tool_names(self, service_config):
        names = list_tools(service_config)
        expected = [
            "search_food", "browse_by_category", "browse_by_cuisine",
            "get_dish_details", "surprise_me", "list_all_categories",
        ]
        assert sorted(names) == sorted(expected)

    def test_search_food_tool(self, service_config):
        tool = get_tool(service_config, "search_food")
        assert tool is not None
        assert tool.method == "GET"
        assert "/search.php" in tool.endpoint
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "s"
        assert tool.parameters[0].required is True
        assert tool.parameters[0].location == "query"

    def test_browse_by_category_tool(self, service_config):
        tool = get_tool(service_config, "browse_by_category")
        assert tool is not None
        assert tool.method == "GET"
        assert "/filter.php" in tool.endpoint
        assert tool.parameters[0].name == "c"

    def test_browse_by_cuisine_tool(self, service_config):
        tool = get_tool(service_config, "browse_by_cuisine")
        assert tool is not None
        assert tool.parameters[0].name == "a"

    def test_get_dish_details_tool(self, service_config):
        tool = get_tool(service_config, "get_dish_details")
        assert tool is not None
        assert "/lookup.php" in tool.endpoint
        assert tool.parameters[0].name == "i"

    def test_surprise_me_no_params(self, service_config):
        tool = get_tool(service_config, "surprise_me")
        assert tool is not None
        assert len(tool.parameters) == 0
        assert "/random.php" in tool.endpoint

    def test_list_all_categories_no_params(self, service_config):
        tool = get_tool(service_config, "list_all_categories")
        assert tool is not None
        assert len(tool.parameters) == 0
        assert "/categories.php" in tool.endpoint

    def test_nonexistent_tool_returns_none(self, service_config):
        assert get_tool(service_config, "order_food") is None


@pytest.mark.unit
class TestResponseMappings:
    """Test that response_mapping is set for each tool."""

    def test_search_food_mapping(self, service_config):
        tool = get_tool(service_config, "search_food")
        m = tool.response_mapping
        assert m is not None
        assert m["items_path"] == "meals"
        assert m["title_field"] == "strMeal"
        assert m["description_field"] == "strInstructions"
        assert m["image_field"] == "strMealThumb"

    def test_categories_mapping(self, service_config):
        tool = get_tool(service_config, "list_all_categories")
        m = tool.response_mapping
        assert m["items_path"] == "categories"
        assert m["title_field"] == "strCategory"

    def test_all_tools_have_category_title(self, service_config):
        for tool in service_config.tools:
            if tool.response_mapping:
                assert "category_title" in tool.response_mapping, f"{tool.name} missing category_title"


@pytest.mark.unit
class TestPathValidation:
    """Test config path validation security."""

    def test_nonexistent_file_raises(self):
        # Use a path within the repo that doesn't exist
        fake_path = str(Path(__file__).parent.parent.parent / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            load_tools_from_config(fake_path)

    def test_outside_repo_raises_value_error(self):
        with pytest.raises(ValueError, match="project directory"):
            load_tools_from_config("/tmp/does_not_exist.yaml")

    def test_non_yaml_raises(self):
        # Create a .txt file within the repo directory
        repo_dir = Path(__file__).parent.parent.parent
        txt = repo_dir / "_test_config.txt"
        txt.write_text("hello")
        try:
            with pytest.raises(ValueError, match="YAML"):
                load_tools_from_config(str(txt))
        finally:
            txt.unlink()


@pytest.mark.unit
class TestParseToolDirect:
    """Test _parse_tool with raw dicts."""

    def test_minimal_tool(self):
        tool = _parse_tool({"name": "test_tool"})
        assert tool.name == "test_tool"
        assert tool.method == "POST"
        assert tool.endpoint == "/test_tool"

    def test_tool_with_params(self):
        tool = _parse_tool({
            "name": "search",
            "method": "GET",
            "endpoint": "/search",
            "parameters": [
                {"name": "q", "type": "string", "required": True, "in": "query"},
            ],
        })
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "q"
        assert tool.parameters[0].required is True
        assert tool.parameters[0].location == "query"

    def test_tool_without_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            _parse_tool({})

    def test_method_uppercased(self):
        tool = _parse_tool({"name": "t", "method": "get"})
        assert tool.method == "GET"
