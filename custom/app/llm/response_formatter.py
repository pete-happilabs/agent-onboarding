# ============================================================================
# FILE: app/llm/response_formatter.py
# ============================================================================
"""
Response Formatter - Convert API responses to dostObjects/dostCategories.

Generic converter that works with any API response structure.
Uses response_mapping from YAML config to extract fields.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, Any, List, Optional

from dost.protocol import (
    create_dost_categories,
    create_dost_category,
    create_dost_object,
    create_dost_location,
    create_dost_pricing,
    create_dost_action,
)

logger = logging.getLogger(__name__)


def get_nested_value(obj: Dict[str, Any], path: str) -> Any:
    """
    Get a nested value from a dict using dot notation.

    Args:
        obj: The dictionary to extract from
        path: Dot-separated path (e.g., "pickup.lat")

    Returns:
        The value at the path, or None if not found
    """
    if not path or not obj:
        return None

    keys = path.split(".")
    current = obj

    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and key.isdigit():
            idx = int(key)
            current = current[idx] if idx < len(current) else None
        else:
            return None

        if current is None:
            return None

    return current


def extract_items_from_response(
    response_data: Any,
    items_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract items array from API response.

    Args:
        response_data: Raw API response (dict or list)
        items_path: Path to items array (e.g., "data.rides")

    Returns:
        List of items
    """
    if response_data is None:
        return []

    # If response is already a list, return it
    if isinstance(response_data, list):
        return response_data

    # If no path specified, try common patterns
    if not items_path:
        if isinstance(response_data, dict):
            # Try common response patterns
            for key in ["data", "items", "results", "records", "list"]:
                if key in response_data and isinstance(response_data[key], list):
                    return response_data[key]
            # Return as single-item list if it's an object
            return [response_data]
        return []

    # Extract using path
    items = get_nested_value(response_data, items_path)
    if isinstance(items, list):
        return items
    elif items is not None:
        return [items]

    return []


def build_dost_object_from_item(
    item: Dict[str, Any],
    mapping: Optional[Dict[str, Any]] = None,
    object_type: str = "item",
    index: int = 0
) -> Dict[str, Any]:
    """
    Build a dostObject from a single API response item.

    Args:
        item: Single item from API response
        mapping: Response mapping from YAML config
        object_type: Type for the dostObject
        index: Item index (for generating unique IDs)

    Returns:
        dostObject dict
    """
    mapping = mapping or {}

    # Extract basic fields
    item_id = str(item.get("id", f"{object_type}_{index}_{uuid.uuid4().hex[:8]}"))
    title_field = mapping.get("title_field", "title")
    desc_field = mapping.get("description_field", "description")
    rep_field = mapping.get("reputation_field", "rating")

    title = get_nested_value(item, title_field) or item.get("name") or item.get("title") or f"Item {index + 1}"
    description = get_nested_value(item, desc_field) or item.get("description")
    reputation = get_nested_value(item, rep_field)
    if reputation is not None:
        reputation = str(reputation)

    # Build location if mapping provided
    location = None
    loc_fields = mapping.get("location_fields")
    if loc_fields:
        lat = get_nested_value(item, loc_fields.get("latitude", "latitude"))
        lng = get_nested_value(item, loc_fields.get("longitude", "longitude"))
        addr = get_nested_value(item, loc_fields.get("address", "address"))

        loc = create_dost_location(
            latitude=str(lat) if lat else None,
            longitude=str(lng) if lng else None,
            address=str(addr) if addr else None
        )
        if loc:
            location = [loc]

    # Build pricing if mapping provided
    pricing = None
    price_field = mapping.get("price_field", "price")
    price_value = get_nested_value(item, price_field)
    if price_value is not None:
        try:
            pricing = [create_dost_pricing(
                id=f"price_{item_id}",
                value=float(price_value),
                duration_type="permanent",
                duration_value=1
            )]
        except (ValueError, TypeError):
            pass

    # Build media if available
    media = None
    image_field = mapping.get("image_field", "image")
    image_url = get_nested_value(item, image_field) or item.get("image_url") or item.get("thumbnail")
    if image_url:
        image_str = str(image_url)
        if image_str.lower().startswith(("http://", "https://")):
            media = {
                "images": [{"data-type": "url", "data": image_str}]
            }

    # Build actions if mapping provided
    actions = None
    action_mappings = mapping.get("actions")
    if action_mappings and isinstance(action_mappings, list):
        actions = []
        for action_map in action_mappings:
            display_text = action_map.get("display_text", "Select")
            prompt_template = action_map.get("prompt")
            if prompt_template:
                # Replace placeholders with item values
                prompt = prompt_template.replace("{id}", item_id)
                prompt = prompt.replace("{title}", str(title))
            else:
                prompt = None

            actions.append(create_dost_action(
                display_text=display_text,
                prompt=prompt,
                url=action_map.get("url")
            ))

    # Extract tags
    tags = None
    tags_field = mapping.get("tags_field", "tags")
    tags_value = get_nested_value(item, tags_field)
    if isinstance(tags_value, list):
        tags = [str(t) for t in tags_value]

    return create_dost_object(
        id=item_id,
        type=object_type,
        title=str(title),
        description=str(description) if description else None,
        reputation=reputation,
        media=media,
        location=location,
        pricing=pricing,
        actions=actions,
        tags=tags
    )


