# ============================================================================
# FILE: mcp/llm/agent.py
# ============================================================================
"""
ReAct Agent - Natural language to MCP tool execution.

ReAct (Reasoning + Acting) loop:
1. Reason - LLM thinks about what to do
2. Act - LLM calls a tool
3. Observe - Get tool result
4. Repeat until done

Works with ANY MCP server by dynamically discovering tools at runtime.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING

from openai import AsyncOpenAI

from .tool_converter import mcp_to_openai_tools

if TYPE_CHECKING:
    from ..client.mcp_client import MCPClient
    from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from ReAct agent execution."""

    text: str  # Human-readable response text
    tool_results: List[Dict[str, Any]] = field(default_factory=list)  # Raw tool results for structured data
    input_tokens: int = 0  # Total input tokens used
    output_tokens: int = 0  # Total output tokens used
    model: str = ""  # Model name used

# System prompt for the ReAct agent
SYSTEM_PROMPT = """You are a helpful assistant that uses tools to help users.

When the user asks for something:
1. Analyze what they need
2. Call the appropriate tool with the correct parameters
3. Return a BRIEF summary (1-2 sentences max)

IMPORTANT: Keep your response very short! Just say what you found, like:
- "Here are 5 places to stay in Marathalli for 2 adults from Feb 13-17."
- "Found 10 restaurants near you."
- "Here are your flight options."

Do NOT list individual items in your response - the structured data will be shown separately.
If a tool returns an error, briefly explain what went wrong.

Important:
- Extract specific values from the user's message (names, locations, quantities, etc.)
- Use the tool's parameter schema to understand what's required
- If required information is missing, ask the user for it instead of guessing
"""


class ReActAgent:
    """
    ReAct agent that translates natural language to MCP tool calls.

    Works with ANY MCP server - tools are discovered dynamically.

    Usage:
        agent = ReActAgent(mcp_client, settings)
        response = await agent.run("Order me a pizza with extra cheese")
        # Agent discovers tools, calls order_food({...}), formats response
    """

    def __init__(self, mcp_client: "MCPClient", settings: "Settings"):
        """
        Initialize the ReAct agent.

        Args:
            mcp_client: Connected MCP client for tool discovery and execution
            settings: Configuration with LLM settings
        """
        self.mcp_client = mcp_client
        self.client = AsyncOpenAI(api_key=settings.llm.api_key)
        self.model = settings.llm.model
        self.temperature = settings.llm.temperature

    async def run(self, user_message: str, max_iterations: int = 5) -> AgentResult:
        """
        Process a user message through the ReAct loop.

        Flow:
        1. Get available tools from MCP server
        2. Send user message + tools to LLM
        3. If LLM wants to call a tool, execute it and loop
        4. When LLM responds without tools, return the response

        Args:
            user_message: Natural language user input
            max_iterations: Max tool call loops (prevents infinite loops)

        Returns:
            AgentResult with text response and raw tool results
        """
        # Get MCP tools and convert to OpenAI format
        mcp_tools = await self.mcp_client.list_tools()
        openai_tools = mcp_to_openai_tools(mcp_tools)

        logger.info(f"ReAct agent starting with {len(mcp_tools)} tools available")

        # Build initial messages
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Collect all tool results for structured data extraction
        all_tool_results: List[Dict[str, Any]] = []

        # Track token usage across all API calls
        total_input_tokens = 0
        total_output_tokens = 0

        # ReAct loop
        for iteration in range(max_iterations):
            logger.debug(f"ReAct iteration {iteration + 1}/{max_iterations}")

            # Call LLM with tools
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
                temperature=self.temperature,
            )

            # Track token usage from this API call
            if response.usage:
                total_input_tokens += response.usage.prompt_tokens
                total_output_tokens += response.usage.completion_tokens

            msg = response.choices[0].message

            # Add assistant message to history
            messages.append(msg.model_dump())

            # Check if LLM wants to call tools
            if not msg.tool_calls:
                # No tool calls = LLM is done, return response
                logger.info(f"ReAct completed after {iteration + 1} iterations")
                return AgentResult(
                    text=msg.content or "I processed your request.",
                    tool_results=all_tool_results,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    model=self.model
                )

            # Execute each tool call
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Calling MCP tool: {tool_name} with args: {tool_args}")

                # Call the MCP tool
                result = await self.mcp_client.call_tool(tool_name, tool_args)

                # Add tool result to messages
                tool_content = result.content if result.content else "Success"
                if result.is_error:
                    tool_content = f"Error: {result.content}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_content,
                })

                # Store raw tool result for structured data extraction
                all_tool_results.append({
                    "name": tool_name,
                    "args": tool_args,
                    "content": tool_content,
                    "is_error": result.is_error
                })

                logger.debug(f"Tool {tool_name} returned: {tool_content[:100]}...")

        # Max iterations reached
        logger.warning(f"ReAct reached max iterations ({max_iterations})")
        return AgentResult(
            text="I couldn't complete your request. Please try being more specific.",
            tool_results=all_tool_results,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            model=self.model
        )
