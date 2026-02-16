# ============================================================================
# FILE: app/custom/client.py
# ============================================================================
"""
Custom Client - Unified interface that mimics MCPClient.

Provides list_tools() and call_tool() methods so the ReActAgent works
unchanged whether using MCP or REST APIs.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List

from .auth import AuthHandler
from .registry import RESTTool, ServiceConfig, load_tools_from_config
from .executor import RESTExecutor
from ..llm.agent import ToolResult

logger = logging.getLogger(__name__)


class CustomClient:
    """
    Client that mimics MCPClient interface for REST APIs.

    Provides:
    - list_tools(): Return registered tools
    - call_tool(name, arguments): Execute tool and return result
    """

    def __init__(self, config_path: str):
        """
        Initialize the CustomClient.

        Args:
            config_path: Path to YAML config file
        """
        self.config_path = config_path
        self.service_config: ServiceConfig = load_tools_from_config(config_path)
        self.auth = AuthHandler.from_dict(self.service_config.auth)
        self.executor = RESTExecutor(self.service_config.base_url, self.auth)

        logger.info(f"CustomClient initialized for {self.service_config.name}")
        logger.info(f"Base URL: {self.service_config.base_url}")
        logger.info(f"Tools: {[t.name for t in self.service_config.tools]}")

    @property
    def tools(self) -> List[RESTTool]:
        """Return registered tools."""
        return self.service_config.tools

    @property
    def service_name(self) -> str:
        """Return service name."""
        return self.service_config.name

    @property
    def base_url(self) -> str:
        """Return base URL."""
        return self.service_config.base_url

    async def list_tools(self) -> List[RESTTool]:
        """
        Return registered tools (mimics MCPClient.list_tools).

        Returns:
            List of RESTTool objects
        """
        return self.tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute tool and return result (mimics MCPClient.call_tool).

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolResult with content and is_error flag
        """
        # Find the tool
        tool = None
        for t in self.tools:
            if t.name == name:
                tool = t
                break

        if not tool:
            logger.error(f"Tool not found: {name}")
            return ToolResult(
                content=json.dumps({"error": f"Tool not found: {name}"}),
                is_error=True
            )

        try:
            # Execute the REST call
            result = await self.executor.execute(tool, arguments)

            return ToolResult(
                content=json.dumps(result),
                is_error=False
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                content=json.dumps({"error": str(e)}),
                is_error=True
            )

    def get_agent_config(self) -> Dict[str, Any]:
        """Return agent configuration from YAML."""
        return self.service_config.agent
