# ============================================================================
# FILE: mcp/config.py
# ============================================================================
"""
Configuration loader for MCP Bridge.

Loads settings from mcp.yaml and environment variables.
No DPA keys needed - just MCP server connection details.

Supports three transport modes:
- stdio: Local MCP server via subprocess
- remote: Remote MCP server via mcp-remote (handles OAuth automatically)
- sse: Direct HTTP/SSE connection (no OAuth)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

import yaml
from dotenv import load_dotenv

# Load .env from mcp directory
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass(frozen=True)
class MCPConfig:
    """Configuration for connecting to external MCP server."""

    transport: str  # "stdio", "remote", or "sse"
    command: Optional[str]  # For stdio: command to run (e.g., "npx @some/mcp-server")
    url: Optional[str]  # For remote/sse: URL of the MCP server
    timeout: int  # Request timeout in seconds

    # Remote-specific options (for mcp-remote)
    oauth_port: int = 3334  # Port for OAuth callback
    auth_timeout: int = 60  # OAuth timeout in seconds
    headers: Optional[List[str]] = None  # Custom headers (e.g., ["Authorization: Bearer xxx"])
    transport_mode: str = "http-first"  # http-first, sse-first, http-only, sse-only

    def get_effective_command(self) -> str:
        """
        Get the actual command to run.

        For 'remote' transport, builds the mcp-remote command.
        For 'stdio' transport, returns the command as-is.
        """
        if self.transport == "remote":
            if not self.url:
                raise ValueError("URL is required for remote transport")

            # Build mcp-remote command
            args = ["npx", "-y", "mcp-remote@latest", self.url]

            # Add OAuth port
            args.append(str(self.oauth_port))

            # Add transport mode
            args.extend(["--transport", self.transport_mode])

            # Add auth timeout
            args.extend(["--auth-timeout", str(self.auth_timeout)])

            # Add custom headers
            if self.headers:
                for header in self.headers:
                    args.extend(["--header", header])

            return " ".join(args)

        elif self.transport == "stdio":
            if not self.command:
                raise ValueError("Command is required for stdio transport")
            return self.command

        else:
            raise ValueError(f"Cannot get command for transport: {self.transport}")


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM (OpenAI) to understand user messages."""

    enabled: bool  # Whether to use LLM for message processing
    provider: str  # "openai"
    model: str  # "gpt-4o-mini"
    api_key: Optional[str]  # OpenAI API key
    temperature: float = 0.0  # Lower = more deterministic


@dataclass(frozen=True)
class AgentConfig:
    """Agent identity for dostEvent responses."""

    entity_id: str  # e.g., "agent.mcp.zomato"
    name: str  # e.g., "Zomato"


@dataclass(frozen=True)
class ServerConfig:
    """WebSocket server configuration."""

    host: str
    port: int


class Settings:
    """
    Container for MCP Bridge configuration.
    Loads from mcp.yaml and environment variables.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path or os.getenv("MCP_CONFIG_PATH", "mcp.yaml")
        self._mcp: Optional[MCPConfig] = None
        self._llm: Optional[LLMConfig] = None
        self._agent: Optional[AgentConfig] = None
        self._server: Optional[ServerConfig] = None
        self._config_data: Optional[dict] = None

    def _load_config(self) -> dict:
        """Load YAML configuration file."""
        if self._config_data is None:
            config_file = Path(self._config_path)
            if config_file.exists():
                with open(config_file) as f:
                    self._config_data = yaml.safe_load(f) or {}
            else:
                self._config_data = {}
        return self._config_data

    @property
    def mcp(self) -> MCPConfig:
        """MCP server connection settings."""
        if self._mcp is None:
            config = self._load_config()
            mcp_config = config.get("mcp", {})

            # Parse headers from config or env
            headers = mcp_config.get("headers")
            if headers is None:
                env_headers = os.getenv("MCP_HEADERS")
                if env_headers:
                    headers = [h.strip() for h in env_headers.split(";") if h.strip()]

            self._mcp = MCPConfig(
                transport=mcp_config.get("transport", os.getenv("MCP_TRANSPORT", "stdio")),
                command=mcp_config.get("command", os.getenv("MCP_COMMAND")),
                url=mcp_config.get("url", os.getenv("MCP_SERVER_URL")),
                timeout=int(mcp_config.get("timeout", os.getenv("MCP_TIMEOUT", "30"))),
                # Remote-specific options
                oauth_port=int(mcp_config.get("oauth_port", os.getenv("MCP_OAUTH_PORT", "3334"))),
                auth_timeout=int(mcp_config.get("auth_timeout", os.getenv("MCP_AUTH_TIMEOUT", "60"))),
                headers=headers,
                transport_mode=mcp_config.get("transport_mode", os.getenv("MCP_TRANSPORT_MODE", "http-first")),
            )
        return self._mcp

    @property
    def llm(self) -> LLMConfig:
        """LLM settings for natural language processing."""
        if self._llm is None:
            config = self._load_config()
            llm_config = config.get("llm", {})

            # Check if LLM is enabled (default: True if API key exists)
            api_key = llm_config.get("api_key", os.getenv("OPENAI_API_KEY"))
            enabled = llm_config.get("enabled", api_key is not None)

            self._llm = LLMConfig(
                enabled=enabled,
                provider=llm_config.get("provider", os.getenv("LLM_PROVIDER", "openai")),
                model=llm_config.get("model", os.getenv("LLM_MODEL", "gpt-4o-mini")),
                api_key=api_key,
                temperature=float(llm_config.get("temperature", os.getenv("LLM_TEMPERATURE", "0.0"))),
            )
        return self._llm

    @property
    def agent(self) -> AgentConfig:
        """Agent identity settings."""
        if self._agent is None:
            config = self._load_config()
            agent_config = config.get("agent", {})

            self._agent = AgentConfig(
                entity_id=agent_config.get("entity_id", os.getenv("AGENT_ENTITY_ID", "agent.mcp.bridge")),
                name=agent_config.get("name", os.getenv("AGENT_NAME", "MCP Bridge")),
            )
        return self._agent

    @property
    def server(self) -> ServerConfig:
        """WebSocket server settings."""
        if self._server is None:
            config = self._load_config()
            server_config = config.get("server", {})

            self._server = ServerConfig(
                host=server_config.get("host", os.getenv("MCP_BRIDGE_HOST", "0.0.0.0")),
                port=int(server_config.get("port", os.getenv("MCP_BRIDGE_PORT", "8003"))),
            )
        return self._server


# Global settings instance (can be replaced for testing)
_SETTINGS: Optional[Settings] = None


def get_settings(config_path: Optional[str] = None) -> Settings:
    """Get or create the global settings instance."""
    global _SETTINGS
    if _SETTINGS is None or config_path is not None:
        _SETTINGS = Settings(config_path)
    return _SETTINGS


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _SETTINGS
    _SETTINGS = None


__all__ = [
    "AgentConfig",
    "LLMConfig",
    "MCPConfig",
    "ServerConfig",
    "Settings",
    "get_settings",
    "reset_settings",
]
