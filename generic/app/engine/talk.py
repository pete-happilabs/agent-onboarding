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
    create_dost_categories,
    create_dost_category,
    create_dost_object,
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

        # Build dostCategories from tool results (same as MCP/Custom)
        categories = None
        event_hint = "response"
        tool_results = result.get("tool_results", [])
        if tool_results:
            categories = _build_categories_from_tools(tool_results, settings)
            event_hint = _infer_event_hint(tool_results)

        logger.info(f"TALK - Response: {len(response_text)} chars, Metrics: {metrics.to_dict()}")

        return _build_response(
            agent_entity_id=agent_entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            message_text=response_text,
            event_hint=event_hint,
            categories=categories,
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
    categories: Dict[str, Any] = None,
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


def _build_categories_from_tools(
    tool_results: list,
    settings,
) -> Dict[str, Any] | None:
    """Build dostCategories from LangGraph tool results."""
    import json
    import uuid

    if not tool_results:
        return None

    all_categories = []

    for result in tool_results:
        tool_name = result.get("name", "unknown")
        content = result.get("content", "")
        if result.get("is_error"):
            continue

        # Try parsing as JSON first (structured data)
        try:
            if isinstance(content, str):
                parsed = json.loads(content)
            else:
                parsed = content

            # If parsed is a list, create objects from each item
            items = parsed if isinstance(parsed, list) else [parsed]
            objects = []
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    objects.append(create_dost_object(
                        id=str(item.get("id", f"{tool_name}_{i}_{uuid.uuid4().hex[:8]}")),
                        type=tool_name,
                        title=str(item.get("name", item.get("title", f"Item {i + 1}"))),
                        description=str(item.get("description", "")),
                    ))
            if objects:
                all_categories.append(create_dost_category(
                    title=_format_tool_name(tool_name),
                    objects=objects,
                ))
                continue
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: wrap text content as a single dostObject
        if content and isinstance(content, str) and len(content.strip()) > 0:
            all_categories.append(create_dost_category(
                title=_format_tool_name(tool_name),
                objects=[create_dost_object(
                    id=f"{tool_name}_{uuid.uuid4().hex[:8]}",
                    type=tool_name,
                    title=_format_tool_name(tool_name),
                    description=content[:2000],
                )],
            ))

    if not all_categories:
        return None

    currency = getattr(settings.generic, "currency", "INR") if hasattr(settings, "generic") else "INR"
    return create_dost_categories(currency=currency, categories=all_categories)


def _infer_event_hint(tool_results: list) -> str:
    """Infer event hint from tool results."""
    for result in reversed(tool_results):
        if not result.get("is_error"):
            name = result.get("name", "")
            if name.startswith("search_"):
                return name.replace("search_", "") + "_list"
            elif name.startswith("book_"):
                return name.replace("book_", "") + "_booked"
            elif name.startswith("get_"):
                return name.replace("get_", "") + "_details"
            elif name.startswith("list_"):
                return name.replace("list_", "") + "_list"
            elif name:
                return name + "_response"
    return "response"


def _format_tool_name(name: str) -> str:
    """Format tool name as human-readable title."""
    return " ".join(word.capitalize() for word in name.replace("_", " ").split())
