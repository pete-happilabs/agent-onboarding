"""
Generic Talk Engine - Same signature as MCP/Custom.

talk(dostEvent) -> (response_dostEvent, metrics)

Bridges the GenericReActAgent (LangGraph) into the standard DOST talk() interface.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Tuple

from dost.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
)
from dost.metrics import TalkMetrics

logger = logging.getLogger(__name__)

# Agent instance — set by main.py at startup
_agent = None


def set_agent(agent) -> None:
    """Set the agent instance for talk()."""
    global _agent
    _agent = agent


def get_agent():
    """Get the current agent instance."""
    return _agent


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a talk request - SAME SIGNATURE AS MCP/Custom.

    Args:
        event: Incoming dostEvent dict with message

    Returns:
        Tuple of (response_dostEvent, metrics)

    Flow:
    1. Extract entity_id, session_id, message from dostEvent
    2. Create TalkMetrics
    3. Call agent.process_message()
    4. Track token usage via TalkMetrics
    5. Build response dostEvent
    6. Return (dostEvent, metrics.to_dict())
    """
    from config import get_settings

    # Extract from INPUT dostEvent
    entity_id = event.get("sourceEntityId", "unknown")
    session_id = event.get("sessionId")
    user_message = extract_query_text(event)

    logger.info(
        f"TALK - Entity: {entity_id}, Session: {session_id}, "
        f"Message: '{user_message[:50] if user_message else ''}...'"
    )

    settings = get_settings()
    agent_entity_id = settings.agent.entity_id

    # Initialize metrics tracker
    metrics = TalkMetrics()

    # Validate message length
    MAX_MESSAGE_LENGTH = 10_000
    if user_message and len(user_message) > MAX_MESSAGE_LENGTH:
        user_message = user_message[:MAX_MESSAGE_LENGTH]

    # Handle empty message
    if not user_message:
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="I didn't catch that. Could you say something?",
        ), metrics.to_dict()

    if _agent is None:
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="Agent not initialized. Please try again later.",
            event_hint="error",
        ), metrics.to_dict()

    try:
        # Call GenericReActAgent
        result = await _agent.process_message(
            user_message=user_message,
            user_id=session_id or "anonymous",
        )

        # Track LLM token usage
        model = result.get("model", "")
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        if model and (input_tokens > 0 or output_tokens > 0):
            metrics.add_llm(model, input_tokens, output_tokens)

        response_text = result.get("response", "I couldn't process that request.")

        logger.info(f"TALK - Response: {len(response_text)} chars, Metrics: {metrics.to_dict()}")

        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=response_text,
        ), metrics.to_dict()

    except Exception as e:
        logger.exception("Talk error")
        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text="I encountered an issue processing your request. Please try again.",
            event_hint="error",
        ), metrics.to_dict()


def _build_response(
    agent_entity_id: str,
    destination_entity_id: str,
    session_id: str,
    message_text: str,
    event_hint: str = "response",
) -> Dict[str, Any]:
    """Build a dostEvent response."""
    return create_dost_event(
        source_entity_id=agent_entity_id,
        destination_entity_id=destination_entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=message_text),
    )
