# ============================================================================
# FILE: app/dost/protocol.py
# ============================================================================
"""
DOST Event Specification (Approved)

Version History:
  - 00.01.01 (21st Jan 2026): Approved
      - dostAction: Added androidIntent/iosIntent for invoking device actions
      - dostObject.location: Now an array of dostLocation[] instead of singleton
  - 00.01.00 (12th Jan 2026): Approved
      - Post team review of initial version

Structure Index (per spec):
  1. dostEvent        - Root envelope
  2. dostMessage      - Multimodal message
  3. dostCategories   - Groups of categories
  4. dostData         - Binary data blob (audioData, videoData, imageData, documentData)
  5. dostCategory     - Logical grouping of objects
  6. dostObject       - Core business/content unit
  7. dostPricing      - Price units and billing rules
  8. dostAction       - Actions for recipient
  9. dostLocation     - Geographic location
"""
from datetime import datetime, timezone
import uuid
from typing import List, Optional, Dict, Any


# =============================================================================
# Constants
# =============================================================================
DOST_SPEC_VERSION = "00.01.01"
VALID_DURATION_TYPES = ["min", "hr", "day", "week", "month", "year", "permanent"]


# =============================================================================
# 1. dostEvent — Root Envelope
# =============================================================================
def create_dost_event(
    source_entity_id: str,
    version: str = DOST_SPEC_VERSION,
    timestamp: Optional[str] = None,
    event_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_hint: Optional[str] = None,
    destination_entity_id: Optional[str] = None,
    is_ai_generated: bool = False,
    message: Optional[Dict[str, Any]] = None,
    categories: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a dostEvent per spec.

    {
      "version": "string",
      "timestamp": "string (ISO-8601)",
      "eventId": "string (UUID)",
      "sessionId": "string (UUID)",
      "eventHint": "string | null",
      "sourceEntityId": "string",
      "destinationEntityId": "string | null",
      "isAiGenerated": "boolean",
      "message": "dostMessage | null",
      "categories": "dostCategories | null"
    }
    """
    if message is None and categories is None:
        raise ValueError("dostEvent must contain at least message or categories")

    return {
        "version": version,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "eventId": event_id or str(uuid.uuid4()),
        "sessionId": session_id or str(uuid.uuid4()),
        "eventHint": event_hint,
        "sourceEntityId": source_entity_id,
        "destinationEntityId": destination_entity_id,
        "isAiGenerated": is_ai_generated,
        "message": message,
        "categories": categories
    }


# =============================================================================
# 2. dostMessage — Multimodal Message
# =============================================================================
def create_dost_message(
    text: Optional[str] = None,
    audios: Optional[List[Dict[str, str]]] = None,
    images: Optional[List[Dict[str, str]]] = None,
    videos: Optional[List[Dict[str, str]]] = None,
    documents: Optional[List[Dict[str, str]]] = None,
    contact: Optional[List[Dict[str, Optional[str]]]] = None,
    dost_entity: Optional[List[Dict[str, str]]] = None,
    location: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Create a dostMessage per spec.

    {
      "text"?: { "data": "string" },
      "audios"?: [audioData],
      "images"?: [imageData],
      "videos"?: [videoData],
      "documents"?: [documentData],
      "contact"?: [{ "name": "string", "phone": "string | null" }],
      "dostEntity"?: [{ "entityId": "string" }],
      "location"?: dostLocation  // SINGLE object only (not array)
    }

    NOTE: dostMessage.location is a SINGLE dostLocation (not array).
          dostObject.location is an ARRAY of dostLocation.
    """
    message: Dict[str, Any] = {}

    if text is not None:
        message["text"] = {"data": text}
    if audios is not None:
        message["audios"] = audios
    if images is not None:
        message["images"] = images
    if videos is not None:
        message["videos"] = videos
    if documents is not None:
        message["documents"] = documents
    if contact is not None:
        message["contact"] = contact
    if dost_entity is not None:
        message["dostEntity"] = dost_entity
    if location is not None:
        if isinstance(location, list):
            raise TypeError("dostMessage.location must be a single dostLocation, not an array")
        message["location"] = location

    return message if message else None


# =============================================================================
# 3. dostCategories
# =============================================================================
def create_dost_categories(
    currency: str,
    categories: Optional[List[Dict[str, Any]]] = None,
    actions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Create a dostCategories per spec.

    {
      "actions"?: dostAction[],
      "currency": "string",
      "categories": dostCategory[]
    }
    """
    cats: Dict[str, Any] = {"currency": currency}

    if actions is not None:
        cats["actions"] = actions
    if categories is not None:
        cats["categories"] = categories

    return cats


# =============================================================================
# 4. dostData (aliases: audioData, videoData, imageData, documentData)
# =============================================================================
def create_dost_data(data_type: str, data: str) -> Dict[str, str]:
    """
    Create a dostData object per spec.

    {
      "data-type": "multipart | url",
      "data": "multipart-form-data-id | https-url"
    }
    """
    if data_type not in ["multipart", "url"]:
        raise ValueError("data-type must be 'multipart' or 'url'")
    return {
        "data-type": data_type,
        "data": data
    }


# =============================================================================
# 5. dostCategory
# =============================================================================
def create_dost_category(
    title: Optional[str] = None,
    objects: Optional[List[Dict[str, Any]]] = None,
    actions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Create a dostCategory per spec.

    {
      "title": "string | null",
      "objects": dostObject[],
      "actions"?: dostAction[]
    }
    """
    category: Dict[str, Any] = {
        "title": title,
        "objects": objects or []
    }

    if actions is not None:
        category["actions"] = actions

    return category


# =============================================================================
# 6. dostObject
# =============================================================================
def create_dost_object(
    id: str,
    type: str,
    title: str,
    description: Optional[str] = None,
    reputation: Optional[str] = None,
    media: Optional[Dict[str, Any]] = None,
    location: Optional[List[Dict[str, str]]] = None,
    pricing: Optional[List[Dict[str, Any]]] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a dostObject per spec v00.01.01.

    {
      "id": "string",
      "type": "string",
      "title": "string",
      "description": "string | null",
      "reputation": "string | null",
      "media"?: { images, videos, audios, documents },
      "location"?: dostLocation[],  // ARRAY only (v00.01.01)
      "pricing"?: dostPricing[],
      "actions"?: dostAction[],
      "tags"?: [string]
    }

    NOTE: location MUST be an array of dostLocation (v00.01.01).
    """
    obj: Dict[str, Any] = {
        "id": id,
        "type": type,
        "title": title,
        "description": description,
        "reputation": reputation
    }

    if media is not None:
        obj["media"] = media
    if location is not None:
        if not isinstance(location, list):
            raise TypeError("dostObject.location must be an array of dostLocation")
        obj["location"] = location
    if pricing is not None:
        obj["pricing"] = pricing
    if actions is not None:
        obj["actions"] = actions
    if tags is not None and len(tags) > 0:
        obj["tags"] = tags

    return obj


# =============================================================================
# 7. dostPricing
# =============================================================================
def create_dost_pricing(
    id: str,
    value: float,
    duration_type: str,
    duration_value: int,
    max_quantity: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a dostPricing object per spec.

    {
      "id": "string",
      "value": "number",
      "maxQuantity": "number | null",
      "durationType": "min | hr | day | week | month | year | permanent",
      "durationValue": "number"
    }
    """
    if duration_type not in VALID_DURATION_TYPES:
        raise ValueError(f"durationType must be one of: {VALID_DURATION_TYPES}")

    pricing: Dict[str, Any] = {
        "id": id,
        "value": value,
        "durationType": duration_type,
        "durationValue": duration_value
    }

    if max_quantity is not None:
        pricing["maxQuantity"] = max_quantity

    return pricing


# =============================================================================
# 8. dostAction
# =============================================================================
def create_dost_action(
    display_text: str,
    prompt: Optional[str] = None,
    android_intent: Optional[str] = None,
    ios_intent: Optional[str] = None,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a dostAction object per spec.

    {
      "displayText": "string",
      "prompt"?: "string",
      "androidIntent"?: "string",
      "iosIntent"?: "string",
      "url"?: "string"
    }
    """
    action: Dict[str, Any] = {"displayText": display_text}

    if prompt is not None:
        action["prompt"] = prompt
    if android_intent is not None:
        action["androidIntent"] = android_intent
    if ios_intent is not None:
        action["iosIntent"] = ios_intent
    if url is not None:
        action["url"] = url

    return action


# =============================================================================
# 9. dostLocation
# =============================================================================
def create_dost_location(
    latitude: Optional[str] = None,
    longitude: Optional[str] = None,
    address: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Create a dostLocation object per spec.

    {
      "latitude"?: "string | null",
      "longitude"?: "string | null",
      "address"?: "string | null"
    }
    """
    if not any([latitude, longitude, address]):
        return None

    location: Dict[str, str] = {}
    if latitude is not None:
        location["latitude"] = latitude
    if longitude is not None:
        location["longitude"] = longitude
    if address is not None:
        location["address"] = address

    return location if location else None


# =============================================================================
# DAS Helpers
# =============================================================================
def create_response_event(
    source_entity_id: str,
    destination_entity_id: Optional[str],
    message_text: str,
    original_session_id: Optional[str] = None,
    categories: Optional[Dict[str, Any]] = None,
    version: str = DOST_SPEC_VERSION,
    event_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a DOST response event (DAS convenience function).
    """
    message = create_dost_message(text=message_text)

    return create_dost_event(
        source_entity_id=source_entity_id,
        version=version,
        session_id=original_session_id,
        event_hint=event_hint,
        destination_entity_id=destination_entity_id,
        is_ai_generated=True,
        message=message,
        categories=categories
    )


# =============================================================================
# Extractors
# =============================================================================
def extract_query_text(event: Dict[str, Any]) -> str:
    """Extract message.text.data from a dostEvent."""
    try:
        message = event.get("message")
        if not isinstance(message, dict):
            return ""

        text = message.get("text")
        if not isinstance(text, dict):
            return ""

        return text.get("data", "")
    except Exception:
        return ""


def extract_objects_from_categories(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all dostObjects from event.categories.categories[].objects[]"""
    try:
        categories_root = event.get("categories")
        if not isinstance(categories_root, dict):
            return []

        categories_list = categories_root.get("categories")
        if not isinstance(categories_list, list):
            return []

        all_objects: List[Dict[str, Any]] = []
        for category in categories_list:
            if isinstance(category, dict):
                objects = category.get("objects")
                if isinstance(objects, list):
                    all_objects.extend(objects)

        return all_objects
    except Exception:
        return []
