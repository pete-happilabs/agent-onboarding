# ============================================================================
# FILE: app/custom/executor.py
# ============================================================================
"""
REST Executor - Execute HTTP requests to REST APIs.

Handles parameter placement (path, query, body, header) and auth headers.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, Any, Optional

import httpx

from .auth import AuthHandler
from .registry import RESTTool

logger = logging.getLogger(__name__)

# Default timeout for API calls (in seconds)
DEFAULT_TIMEOUT = 30.0


class RESTExecutor:
    """
    Execute REST API calls for tools.

    Handles:
    - Parameter substitution in path
    - Query parameters
    - Request body
    - Headers (including auth)
    """

    def __init__(
        self,
        base_url: str,
        auth: AuthHandler,
        timeout: float = DEFAULT_TIMEOUT,
        default_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the REST executor.

        Args:
            base_url: Base URL for all API calls
            auth: AuthHandler for authentication
            timeout: Request timeout in seconds
            default_headers: Default headers for all requests
        """
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.default_headers = default_headers or {}

    async def execute(
        self,
        tool: RESTTool,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a REST API call for a tool.

        Args:
            tool: RESTTool definition
            arguments: Arguments passed from LLM

        Returns:
            API response as dict

        Raises:
            httpx.HTTPError: If the request fails
        """
        # Build URL with path parameters
        url = self._build_url(tool.endpoint, arguments)

        # Separate parameters by location
        query_params = {}
        body_params = {}
        headers = dict(self.default_headers)

        # Add tool-specific headers
        if tool.headers:
            headers.update(tool.headers)

        # Add auth headers
        headers.update(self.auth.get_headers())

        # Process parameters
        for param in tool.parameters:
            value = arguments.get(param.name)
            if value is None:
                if param.default is not None:
                    value = param.default
                elif param.required:
                    raise ValueError(f"Missing required parameter: {param.name}")
                else:
                    continue

            if param.location == "path":
                # Already handled in _build_url
                pass
            elif param.location == "query":
                query_params[param.name] = value
            elif param.location == "header":
                headers[param.name] = str(value)
            else:  # body
                body_params[param.name] = value

        # Make the request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(f"Executing {tool.method} {url}")

            if tool.method in ("GET", "DELETE"):
                response = await client.request(
                    method=tool.method,
                    url=url,
                    params=query_params or None,
                    headers=headers
                )
            else:
                # POST, PUT, PATCH with body
                headers["Content-Type"] = "application/json"
                response = await client.request(
                    method=tool.method,
                    url=url,
                    params=query_params or None,
                    json=body_params or None,
                    headers=headers
                )

            # Log response status
            logger.info(f"Response: {response.status_code}")

            # Raise for error status codes
            response.raise_for_status()

            # Parse response
            try:
                return response.json()
            except json.JSONDecodeError:
                # Return text response wrapped in dict
                return {"text": response.text, "status_code": response.status_code}

    def _build_url(self, endpoint: str, arguments: Dict[str, Any]) -> str:
        """
        Build URL with path parameter substitution.

        Handles patterns like:
        - /rides/{ride_id}/cancel
        - /users/{user_id}

        Args:
            endpoint: Endpoint template
            arguments: Arguments dict

        Returns:
            Full URL with path params substituted
        """
        # Find all {param} patterns
        path_params = re.findall(r"\{(\w+)\}", endpoint)

        url = endpoint
        for param in path_params:
            if param in arguments:
                url = url.replace(f"{{{param}}}", str(arguments[param]))
            else:
                raise ValueError(f"Missing path parameter: {param}")

        return f"{self.base_url}{url}"


async def execute_tool(
    tool: RESTTool,
    arguments: Dict[str, Any],
    base_url: str,
    auth: AuthHandler
) -> Dict[str, Any]:
    """
    Convenience function to execute a tool without creating an executor.

    Args:
        tool: RESTTool definition
        arguments: Arguments dict
        base_url: Base URL
        auth: AuthHandler

    Returns:
        API response
    """
    executor = RESTExecutor(base_url, auth)
    return await executor.execute(tool, arguments)
