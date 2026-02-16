# ============================================================================
# FILE: mcp/llm/tool_converter.py
# ============================================================================
"""
Convert MCP tools to OpenAI function calling format.

MCP tools have:
  - name: str
  - description: str
  - input_schema: dict (JSON Schema)

OpenAI function calling expects:
  - type: "function"
  - function:
      - name: str
      - description: str
      - parameters: dict (JSON Schema)
"""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client.mcp_client import MCPTool


def mcp_to_openai_tools(mcp_tools: List["MCPTool"]) -> List[Dict[str, Any]]:
    """
    Convert MCP tools to OpenAI function calling format.

    Works with ANY MCP server - just transforms the schema format.

    Args:
        mcp_tools: List of MCPTool objects from list_tools()

    Returns:
        List of OpenAI function definitions
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Call the {tool.name} tool",
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }
        for tool in mcp_tools
    ]