def build_dost_categories(
    tool_results: List[Dict[str, Any]],
    currency: str = "INR"
) -> Optional[Dict[str, Any]]:
    """
    Build dostCategories from tool results.

    Args:
        tool_results: List of tool execution results
        currency: Currency code (default INR)

    Returns:
        dostCategories dict or None if no items
    """
    if not tool_results:
        return None

    all_categories = []

    for result in tool_results:
        tool_name = result.get("name", "unknown")
        content = result.get("content", "{}")
        is_error = result.get("is_error", False)

        if is_error:
            continue

        # Parse JSON content
        try:
            if isinstance(content, str):
                response_data = json.loads(content)
            else:
                response_data = content
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool result as JSON: {content[:100]}")
            continue

        # Get response mapping from tool if available
        mapping = result.get("response_mapping", {})
        items_path = mapping.get("items_path")
        object_type = mapping.get("object_type", tool_name)

        # Extract items
        items = extract_items_from_response(response_data, items_path)

        if not items:
            continue

        # Build dostObjects
        objects = []
        for i, item in enumerate(items):
            if isinstance(item, dict):
                obj = build_dost_object_from_item(item, mapping, object_type, i)
                objects.append(obj)

        if objects:
            # Create category with tool name as title
            category_title = mapping.get("category_title") or _format_tool_name(tool_name)
            category = create_dost_category(
                title=category_title,
                objects=objects
            )
            all_categories.append(category)

    if not all_categories:
        return None

    return create_dost_categories(
        currency=currency,
        categories=all_categories
    )


def _format_tool_name(name: str) -> str:
    """Format tool name as human-readable title."""
    # search_rides -> Search Rides
    return " ".join(word.capitalize() for word in name.replace("_", " ").split())


def infer_event_hint(tool_results: List[Dict[str, Any]]) -> str:
    """
    Infer event hint from tool results.

    Args:
        tool_results: List of tool execution results

    Returns:
        Event hint string
    """
    if not tool_results:
        return "response"

    # Use the last successful tool name as hint
    for result in reversed(tool_results):
        if not result.get("is_error", False):
            tool_name = result.get("name", "")
            if tool_name:
                # search_rides -> ride_list
                # book_ride -> ride_booked
                if tool_name.startswith("search_"):
                    return tool_name.replace("search_", "") + "_list"
                elif tool_name.startswith("book_"):
                    return tool_name.replace("book_", "") + "_booked"
                elif tool_name.startswith("cancel_"):
                    return tool_name.replace("cancel_", "") + "_cancelled"
                elif tool_name.startswith("get_"):
                    return tool_name.replace("get_", "") + "_details"
                else:
                    return tool_name + "_response"

    return "response"
