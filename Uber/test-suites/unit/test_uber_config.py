"""
Unit tests for Uber domain configuration and agent setup.
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "generic"))

from app.domains.uber.config import UberConfig, SYSTEM_PROMPT
from app.domains import get_domain_config, DOMAIN_REGISTRY
from app.config.domain_config import BaseDomainConfig


@pytest.mark.unit
class TestUberConfig:
    """Test UberConfig dataclass."""

    def test_uber_in_domain_registry(self):
        assert "uber" in DOMAIN_REGISTRY

    def test_get_domain_config_returns_uber(self):
        config = get_domain_config("uber")
        assert isinstance(config, BaseDomainConfig)
        assert config.domain_name == "uber"

    def test_entity_id(self):
        config = UberConfig()
        assert config.entity_id == "com.uber.rides"

    def test_tools_module(self):
        config = UberConfig()
        assert config.tools_module == "app.domains.uber.tools"

    def test_currency(self):
        config = UberConfig()
        assert config.currency == "INR"

    def test_vector_search_disabled(self):
        config = UberConfig()
        assert config.enable_vector_search is False

    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_mentions_tools(self):
        for tool_name in ["search_rides", "list_ride_types", "get_ride_details", "book_ride", "get_ride_status"]:
            assert tool_name in SYSTEM_PROMPT

    def test_system_prompt_mentions_plain_text(self):
        assert "PLAIN TEXT" in SYSTEM_PROMPT

    def test_invalid_domain_raises(self):
        with pytest.raises(ValueError):
            get_domain_config("nonexistent_domain")


@pytest.mark.unit
class TestAllowedToolsModule:
    """Test that the Uber tools module is in the allowlist."""

    def test_uber_tools_module_allowed(self):
        from app.core.generic_agent import GenericReActAgent
        # Check the class-level constant
        # We can't instantiate without LLM, but we can check the source
        import inspect
        source = inspect.getsource(GenericReActAgent.__init__)
        assert "app.domains.uber.tools" in source
