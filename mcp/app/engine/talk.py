# ============================================================================
# FILE: mcp/engine/talk.py
# ============================================================================
"""
MCP Talk Engine - Bridge dostEvent to MCP servers.

This module provides the talk() function that:
1. Receives a dostEvent
2. Extracts the user message
3. Uses ReAct agent (if LLM enabled) to understand NL and call MCP tools
4. Falls back to simple heuristics if LLM disabled
5. Returns a dostEvent response

SAME SIGNATURE AS DPA's talk():
- Input: dostEvent
- Output: (response_dostEvent, metrics)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from ..core.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
)
from ..client.mcp_client import initialize_mcp_client
from ..config import get_settings

logger = logging.getLogger(__name__)


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a talk request - bridges to MCP server.

    SAME SIGNATURE AS DPA's talk():
    - Input: dostEvent
    - Output: (response_dostEvent, metrics)

    Flow:
    1. Extract message from dostEvent
    2. Get MCP client (connect to their server)
    3. If LLM enabled: Use ReAct agent to understand NL and call tools
       Else: Fall back to simple heuristics
    4. Convert response to dostEvent
    5. Return (response_event, metrics)

    Args:
        event: Incoming dostEvent dict with message

    Returns:
        Tuple of (response_dostEvent, metrics)
    """
    # Extract from dostEvent
    entity_id = event.get("sourceEntityId", "unknown")
    session_id = event.get("sessionId")
    user_message = extract_query_text(event)

    logger.info(
        f"TALK - Entity: {entity_id}, Session: {session_id}, "
        f"Message: '{user_message[:50] if user_message else ''}...'"
    )

    # Get settings
    settings = get_settings()
    agent_entity_id = settings.agent.entity_id

    # Handle empty message
    if not user_message:
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="I didn't catch that. Could you say something?",
        ), {"models": {}}

    # Initialize metrics in DPA format: {"models": {"model_name": {"input_tokens": X, "output_tokens": Y}}}
    metrics: Dict[str, Any] = {"models": {}}

    try:
        # Get and connect MCP client
        client = await initialize_mcp_client()

        # Use ReAct agent if LLM is enabled, otherwise fall back to heuristics
        categories = None
        event_hint = "response"
        if settings.llm.enabled:
            from ..llm import ReActAgent, build_dost_categories, infer_event_hint

            agent = ReActAgent(client, settings)
            result = await agent.run(user_message)
            mcp_response = result.text

            # Track LLM token usage in DPA format
            if result.model and (result.input_tokens > 0 or result.output_tokens > 0):
                metrics["models"][result.model] = {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens
                }

            # Build dostCategories from tool results (structured data)
            if result.tool_results:
                categories = build_dost_categories(result.tool_results)
                # Infer idiomatic event hint from tool names
                event_hint = infer_event_hint(result.tool_results)
        else:
            # Fallback to simple heuristics (existing send_message logic)
            mcp_response = await client.send_message(user_message)

        logger.info(f"TALK - MCP Response: {len(mcp_response)} chars, Metrics: {metrics}")

        # Build dostEvent response with categories if available
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=mcp_response,
            event_hint=event_hint,
            categories=categories,
        ), metrics

    except Exception as e:
        logger.exception(f"Talk error: {e}")

        # Return error response
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=f"Sorry, I encountered an error: {str(e)}",
            event_hint="error",
        ), metrics


def _build_response(
    agent_entity_id: str,
    destination_entity_id: str,
    session_id: str,
    message_text: str,
    event_hint: str = "response",
    categories: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a dostEvent response with optional categories."""
    return create_dost_event(
        source_entity_id=agent_entity_id,
        destination_entity_id=destination_entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=message_text),
        categories=categories,
    )
