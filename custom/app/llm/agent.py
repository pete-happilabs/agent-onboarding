# ============================================================================
# FILE: app/llm/agent.py
# ============================================================================
"""
ReAct Agent - OpenAI-based agent with tool calling and metrics tracking.

Production additions over original:
- Retry with exponential backoff on OpenAI API calls (handles rate limits,
  transient 500s, and network blips — up to 3 attempts, 1s→8s backoff)
- CircuitBreakerOpen re-raised from tool loop so talk() can handle it
  with a user-friendly "service unavailable" message instead of swallowing it
- % logging replaced f-strings for production log safety
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .prompts import get_prompt
from .tool_converter import tools_to_openai_format
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "../../..")))
from shared.shared_breaker import CircuitBreakerOpen


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
        prompt_name: str = "default",
    ):
        self.client = client
        self.openai = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.system_prompt = get_prompt(prompt_name)

        # Wrap the raw OpenAI call with retry at construction time.
        # tenacity wraps the bound method — self is already captured.
        # Retries up to 3 times: 1s → 2s → 4s → 8s (capped) backoff.
        self._create_completion = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )(self._raw_create_completion)

    async def _raw_create_completion(
        self,
        messages: list,
        openai_tools: list,
    ) -> Any:
        """
        Single OpenAI API call — no retry logic here.
        Retry is applied by wrapping this in __init__.
        """
        return await self.openai.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
            temperature=self.temperature,
        )

    async def run(self, user_message: str, max_iterations: int = 5) -> AgentResult:
        """
        Run the ReAct loop with a user message.

        Args:
            user_message:   The user's message.
            max_iterations: Maximum tool-calling iterations (default: 5).

        Returns:
            AgentResult with response text, tool results, and token counts.
        """
        tools = await self.client.list_tools()
        openai_tools = tools_to_openai_format(tools)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        total_input_tokens = 0
        total_output_tokens = 0
        all_tool_results = []

        for iteration in range(max_iterations):
            logger.debug("Agent iteration %d/%d", iteration + 1, max_iterations)

            # Call OpenAI — retry handles transient failures automatically
            response = await self._create_completion(messages, openai_tools)

            if response.usage:
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens

            msg = response.choices[0].message
            messages.append(msg.model_dump())

            # No tool calls → final answer
            if not msg.tool_calls:
                return AgentResult(
                    text=msg.content or "",
                    tool_results=all_tool_results,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    model=self.model,
                )

            # Execute tool calls
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info("Calling tool: %s with args: %s", tool_name, tool_args)

                try:
                    result = await self.client.call_tool(tool_name, tool_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content,
                    })
                    all_tool_results.append({
                        "name": tool_name,
                        "args": tool_args,
                        "content": result.content,
                        "is_error": result.is_error,
                        "response_mapping": self._get_tool_mapping(tool_name),
                    })

                except CircuitBreakerOpen:
                    # Don't swallow — let talk() return "service unavailable"
                    raise

                except Exception as exc:
                    logger.error("Tool execution error: %s", exc)
                    error_content = json.dumps({"error": str(exc)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": error_content,
                    })
                    all_tool_results.append({
                        "name": tool_name,
                        "args": tool_args,
                        "content": error_content,
                        "is_error": True,
                    })

        logger.warning("Max iterations (%d) reached", max_iterations)
        return AgentResult(
            text="I couldn't complete the request within the allowed steps.",
            tool_results=all_tool_results,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            model=self.model,
        )

    def _get_tool_mapping(self, tool_name: str) -> Optional[Dict[str, Any]]:
        try:
            for tool in self.client.tools:
                if tool.name == tool_name:
                    return tool.response_mapping
        except Exception:
            pass
        return None
