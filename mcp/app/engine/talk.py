"""
MCP Talk Engine - Bridge dostEvent to MCP servers.

Production additions over original:
- validate_dost_event()  → rejects malformed input before any processing
- with_timeout()         → hard 28s cap prevents hung WebSocket connections
- CircuitBreakerOpen     → user-friendly message when MCP server is down
- TimeoutError           → user-friendly message on timeout
- % logging             → replaced f-strings for production log safety
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from ..core.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
    validate_dost_event,
)
from ..core.resilience import with_timeout, CircuitBreakerOpen
from ..client.mcp_client import initialize_mcp_client
from ..config import get_settings

logger = logging.getLogger(__name__)

_TALK_TIMEOUT = 28.0  # seconds — less than typical WebSocket/HTTP gateway timeout


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a talk request - bridges to MCP server.

    Flow:
    1. Validate incoming dostEvent structure
    2. Extract message from dostEvent
    3. Connect to MCP server (circuit breaker inside MCPClient.connect)
    4. Run ReAct agent or heuristic with hard timeout
    5. Build response dostEvent
    6. Return (response_event, metrics)
    """
    settings = get_settings()
    agent_entity_id = settings.agent.entity_id

    # --- 1. Validate input ---
    try:
        validate_dost_event(event)
    except ValueError as exc:
        logger.warning("Invalid dostEvent received: %s", exc)
        entity_id = event.get("sourceEntityId", "unknown") if isinstance(event, dict) else "unknown"
        session_id = event.get("sessionId") if isinstance(event, dict) else None
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=f"Invalid request: {exc}",
            event_hint="error",
        ), {"models": {}}

    # --- 2. Extract fields ---
    entity_id = event.get("sourceEntityId", "unknown")
    session_id = event.get("sessionId")
    user_message = extract_query_text(event)

    logger.info(
        "TALK - Entity: %s, Session: %s, Message: '%s...'",
        entity_id, session_id, (user_message[:50] if user_message else ""),
    )

    # --- 3. Handle empty message ---
    if not user_message:
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="I didn't catch that. Could you say something?",
        ), {"models": {}}

    metrics: Dict[str, Any] = {"models": {}}

    try:
        # --- 4. Connect to MCP server (circuit breaker lives inside MCPClient) ---
        client = await initialize_mcp_client()

        # --- 5. Run agent or heuristic with hard timeout ---
        categories = None
        event_hint = "response"

        if settings.llm.enabled:
            from ..llm import ReActAgent, build_dost_categories, infer_event_hint

            agent = ReActAgent(client, settings)

            result = await with_timeout(
                agent.run(user_message),
                timeout=_TALK_TIMEOUT,
                operation="mcp_agent.run",
            )
            mcp_response = result.text

            if result.model and (result.input_tokens > 0 or result.output_tokens > 0):
                metrics["models"][result.model] = {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }

            if result.tool_results:
                categories = build_dost_categories(result.tool_results)
                event_hint = infer_event_hint(result.tool_results)
        else:
            mcp_response = await with_timeout(
                client.send_message(user_message),
                timeout=_TALK_TIMEOUT,
                operation="mcp_client.send_message",
            )

        logger.info("TALK - MCP Response: %d chars, Metrics: %s", len(mcp_response), metrics)

        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=mcp_response,
            event_hint=event_hint,
            categories=categories,
        ), metrics

    except CircuitBreakerOpen as exc:
        logger.error("Circuit breaker open: %s", exc)
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="Service temporarily unavailable. Please try again shortly.",
            event_hint="error",
        ), metrics

    except TimeoutError as exc:
        logger.error("Talk timed out: %s", exc)
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="Request timed out. Please try again.",
            event_hint="error",
        ), metrics

    except Exception as exc:
        logger.exception("Talk error: %s", exc)
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=f"Sorry, I encountered an error: {exc}",
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
    return create_dost_event(
        source_entity_id=agent_entity_id,
        destination_entity_id=destination_entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=message_text),
        categories=categories,
    )
