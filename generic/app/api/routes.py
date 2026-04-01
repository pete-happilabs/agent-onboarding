"""
REST API routes for Generic Agent.
DOST-compliant using dostEvent protocol v00.01.01
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dost.protocol import (
    create_dost_event,
    create_dost_message,
    create_dost_object,
    create_dost_category,
    create_dost_categories,
    create_dost_pricing,
    create_dost_location,
    create_dost_action,
    extract_query_text,
)
from dost.metrics import TalkMetrics
from app.core.database import get_mongodb
from app.core.vector_store import get_vector_store
from config import get_settings


# =============================================================================
# DOST Protocol Models
# =============================================================================

class DostMessage(BaseModel):
    """dostMessage structure."""
    text: Dict[str, Any] | None = None

class DostEvent(BaseModel):
    """dostEvent structure - the root envelope."""
    version: str
    timestamp: str
    eventId: str
    sessionId: str | None = None
    eventHint: str | None = None
    sourceEntityId: str
    destinationEntityId: str | None = None
    isAiGenerated: bool = False
    message: DostMessage | None = None
    categories: Dict[str, Any] | None = None

class DostResponse(BaseModel):
    """Response wrapper with dostEvent and metrics."""
    event: Dict[str, Any]
    metrics: Dict[str, Any]


logger = logging.getLogger(__name__)

router = APIRouter()

# Agent instance (initialized in main.py)
_agent = None


def set_agent(agent) -> None:
    """Set the agent instance for routes."""
    global _agent
    _agent = agent


# =============================================================================
# Service to DOST Object Converter
# =============================================================================

def service_to_dost_object(service: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a service to dostObject."""

    # Build pricing
    pricing = create_dost_pricing(
        id=service['service_id'],
        value=service['pricing']['base_price'],
        duration_type="min",
        duration_value=service['pricing'].get('base_duration_minutes', 30)
    )

    # Build locations
    locations = []
    for avail in service.get('availability', []):
        loc = create_dost_location(address=avail['city_name'])
        if loc:
            locations.append(loc)

    # Build action
    action = create_dost_action(
        display_text="Book Now",
        url=f"/uc-agent?action=book&service_id={quote(str(service['service_id']), safe='')}"
    )

    # Build dostObject
    return create_dost_object(
        id=service['service_id'],
        type=service['category']['name'],
        title=service['name'],
        description=service['description'],
        location=locations if locations else None,
        pricing=[pricing],
        actions=[action]
    )


