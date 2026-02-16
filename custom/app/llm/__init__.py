# ============================================================================
# FILE: app/llm/__init__.py
# ============================================================================
"""
LLM Module - ReAct Agent and Tool Conversion.

Contains:
- ReActAgent: OpenAI-based agent with tool calling and metrics tracking
- Tool converters: REST tools to OpenAI format
- Response formatter: API responses to dostObjects
- Configurable prompts: Change agent behavior via prompts
"""

from .prompts import get_prompt, DEFAULT_SYSTEM_PROMPT, register_prompt, list_prompts
from .tool_converter import tools_to_openai_format
from .response_formatter import build_dost_categories, infer_event_hint
from .agent import ReActAgent, AgentResult, ToolResult

__all__ = [
    "get_prompt",
    "DEFAULT_SYSTEM_PROMPT",
    "register_prompt",
    "list_prompts",
    "tools_to_openai_format",
    "build_dost_categories",
    "infer_event_hint",
    "ReActAgent",
    "AgentResult",
    "ToolResult",
]
