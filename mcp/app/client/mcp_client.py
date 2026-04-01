# ============================================================================
# FILE: mcp/client/mcp_client.py
# ============================================================================
"""
MCP Client - Connect to external MCP servers.

This client implements the MCP JSON-RPC protocol to communicate
with existing MCP servers (like Zomato's).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .transport import Transport, StdioTransport, SSETransport

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool (capability)."""

    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPToolResult:
    """Result from calling an MCP tool."""

    content: str
    is_error: bool = False


class MCPClient:
    """
    MCP Client - connects to external MCP servers.

    Supports three transport modes:
    - stdio: Local MCP server via subprocess
    - remote: Remote MCP server via mcp-remote (handles OAuth)
    - sse: Direct HTTP/SSE connection

    Usage:
        # Local MCP server
        client = MCPClient(transport="stdio", command="npx @some/mcp-server")

        # Remote MCP server (like Zomato) - uses mcp-remote
        client = MCPClient(transport="remote", url="https://mcp-server.zomato.com/mcp")

        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("search_restaurants", {"query": "pizza"})
        await client.close()
    """

    def __init__(
        self,
        transport: str = "stdio",
        command: Optional[str] = None,
        url: Optional[str] = None,
        timeout: int = 30,
        # Remote-specific options
        oauth_port: int = 3334,
        auth_timeout: int = 60,
        headers: Optional[List[str]] = None,
        transport_mode: str = "http-first",
    ):
        """
        Initialize MCP client.

        Args:
            transport: "stdio", "remote", or "sse"
            command: Command to run for stdio transport
            url: URL for remote/sse transport
            timeout: Request timeout in seconds
            oauth_port: Port for OAuth callback (remote only)
            auth_timeout: OAuth timeout in seconds (remote only)
            headers: Custom headers for auth (remote only)
            transport_mode: http-first, sse-first, http-only, sse-only (remote only)
        """
        self.transport_type = transport
        self.timeout = timeout

        # Create transport based on type
        if transport == "stdio":
            if not command:
                raise ValueError("command is required for stdio transport")
            self._transport: Transport = StdioTransport(command, timeout)

        elif transport == "remote":
            # Build mcp-remote command
            if not url:
                raise ValueError("url is required for remote transport")
            remote_command = self._build_remote_command(
                url, oauth_port, auth_timeout, headers, transport_mode
            )
            logger.info(f"Using mcp-remote: {remote_command}")
            self._transport = StdioTransport(remote_command, timeout)

        elif transport == "sse":
            if not url:
                raise ValueError("url is required for sse transport")
            self._transport = SSETransport(url, timeout)

        else:
            raise ValueError(f"Unknown transport: {transport}")

        self._tools: Optional[List[MCPTool]] = None
        self._connected = False

    def _build_remote_command(
        self,
        url: str,
        oauth_port: int,
        auth_timeout: int,
        headers: Optional[List[str]],
        transport_mode: str,
    ) -> str:
        """Build the mcp-remote command for remote MCP servers."""
        import shlex

        args = ["npx", "mcp-remote@latest", url]

        # Add OAuth port
        args.append(str(oauth_port))

        # Add transport mode
        args.extend(["--transport", transport_mode])

        # Add auth timeout
        args.extend(["--auth-timeout", str(auth_timeout)])

        # Add custom headers (shell-escape each value to prevent injection)
        if headers:
            for header in headers:
                args.extend(["--header", header])

        return " ".join(shlex.quote(arg) for arg in args)

    async def connect(self) -> None:
        """Connect to the MCP server and initialize."""
        await self._transport.connect()
        self._connected = True

        # Initialize the MCP connection
        await self._initialize()

        logger.info("MCP client connected and initialized")

    async def _initialize(self) -> Dict[str, Any]:
        """Send initialize request to MCP server."""
        response = await self._transport.send({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-dost-bridge",
                    "version": "0.1.0"
                }
            }
        })

        if "error" in response:
            raise RuntimeError(f"MCP initialize failed: {response['error']}")

        # Send initialized notification (no response expected for notifications)
        # For notifications, we don't include an "id" field
        if isinstance(self._transport, StdioTransport):
            # Write directly without expecting response
            import json
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            if self._transport._process and self._transport._process.stdin:
                request_bytes = (json.dumps(notification) + "\n").encode()
                self._transport._process.stdin.write(request_bytes)
                await self._transport._process.stdin.drain()
                logger.debug("Sent initialized notification")

        return response.get("result", {})

    async def list_tools(self) -> List[MCPTool]:
        """Get available tools from the MCP server."""
        if not self._connected:
            raise RuntimeError("Client not connected")

        if self._tools is not None:
            return self._tools

        response = await self._transport.send({
            "jsonrpc": "2.0",
            "method": "tools/list"
        })

        if "error" in response:
            raise RuntimeError(f"MCP list_tools failed: {response['error']}")

        tools_data = response.get("result", {}).get("tools", [])
        self._tools = [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {})
            )
            for t in tools_data
        ]

        logger.info(f"Found {len(self._tools)} MCP tools")
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """
        Call an MCP tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            MCPToolResult with content and error status
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        logger.info(f"Calling MCP tool: {name}")

        response = await self._transport.send({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        })

        if "error" in response:
            error = response["error"]
            return MCPToolResult(
                content=f"Error: {error.get('message', str(error))}",
                is_error=True
            )

        result = response.get("result", {})
        content_list = result.get("content", [])

        # Extract text content
        text_parts = []
        for item in content_list:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))

        return MCPToolResult(
            content="\n".join(text_parts) if text_parts else str(result),
            is_error=result.get("isError", False)
        )

    async def send_message(self, message: str) -> str:
        """
        Send a message to the MCP server.

        This is a convenience method that:
        1. Lists available tools
        2. Tries to find a relevant tool based on the message
        3. Calls the tool and returns the result

        For simple MCP servers, this provides a chat-like interface.

        Args:
            message: User's message

        Returns:
            Response from MCP server
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        # Get available tools
        tools = await self.list_tools()

        if not tools:
            return "No tools available on this MCP server."

        # For now, we'll use a simple heuristic:
        # If there's only one tool, use it
        # If there are multiple, try to find a "chat" or "query" tool
        # Otherwise, list available tools

        # Look for a chat/query/search tool
        chat_tools = [t for t in tools if any(
            keyword in t.name.lower()
            for keyword in ["chat", "query", "search", "ask", "message"]
        )]

        if chat_tools:
            tool = chat_tools[0]
            result = await self.call_tool(tool.name, {"query": message, "message": message})
            return result.content

        # If only one tool, use it with the message
        if len(tools) == 1:
            tool = tools[0]
            # Try common parameter names
            result = await self.call_tool(tool.name, {
                "query": message,
                "input": message,
                "text": message,
                "message": message
            })
            return result.content

        # Multiple tools - list them
        tool_list = "\n".join(f"- {t.name}: {t.description}" for t in tools)
        return f"Available tools:\n{tool_list}\n\nPlease specify which tool to use."

    async def close(self) -> None:
        """Close the connection to the MCP server."""
        if self._connected:
            await self._transport.close()
            self._connected = False
            logger.info("MCP client closed")


# Singleton client instance
_MCP_CLIENT: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _MCP_CLIENT
    if _MCP_CLIENT is None:
        from ..config import get_settings
        settings = get_settings()
        _MCP_CLIENT = MCPClient(
            transport=settings.mcp.transport,
            command=settings.mcp.command,
            url=settings.mcp.url,
            timeout=settings.mcp.timeout,
            # Remote-specific options
            oauth_port=settings.mcp.oauth_port,
            auth_timeout=settings.mcp.auth_timeout,
            headers=settings.mcp.headers,
            transport_mode=settings.mcp.transport_mode,
        )
    return _MCP_CLIENT


async def initialize_mcp_client() -> MCPClient:
    """Initialize and connect the global MCP client."""
    client = get_mcp_client()
    if not client._connected:
        await client.connect()
    return client


def reset_mcp_client() -> None:
    """Reset the global MCP client (useful for testing)."""
    global _MCP_CLIENT
    _MCP_CLIENT = None