def search_services_for_dost(query: str, city: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """Search services and return as dostObjects grouped by category."""

    vector_store = get_vector_store()
    results = vector_store.search(query, top_k=10)

    if not results:
        return {}

    # City normalization
    city_aliases = {
        "bengaluru": "bangaluru", "bangalore": "bangaluru", "blr": "bangaluru",
        "bombay": "mumbai", "new delhi": "delhi", "ncr": "delhi"
    }
    city_normalized = city_aliases.get(city.lower().strip(), city.lower().strip()) if city else ""

    # Filter and group by category
    categories_dict: Dict[str, List[Dict[str, Any]]] = {}

    for result in results:
        service = result['service']
        similarity = result['similarity']

        if similarity < 0.25:
            continue

        # Filter by city if specified
        if city_normalized:
            service_cities = [city_aliases.get(c['city_name'].lower(), c['city_name'].lower())
                           for c in service['availability']]
            if city_normalized not in service_cities:
                continue

        # Group by category
        cat_name = service['category']['name']
        if cat_name not in categories_dict:
            categories_dict[cat_name] = []

        dost_obj = service_to_dost_object(service)
        categories_dict[cat_name].append(dost_obj)

    return categories_dict


def extract_city_from_message(message: str) -> str:
    """Extract city name from user message."""
    cities = ["bangalore", "bengaluru", "bangaluru", "mumbai", "bombay", "delhi", "new delhi"]
    message_lower = message.lower()
    for city in cities:
        if city in message_lower:
            return city
    return ""


# =============================================================================
# DOST Protocol Endpoint
# =============================================================================

@router.post("/uc-agent", response_model=DostResponse)
async def uc_agent(event: DostEvent):
    """
    Generic Agent - DOST-compliant endpoint.

    Accepts: dostEvent with message.text.data containing user message
    Returns: dostEvent with AI response + structured categories with dostObjects

    Protocol: DOST Event Specification v00.01.01
    """
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    settings = get_settings()
    agent_entity_id = settings.agent.entity_id

    try:
        mongodb = get_mongodb()

        # Extract from dostEvent
        session_id = event.sessionId or event.eventId
        user_message = extract_query_text(event.model_dump())
        source_entity = event.sourceEntityId

        if not user_message:
            raise HTTPException(status_code=400, detail="No message text in dostEvent")

        MAX_MESSAGE_LENGTH = 10_000
        if len(user_message) > MAX_MESSAGE_LENGTH:
            user_message = user_message[:MAX_MESSAGE_LENGTH]

        logger.info(f"[UC-AGENT] Received from {source_entity}: {user_message[:50]}...")

        # Load or create session
        session = await mongodb.sessions.find_one({"session_id": {"$eq": session_id}})

        if session:
            previous_state = {
                "selected_service_id": session.get("selected_service_id"),
                "booking_details": session.get("booking_details", {}),
                "details_shown": session.get("details_shown", False)
            }
            messages_history = session.get("messages", [])
        else:
            previous_state = {}
            messages_history = []
            await mongodb.sessions.insert_one({
                "session_id": session_id,
                "messages": [],
                "selected_service_id": None,
                "booking_details": {},
                "details_shown": False,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })
            logger.info(f"[UC-AGENT] Created new session: {session_id}")

        # Process message with agent
        result = await _agent.process_message(
            user_message=user_message,
            user_id=session_id,
            customer_profile=None,
            previous_state=previous_state,
            metadata=None
        )

        # Track token usage via TalkMetrics
        metrics = TalkMetrics()
        model = result.get("model", "")
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        if model and (input_tokens > 0 or output_tokens > 0):
            metrics.add_llm(model, input_tokens, output_tokens)

        # Update session
        messages_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        messages_history.append({
            "role": "assistant",
            "content": result["response"],
            "timestamp": datetime.now().isoformat()
        })
        messages_history = messages_history[-20:]

        new_state = result.get("state", {})
        await mongodb.sessions.update_one(
            {"session_id": {"$eq": session_id}},
            {
                "$set": {
                    "messages": messages_history,
                    "selected_service_id": new_state.get("selected_service_id"),
                    "booking_details": new_state.get("booking_details", {}),
                    "details_shown": new_state.get("details_shown", False),
                    "updated_at": datetime.now()
                }
            }
        )

        # Search for services to include as structured data
        city = extract_city_from_message(user_message)
        categories_dict = search_services_for_dost(user_message, city)

        # Build dostCategories if services found
        dost_categories = None
        if categories_dict:
            category_list = []
            for cat_name, objects in categories_dict.items():
                cat = create_dost_category(
                    title=cat_name,
                    objects=objects[:5]  # Limit to 5 per category
                )
                category_list.append(cat)

            if category_list:
                dost_categories = create_dost_categories(
                    currency=settings.generic.currency,
                    categories=category_list
                )

        # Build DOST response event
        response_message = create_dost_message(text=result["response"])
        response_event = create_dost_event(
            source_entity_id=agent_entity_id,
            destination_entity_id=source_entity,
            session_id=session_id,
            event_hint="talk_response",
            is_ai_generated=True,
            message=response_message,
            categories=dost_categories
        )

        logger.info(f"[UC-AGENT] Response: {result['response'][:50]}... (categories: {len(categories_dict)} types)")

        return DostResponse(event=response_event, metrics=metrics.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[UC-AGENT] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
