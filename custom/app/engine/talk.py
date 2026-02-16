# ============================================================================
# FILE: app/engine/talk.py
# ============================================================================
"""
Custom Talk Engine - Same signature as MCP/DPA.

talk(dostEvent) -> (response_dostEvent, metrics)

Features:
- Accepts dostEvent as INPUT (from DOST)
- Returns dostEvent as OUTPUT (to DOST)
- Same metrics format as DPA
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Tuple

from ..core.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
)
from ..core.metrics import TalkMetrics
from ..custom.client import CustomClient
from ..llm.agent import ReActAgent
from ..llm.response_formatter import build_dost_categories, infer_event_hint
from ..config import get_settings

logger = logging.getLogger(__name__)


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a talk request - SAME SIGNATURE AS MCP/DPA.

    Args:
        event: Incoming dostEvent dict with message

    Returns:
        Tuple of (response_dostEvent, metrics)

    Flow:
    1. Extract entity_id, session_id, message from event
    2. Initialize CustomClient with tools from YAML config
    3. Run ReActAgent with configurable prompt
    4. Build response dostEvent with dostCategories
    5. Return (dostEvent, metrics)
    """
    # Extract from INPUT dostEvent
    entity_id = event.get("sourceEntityId", "unknown")
    session_id = event.get("sessionId")
    user_message = extract_query_text(event)

    logger.info(f"TALK - Entity: {entity_id}, Session: {session_id}, Message: '{user_message[:50] if user_message else ''}...'")

    # Get settings
    settings = get_settings()

    # Initialize metrics tracker
    metrics = TalkMetrics()

    # Handle empty message
    if not user_message:
        return _build_response(
            entity_id=entity_id,
            session_id=session_id,
            message_text="I didn't catch that. Could you say something?",
            source_entity_id=settings.agent.entity_id
        ), metrics.to_dict()

    try:
        # Create client and agent
        client = CustomClient(settings.custom.config_path)

        # Get agent config from YAML
        agent_config = client.get_agent_config()
        prompt_name = agent_config.get("prompt_name", "default")

        agent = ReActAgent(
            client=client,
            api_key=settings.llm.api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            prompt_name=prompt_name
        )

        # Run agent
        result = await agent.run(user_message)

        # Track LLM token usage (DPA format)
        if result.model and (result.input_tokens > 0 or result.output_tokens > 0):
            metrics.add_llm(result.model, result.input_tokens, result.output_tokens)

        # Build OUTPUT dostEvent with dostCategories
        categories = None
        event_hint = "response"
        if result.tool_results:
            categories = build_dost_categories(
                result.tool_results,
                currency=settings.custom.currency
            )
            event_hint = infer_event_hint(result.tool_results)

        response_event = create_dost_event(
            source_entity_id=settings.agent.entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            event_hint=event_hint,
            is_ai_generated=True,
            message=create_dost_message(text=result.text),
            categories=categories
        )

        logger.info(f"TALK - Response: {len(result.text)} chars, Metrics: {metrics.to_dict()}")

        return response_event, metrics.to_dict()

    except Exception as e:
        logger.exception(f"Talk error: {e}")
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message=str(e),
            source_entity_id=settings.agent.entity_id
        ), metrics.to_dict()


def _build_response(
    entity_id: str,
    session_id: str,
    message_text: str,
    source_entity_id: str,
    event_hint: str = "response",
    categories: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Build a response dostEvent."""
    return create_dost_event(
        source_entity_id=source_entity_id,
        destination_entity_id=entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=message_text),
        categories=categories
    )


def _build_error_response(
    entity_id: str,
    session_id: str,
    error_message: str,
    source_entity_id: str
) -> Dict[str, Any]:
    """Build an error response dostEvent."""
    return _build_response(
        entity_id=entity_id,
        session_id=session_id,
        message_text=f"I encountered an issue: {error_message}",
        source_entity_id=source_entity_id,
        event_hint="error"
    )
