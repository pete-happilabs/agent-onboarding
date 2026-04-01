# ============================================================================
# FILE: app/llm/agent.py
# ============================================================================
"""
ReAct Agent - OpenAI-based agent with tool calling and metrics tracking.

Uses configurable prompts and tracks token usage for billing.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from openai import AsyncOpenAI

from .prompts import get_prompt
from .tool_converter import tools_to_openai_format

if TYPE_CHECKING:
    from ..custom.client import CustomClient

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution."""

    content: str
    is_error: bool = False


@dataclass
class AgentResult:
    """Result from ReAct agent execution."""

    text: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class ReActAgent:
    """
    ReAct agent using OpenAI function calling.

    Supports any client that implements list_tools() and call_tool().
    Tracks token usage for metrics.
    """

    def __init__(
        self,
        client: "CustomClient",
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        prompt_name: str = "default"
    ):
        """
        Initialize the ReAct agent.

        Args:
            client: CustomClient (or any client with list_tools/call_tool)
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)
            temperature: Temperature for generation
            prompt_name: Name of system prompt to use
        """
        self.client = client
        self.openai = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.system_prompt = get_prompt(prompt_name)

    async def run(self, user_message: str, max_iterations: int = 5) -> AgentResult:
        """
        Run the agent with a user message.

        Args:
            user_message: The user's message
            max_iterations: Max tool-calling iterations

        Returns:
            AgentResult with text, tool_results, and token counts
        """
        # Get tools and convert to OpenAI format
        tools = await self.client.list_tools()
        openai_tools = tools_to_openai_format(tools)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        total_input_tokens = 0
        total_output_tokens = 0
        all_tool_results = []

        for iteration in range(max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            # Call OpenAI
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
                temperature=self.temperature
            )

            # Track tokens
            if response.usage:
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens

            msg = response.choices[0].message

            # Add assistant message to history
            messages.append(msg.model_dump())

            # If no tool calls, we're done
            if not msg.tool_calls:
                return AgentResult(
                    text=msg.content or "",
                    tool_results=all_tool_results,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    model=self.model
                )

            # Execute tool calls
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")

                try:
                    result = await self.client.call_tool(tool_name, tool_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content
                    })

                    all_tool_results.append({
                        "name": tool_name,
                        "args": tool_args,
                        "content": result.content,
                        "is_error": result.is_error,
                        "response_mapping": self._get_tool_mapping(tool_name)
                    })

                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    error_content = json.dumps({"error": str(e)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": error_content
                    })

                    all_tool_results.append({
                        "name": tool_name,
                        "args": tool_args,
                        "content": error_content,
                        "is_error": True
                    })

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return AgentResult(
            text="I couldn't complete the request within the allowed steps.",
            tool_results=all_tool_results,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            model=self.model
        )

    def _get_tool_mapping(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get response mapping for a tool if available."""
        try:
            for tool in self.client.tools:
                if tool.name == tool_name:
                    return tool.response_mapping
        except Exception:
            pass
        return None
