"""
Unit tests for Airbnb agent configuration (MCP template).

Tests:
  - YAML config parsing
  - MCP settings structure
  - Transport configuration
  - Agent entity ID
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp"))

from app.config import Settings


@pytest.fixture
def airbnb_settings():
    config_path = str(Path(__file__).parent.parent.parent / "config.yaml")
    return Settings(config_path=config_path)


@pytest.mark.unit
class TestAirbnbMCPConfig:
    """Test Airbnb MCP configuration."""

    def test_settings_loads(self, airbnb_settings):
        assert airbnb_settings is not None

    def test_transport_is_stdio(self, airbnb_settings):
        assert airbnb_settings.mcp.transport == "stdio"

    def test_command_contains_airbnb(self, airbnb_settings):
        cmd = airbnb_settings.mcp.get_effective_command()
        assert "airbnb" in cmd.lower()

    def test_timeout(self, airbnb_settings):
        assert airbnb_settings.mcp.timeout == 60

    def test_llm_enabled(self, airbnb_settings):
        assert airbnb_settings.llm.enabled is True

    def test_llm_model(self, airbnb_settings):
        assert airbnb_settings.llm.model == "gpt-4o-mini"

    def test_llm_temperature(self, airbnb_settings):
        assert airbnb_settings.llm.temperature == 0.0

    def test_agent_entity_id(self, airbnb_settings):
        assert airbnb_settings.agent.entity_id == "agent.mcp.airbnb"

    def test_agent_name(self, airbnb_settings):
        assert airbnb_settings.agent.name == "Airbnb"


@pytest.mark.unit
class TestMCPTransportClasses:
    """Test MCP transport layer classes."""

    def test_stdio_transport_init(self):
        from app.client.transport import StdioTransport
        t = StdioTransport("echo hello", timeout=10)
        assert t.command == "echo hello"
        assert t.timeout == 10
        assert t._process is None

    def test_sse_transport_init(self):
        from app.client.transport import SSETransport
        t = SSETransport("http://localhost:3000/sse", timeout=15)
        assert t.url == "http://localhost:3000/sse"
        assert t.timeout == 15

    def test_sse_rejects_non_http(self):
        from app.client.transport import SSETransport
        with pytest.raises(ValueError, match="http"):
            SSETransport("ftp://example.com/sse")

    def test_sse_strips_trailing_slash(self):
        from app.client.transport import SSETransport
        t = SSETransport("http://localhost:3000/sse/")
        assert t.url == "http://localhost:3000/sse"

    def test_transport_abc(self):
        from app.client.transport import Transport
        import abc
        assert hasattr(Transport, "connect")
        assert hasattr(Transport, "send")
        assert hasattr(Transport, "close")
