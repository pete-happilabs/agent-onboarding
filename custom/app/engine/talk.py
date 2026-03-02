"""
Custom Talk Engine — production-hardened.

Additions over original:
- validate_dost_event()  → rejects malformed input immediately
- with_timeout()         → hard 28s cap prevents hung requests
- CircuitBreakerOpen     → user-friendly message when REST APIs are down
- TimeoutError           → user-friendly message on timeout
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, Tuple, Dict as _Dict

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "../../..")))
from shared.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
    validate_dost_event,
)
from shared.shared_breaker import with_timeout, CircuitBreakerOpen

from ..core.metrics import TalkMetrics
from ..custom.client import CustomClient
from ..llm.agent import ReActAgent
from ..llm.response_formatter import build_dost_categories, infer_event_hint
from ..config import get_settings

logger = logging.getLogger(__name__)

_TALK_TIMEOUT = 28.0  # seconds — less than typical WebSocket/HTTP gateway timeout

_RATE_BUCKETS: _Dict[str, _Dict[str, float]] = defaultdict(
    lambda: {"tokens": 10.0, "last_refill": time.monotonic()}
)
_RATE_LIMIT_CAPACITY = 10.0
_RATE_LIMIT_REFILL_RATE = 10.0 / 60.0


def _check_rate_limit(session_id: str) -> bool:
    bucket = _RATE_BUCKETS[session_id]
    now = time.monotonic()
    elapsed = now - bucket["last_refill"]
    bucket["tokens"] = min(_RATE_LIMIT_CAPACITY, bucket["tokens"] + elapsed * _RATE_LIMIT_REFILL_RATE)
    bucket["last_refill"] = now
    if bucket["tokens"] >= 1.0:
        bucket["tokens"] -= 1.0
        return True
    return False


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a talk request.

    Flow:
    1. Validate incoming dostEvent structure
    2. Extract entity_id, session_id, message
    3. Initialize CustomClient + ReActAgent
    4. Run agent with hard timeout
    5. Build response dostEvent with dostCategories
    6. Return (dostEvent, metrics)
    """
    settings = get_settings()
    metrics = TalkMetrics()

    # --- 1. Validate input ---
    try:
        validate_dost_event(event)
    except ValueError as exc:
        logger.warning("Invalid dostEvent received: %s", exc)
        entity_id = event.get("sourceEntityId", "unknown") if isinstance(event, dict) else "unknown"
        session_id = event.get("sessionId") if isinstance(event, dict) else None
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message=f"Invalid request: {exc}",
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()

    # --- 2. Extract fields ---
    entity_id = event.get("sourceEntityId", "unknown")
    session_id = event.get("sessionId")
    user_message = extract_query_text(event)

    logger.info(
        "TALK - Entity: %s, Session: %s, Message: '%s...'",
        entity_id, session_id, (user_message[:50] if user_message else ""),
    )

    if session_id and not _check_rate_limit(session_id):
        logger.warning("Rate limit exceeded — session: %s", session_id)
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message="Too many requests. Please wait a moment before trying again.",
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()

    # --- 3. Handle empty message ---
    if not user_message:
        return _build_response(
            entity_id=entity_id,
            session_id=session_id,
            message_text="I didn't catch that. Could you say something?",
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()

    try:
        # --- 4. Initialize client + agent ---
        client = CustomClient(settings.custom.config_path)
        agent_config = client.get_agent_config()
        prompt_name = agent_config.get("prompt_name", "default")

        agent = ReActAgent(
            client=client,
            api_key=settings.llm.api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            prompt_name=prompt_name,
        )

        # --- 5. Run agent with hard timeout ---
        result = await with_timeout(
            agent.run(user_message),
            timeout=_TALK_TIMEOUT,
            operation="agent.run",
        )

        if result.model and (result.input_tokens > 0 or result.output_tokens > 0):
            metrics.add_llm(result.model, result.input_tokens, result.output_tokens)

        # --- 6. Build response ---
        categories = None
        event_hint = "response"
        if result.tool_results:
            categories = build_dost_categories(
                result.tool_results,
                currency=settings.custom.currency,
            )
            event_hint = infer_event_hint(result.tool_results)

        response_event = create_dost_event(
            source_entity_id=settings.agent.entity_id,
            destination_entity_id=entity_id,
            session_id=session_id,
            event_hint=event_hint,
            is_ai_generated=True,
            message=create_dost_message(text=result.text),
            categories=categories,
        )

        logger.info(
            "TALK - Response: %d chars, Metrics: %s",
            len(result.text), metrics.to_dict(),
        )
        return response_event, metrics.to_dict()

    except CircuitBreakerOpen as exc:
        logger.error("Circuit breaker open: %s", exc)
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message="Service temporarily unavailable. Please try again shortly.",
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()

    except TimeoutError as exc:
        logger.error("Talk timed out: %s", exc)
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message="Request timed out. Please try again.",
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()

    except Exception as exc:
        logger.exception("Talk error: %s", exc)
        return _build_error_response(
            entity_id=entity_id,
            session_id=session_id,
            error_message=str(exc),
            source_entity_id=settings.agent.entity_id,
        ), metrics.to_dict()


def _build_response(
    entity_id: str,
    session_id: str,
    message_text: str,
    source_entity_id: str,
    event_hint: str = "response",
    categories: Dict[str, Any] = None,
) -> Dict[str, Any]:
    return create_dost_event(
        source_entity_id=source_entity_id,
        destination_entity_id=entity_id,
        session_id=session_id,
        event_hint=event_hint,
        is_ai_generated=True,
        message=create_dost_message(text=message_text),
        categories=categories,
    )


def _build_error_response(
    entity_id: str,
    session_id: str,
    error_message: str,
    source_entity_id: str,
) -> Dict[str, Any]:
    return _build_response(
        entity_id=entity_id,
        session_id=session_id,
        message_text=f"I encountered an issue: {error_message}",
        source_entity_id=source_entity_id,
        event_hint="error",
    )
