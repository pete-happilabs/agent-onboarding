# ============================================================================
# FILE: mcp/llm/__init__.py
# ============================================================================
"""
LLM module for natural language to MCP tool translation.

Provides ReAct agent that:
1. Takes natural language user messages
2. Dynamically discovers MCP tools via list_tools()
3. Reasons about which tool to call
4. Executes tools via call_tool()
5. Formats responses for users
"""

from .agent import ReActAgent, AgentResult
from .response_formatter import build_dost_categories, infer_event_hint

__all__ = ["ReActAgent", "AgentResult", "build_dost_categories", "infer_event_hint"]
