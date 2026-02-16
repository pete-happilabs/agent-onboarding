# ============================================================================
# FILE: mcp/client/transport.py
# ============================================================================
"""
MCP Transport Layer - stdio and SSE transports.

Handles the low-level communication with MCP servers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class Transport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        pass

    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC message and receive the response."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass


class StdioTransport(Transport):
    """
    Stdio transport - runs MCP server as subprocess.

    Used for MCP servers that communicate via stdin/stdout.
    Example: npx @modelcontextprotocol/server-everything
    Example: npx -y mcp-remote@latest https://mcp-server.zomato.com/mcp
    """

    def __init__(self, command: str, timeout: int = 30):
        self.command = command
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0

    async def connect(self) -> None:
        """Start the MCP server subprocess."""
        logger.info(f"Starting MCP server: {self.command}")

        import shlex
        import os

        # Parse command properly (handles quotes and special chars)
        parts = shlex.split(self.command)

        # Get current environment and ensure PATH includes npm/node
        env = os.environ.copy()

        self._process = await asyncio.create_subprocess_exec(
            *parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        logger.info(f"MCP server started (PID: {self._process.pid})")

        # Start a task to log stderr
        asyncio.create_task(self._log_stderr())

    async def _log_stderr(self) -> None:
        """Log stderr output from the subprocess."""
        if self._process is None or self._process.stderr is None:
            return
        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                stderr_text = line.decode().strip()
                if stderr_text:
                    # Check if it's an OAuth-related message
                    if "oauth" in stderr_text.lower() or "auth" in stderr_text.lower():
                        logger.info(f"MCP Auth: {stderr_text}")
                    else:
                        logger.debug(f"MCP stderr: {stderr_text}")
        except Exception as e:
            logger.debug(f"Stderr reader stopped: {e}")

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC message via stdin and read response from stdout."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Transport not connected")

        # Add request ID if not present
        self._request_id += 1
        if "id" not in message:
            message["id"] = self._request_id

        expected_id = message.get("id")

        # Send message
        request_bytes = (json.dumps(message) + "\n").encode()
        self._process.stdin.write(request_bytes)
        await self._process.stdin.drain()

        logger.debug(f"Sent: {message}")

        # Read responses until we get the one with matching ID
        # (server may send notifications before the actual response)
        try:
            while True:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=self.timeout
                )

                if not response_line:
                    raise RuntimeError("MCP server closed connection")

                response = json.loads(response_line.decode())
                logger.debug(f"Received: {response}")

                # Check if this is a notification (no id) or a response
                if "id" not in response:
                    # It's a notification, skip it and keep reading
                    logger.debug(f"Skipping notification: {response.get('method', 'unknown')}")
                    continue

                # Check if ID matches
                if response.get("id") == expected_id:
                    return response

                # Different ID - unexpected, but log and continue
                logger.warning(f"Received response with unexpected ID: {response.get('id')} (expected {expected_id})")

        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP server did not respond within {self.timeout}s")

    async def close(self) -> None:
        """Terminate the subprocess."""
        if self._process is not None:
            logger.info("Closing MCP server subprocess")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None


class SSETransport(Transport):
    """
    SSE transport - connects to HTTP MCP server.

    Used for MCP servers that expose HTTP endpoints.
    Example: http://localhost:3000/sse
    """

    def __init__(self, url: str, timeout: int = 30):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def connect(self) -> None:
        """Initialize HTTP client."""
        logger.info(f"Connecting to MCP server: {self.url}")
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC message via HTTP POST."""
        if self._client is None:
            raise RuntimeError("Transport not connected")

        # Add request ID if not present
        self._request_id += 1
        if "id" not in message:
            message["id"] = self._request_id

        logger.debug(f"Sending to {self.url}: {message}")

        # Send as POST request
        response = await self._client.post(
            self.url,
            json=message,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        result = response.json()
        logger.debug(f"Received: {result}")
        return result

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            logger.info("Closing HTTP client")
            await self._client.aclose()
            self._client = None
