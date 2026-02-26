"""
Generic Talk Engine — production-hardened wrapper for UrbanBotAgent.

Resilience:
- validate_dost_event()  → rejects malformed/non-UUID input before any processing
- with_timeout(55s)      → hard cap prevents hung LangGraph ReAct loops
- TalkMetrics            → consistent DPA format metrics across all agents
- Token-bucket rate limiter → per-session, 10 requests/minute
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, Tuple

from app.core.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
    validate_dost_event,
)
from app.core.resilience import with_timeout
from app.agent.urban_agent import UrbanBotAgent
from app.config import get_settings

logger = logging.getLogger(__name__)

_TALK_TIMEOUT = 55.0  # seconds — LangGraph ReAct loops can be multi-step

# ---------------------------------------------------------------------------
# Rate limiter — token bucket, per sessionId
# ---------------------------------------------------------------------------
_RATE_BUCKETS: Dict[str, Dict[str, float]] = defaultdict(
    lambda: {"tokens": 10.0, "last_refill": time.monotonic()}
)
_RATE_LIMIT_CAPACITY = 10.0   # max tokens per session
_RATE_LIMIT_REFILL_RATE = 10.0 / 60.0  # tokens per second (10 per minute)


def _check_rate_limit(session_id: str) -> bool:
    """
    Token-bucket rate limiter.
    Returns True if the request is allowed, False if rate-limited.
    """
    bucket = _RATE_BUCKETS[session_id]
    now = time.monotonic()
    elapsed = now - bucket["last_refill"]
    bucket["tokens"] = min(
        _RATE_LIMIT_CAPACITY,
        bucket["tokens"] + elapsed * _RATE_LIMIT_REFILL_RATE,
    )
    bucket["last_refill"] = now
    if bucket["tokens"] >= 1.0:
        bucket["tokens"] -= 1.0
        return True
    return False


# ---------------------------------------------------------------------------
# Agent singleton
# ---------------------------------------------------------------------------
_agent: UrbanBotAgent | None = None


def _get_agent() -> UrbanBotAgent:
    global _agent
    if _agent is None:
        _agent = UrbanBotAgent()
    return _agent


# ---------------------------------------------------------------------------
# Talk
# ---------------------------------------------------------------------------
async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a dostEvent through the UrbanBotAgent.

    Flow:
    1. Validate dostEvent structure (UUID sessionId enforced)
    2. Rate limit per sessionId
    3. Extract message
    4. Run agent with hard 55s timeout
    5. Return (dostEvent response, DPA metrics)
    """
    settings = get_settings()
    agent_entity_id = settings.agent.entity_id

    # 1. Validate
    try:
        validate_dost_event(event)
    except ValueError as exc:
        logger.warning("Invalid dostEvent: %s", exc)
        entity_id = event.get("sourceEntityId", "unknown") if isinstance(event, dict) else "unknown"
        session_id = event.get("sessionId") if isinstance(event, dict) else None
        return _build_error(agent_entity_id, entity_id, session_id, str(exc)), {"models": {}}

    entity_id = event["sourceEntityId"]
    session_id = event["sessionId"]

    # 2. Rate limit
    if not _check_rate_limit(session_id):
        logger.warning("Rate limit exceeded — session: %s", session_id)
        return _build_error(
            agent_entity_id, entity_id, session_id,
            "Too many requests. Please wait a moment before trying again."
        ), {"models": {}}

    # 3. Extract message
    user_message = extract_query_text(event)
    logger.info("TALK - Entity: %s, Session: %s, Message: '%s...'", entity_id, session_id, user_message[:50])

    if not user_message:
        return _build_response(
            agent_entity_id, entity_id, session_id, "I didn't catch that. Could you say something?"
        ), {"models": {}}

    # 4. Run agent with timeout
    try:
        result = await with_timeout(
            _get_agent().process_message(user_message, session_id),
            timeout=_TALK_TIMEOUT,
            operation="generic_agent.process_message",
        )
        response_text = result["response"]
        logger.info("TALK - Response: %d chars", len(response_text))
        return _build_response(agent_entity_id, entity_id, session_id, response_text), {"models": {}}

    except TimeoutError as exc:
        logger.error("Talk timed out: %s", exc)
        return _build_error(
            agent_entity_id, entity_id, session_id,
            "Request timed out. Please try again."
        ), {"models": {}}

    except Exception as exc:
        logger.exception("Talk error: %s", exc)
        return _build_error(
            agent_entity_id, entity_id, session_id,
            "Service temporarily unavailable. Please try again shortly."
        ), {"models": {}}


def _build_response(
    agent_entity_id: str,
    entity_id: str,
    session_id: str,
    text: str,
    event_hint: str = "response",
) -> Dict[str, Any]:
    return create_dost_event(
        source_entity_id=agent_entity_id,
        destination_entity_id=entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=text),
    )


def _build_error(
    agent_entity_id: str,
    entity_id: str,
    session_id: str | None,
    message: str,
) -> Dict[str, Any]:
    # If session_id is missing/invalid, fall back to a synthetic one for the response
    sid = session_id or "00000000-0000-0000-0000-000000000000"
    return _build_response(agent_entity_id, entity_id, sid, message, event_hint="error")
