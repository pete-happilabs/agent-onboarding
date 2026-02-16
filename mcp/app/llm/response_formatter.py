# ============================================================================
# FILE: mcp/llm/response_formatter.py
# ============================================================================
"""
Generic converter for MCP tool results to dostObject format.

Transforms structured data from ANY MCP tool into proper
dostCategories with dostObjects per DOST spec.

Works by:
1. Detecting JSON arrays in tool responses
2. Mapping common field names to dostObject fields
3. Building proper dostCategories structure
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Common field name mappings (MCP field -> dostObject field)
# Supports dot notation for nested fields
FIELD_MAPPINGS = {
    "id": ["id", "listingId", "itemId", "productId", "restaurantId", "placeId", "_id"],
    "title": [
        "title", "name", "displayName", "heading", "label",
        # Nested paths for complex APIs
        "demandStayListing.description.name.localizedStringWithTranslationPreference",
        "demandStayListing.description.name",
        "listing.name", "listing.title",
    ],
    "description": [
        "description", "subtitle", "summary", "details", "about",
        "structuredContent.primaryLine",  # e.g., "1 bedroom, 1 queen bed"
    ],
    "rating": [
        "rating", "avgRating", "averageRating", "stars", "score",
        "avgRatingA11yLabel",
    ],
    "reviews": ["reviewsCount", "reviews", "reviewCount", "numReviews", "totalReviews"],
    "price": [
        "price", "pricePerNight", "totalPrice", "cost", "amount", "priceValue",
        "structuredDisplayPrice.primaryLine.accessibilityLabel",
    ],
    "currency": ["currency", "currencyCode", "currencySymbol"],
    "latitude": [
        "latitude", "lat", "y",
        "demandStayListing.location.coordinate.latitude",
        "coordinate.latitude", "location.lat", "geo.lat",
    ],
    "longitude": [
        "longitude", "lng", "lon", "x",
        "demandStayListing.location.coordinate.longitude",
        "coordinate.longitude", "location.lng", "geo.lon",
    ],
    "address": [
        "address", "fullAddress", "formattedAddress", "vicinity",
    ],
    "url": ["url", "link", "deeplink", "webUrl", "permalink"],
    "image": [
        "image", "thumbnail", "pictureUrl", "imageUrl", "photo", "coverImage",
    ],
    "images": ["images", "photos", "pictures", "gallery", "media", "contextualPictures"],
    "type": ["type", "category", "roomType", "listingType", "kind"],
    "tags": ["tags", "amenities", "features", "labels", "badges"],
}


def get_nested_value(obj: Any, path: str) -> Any:
    """
    Get a value from nested dict/list using dot notation.

    Examples:
        get_nested_value({"a": {"b": 1}}, "a.b") -> 1
        get_nested_value({"items": [{"x": 1}]}, "items.0.x") -> 1
    """
    parts = path.split(".")
    current = obj

    for part in parts:
        if current is None:
            return None

        # Try numeric index for lists
        if isinstance(current, list):
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            except ValueError:
                return None
        # Dict key access
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None

    return current


def is_meaningful_text(text: str) -> bool:
    """Check if text is meaningful (not a date, short code, etc.)."""
    if not text or len(text) < 5:
        return False
    # Skip date-like strings
    if re.match(r'^\d{1,2}[–\-/]\d{1,2}\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?', text, re.I):
        return False
    # Skip very short or numeric-only strings
    if text.replace(" ", "").isdigit():
        return False
    return True


def find_text_in_structure(obj: Any, max_depth: int = 5) -> Optional[str]:
    """
    Recursively find first meaningful text string in a complex structure.

    Useful for extracting titles/descriptions from nested API responses.
    Prefers longer, more meaningful text and avoids dates/codes.
    """
    if max_depth <= 0:
        return None

    if isinstance(obj, str) and is_meaningful_text(obj):
        return obj

    if isinstance(obj, dict):
        # Check common text field names first (prioritized order)
        priority_keys = [
            "localizedStringWithTranslationPreference",  # Common in i18n APIs
            "title", "name", "displayName", "heading",
            "body", "text", "value", "content", "displayText", "label"
        ]
        for key in priority_keys:
            if key in obj:
                val = obj[key]
                if isinstance(val, str) and is_meaningful_text(val):
                    return val
                elif isinstance(val, dict):
                    # Recurse one level for nested text
                    result = find_text_in_structure(val, max_depth - 1)
                    if result:
                        return result

        # Recurse into all values
        for val in obj.values():
            result = find_text_in_structure(val, max_depth - 1)
            if result:
                return result

    if isinstance(obj, list) and len(obj) > 0:
        result = find_text_in_structure(obj[0], max_depth - 1)
        if result:
            return result

    return None


def extract_field(item: Dict[str, Any], field_type: str) -> Any:
    """
    Extract a field from item using common field name mappings.

    Supports both direct field names and dot notation for nested fields.
    Falls back to searching complex nested structures.
    """
    possible_names = FIELD_MAPPINGS.get(field_type, [field_type])

    # First pass: direct field access
    for name in possible_names:
        # Check for dot notation (nested field)
        if "." in name:
            value = get_nested_value(item, name)
            if value is not None and not isinstance(value, (dict, list)):
                return value
        # Direct field access
        elif name in item:
            value = item[name]
            # If it's a simple value, return it
            if not isinstance(value, (dict, list)):
                return value

    # Second pass: search complex nested structures for text fields
    if field_type in ["title", "description", "address"]:
        # Common container keys for structured content
        container_keys = [
            "demandStayListing", "description", "name",
            "structuredContent", "primaryLine", "secondaryLine", "mapLine",
            "listing", "item", "data"
        ]
        for key in container_keys:
            if key in item:
                text = find_text_in_structure(item[key])
                if text:
                    return text

    # Third pass: search the entire item for text
    if field_type in ["title", "description"]:
        text = find_text_in_structure(item, max_depth=6)
        if text:
            return text

    return None


def parse_items_from_content(content: str) -> List[Dict[str, Any]]:
    """
    Parse items from MCP tool response content.

    Handles various formats:
    - JSON array: [...]
    - JSON object with array field: {"results": [...], "items": [...], etc}
    - Text with embedded JSON
    """
    if not content:
        return []

    try:
        data = json.loads(content)

        # If it's already a list, return it
        if isinstance(data, list):
            logger.info(f"Content is JSON array with {len(data)} items")
            return data

        # If it's an object, look for array fields
        if isinstance(data, dict):
            # Common keys that contain result arrays
            array_keys = [
                "searchResults", "results", "items", "data", "listings",
                "records", "entries", "objects", "list", "content",
                "restaurants", "places", "products", "hotels", "flights"
            ]
            for key in array_keys:
                if key in data and isinstance(data[key], list):
                    logger.info(f"Found {len(data[key])} items under '{key}'")
                    return data[key]

            # If no known key, look for any array field
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    logger.info(f"Found {len(value)} items under '{key}'")
                    return value

    except json.JSONDecodeError:
        logger.debug("Content is not valid JSON, trying to extract embedded JSON")

    # Try to extract JSON array from text
    json_match = re.search(r'\[[\s\S]*?\](?=\s*$|\s*[,}])', content)
    if json_match:
        try:
            items = json.loads(json_match.group())
            if isinstance(items, list):
                logger.info(f"Extracted {len(items)} items from embedded JSON")
                return items
        except json.JSONDecodeError:
            pass

    return []


def extract_images_from_item(item: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract images from item, handling various nested structures."""
    image_list = []

    # Try contextualPictures (common in listing APIs)
    ctx_pics = item.get("contextualPictures", [])
    if isinstance(ctx_pics, list):
        for pic in ctx_pics[:5]:
            if isinstance(pic, dict):
                pic_url = pic.get("picture") or pic.get("url") or pic.get("src")
                if pic_url:
                    image_list.append({"data-type": "url", "data": pic_url})

    # Try direct images field
    if not image_list:
        images = extract_field(item, "images") or []
        single_image = extract_field(item, "image")

        if single_image and not images:
            images = [single_image]

        for img in images[:5]:
            if isinstance(img, str):
                image_list.append({"data-type": "url", "data": img})
            elif isinstance(img, dict):
                img_url = (
                    img.get("url") or img.get("src") or img.get("link") or
                    img.get("picture") or img.get("imageUrl") or img.get("thumbnail")
                )
                if img_url:
                    image_list.append({"data-type": "url", "data": img_url})

    return image_list


def extract_tags_from_item(item: Dict[str, Any]) -> List[str]:
    """Extract tags from item, handling badges and other formats."""
    tags = []

    # Try badges field (string like "Guest favourite")
    badges = item.get("badges")
    if isinstance(badges, str) and badges:
        tags.append(badges)
    elif isinstance(badges, list):
        for badge in badges[:5]:
            if isinstance(badge, str):
                tags.append(badge)
            elif isinstance(badge, dict):
                badge_text = badge.get("text") or badge.get("label") or badge.get("name")
                if badge_text:
                    tags.append(badge_text)

    # Try amenities/features
    for field in ["amenities", "features", "tags"]:
        field_val = item.get(field)
        if isinstance(field_val, list):
            for val in field_val[:5]:
                if isinstance(val, str) and val not in tags:
                    tags.append(val)

    # Try structuredContent.primaryLine for room details
    primary_line = get_nested_value(item, "structuredContent.primaryLine")
    if isinstance(primary_line, str) and primary_line:
        # Extract room info like "1 bedroom, 1 queen bed"
        parts = [p.strip() for p in primary_line.split(",")]
        for part in parts[:3]:
            if part and part not in tags:
                tags.append(part)

    return tags[:10]  # Limit to 10 tags


def item_to_dost_object(item: Dict[str, Any], obj_type: str = "item") -> Dict[str, Any]:
    """
    Convert a generic item to dostObject format per DOST spec.

    Uses field mappings to find common fields regardless of source.
    All values are properly typed per spec:
    - latitude/longitude: string
    - price value: number (INR, reasonable range)
    """
    # Extract basic fields
    item_id = extract_field(item, "id") or str(hash(str(item)))[:12]
    title = extract_field(item, "title") or "Untitled"
    description = extract_field(item, "description")
    item_type = extract_field(item, "type") or obj_type

    # Build reputation from rating/reviews
    rating = extract_field(item, "rating")
    reviews = extract_field(item, "reviews")
    reputation = None
    if rating:
        # Clean rating string (e.g., "4.85 out of 5 average rating,  34 reviews")
        if isinstance(rating, str):
            # Extract just the numeric rating
            rating_match = re.search(r'([\d.]+)\s*(?:out of\s*5|/5)?', rating)
            if rating_match:
                rating_num = rating_match.group(1)
                reputation = f"{rating_num}/5"
                # Extract review count
                review_match = re.search(r'(\d+)\s*reviews?', rating)
                if review_match:
                    reputation += f" ({review_match.group(1)} reviews)"
        else:
            reputation = f"{rating}/5"
            if reviews:
                reputation += f" ({reviews} reviews)"

    # Build media with images
    media = None
    image_list = extract_images_from_item(item)
    if image_list:
        media = {"images": image_list}

    # Build location - handle deeply nested coordinate structures
    # Per spec: latitude and longitude must be STRINGS
    location = None
    lat = None
    lng = None

    # Search for coordinates in common nested paths
    coord_paths = [
        "demandStayListing.location.coordinate",
        "location.coordinate",
        "coordinate",
        "geo",
        "position",
    ]
    for path in coord_paths:
        coord = get_nested_value(item, path)
        if isinstance(coord, dict):
            lat = coord.get("latitude") or coord.get("lat")
            lng = coord.get("longitude") or coord.get("lng") or coord.get("lon")
            if lat and lng:
                break

    # Fallback to direct field extraction
    if not lat:
        lat = extract_field(item, "latitude")
    if not lng:
        lng = extract_field(item, "longitude")

    # Extract address for location
    address = extract_field(item, "address")
    # Skip encoded/base64-like addresses
    if address and isinstance(address, str):
        if re.match(r'^[A-Za-z0-9+/=]{20,}', address):
            address = None

    if lat or lng or address:
        loc_obj: Dict[str, Any] = {}
        # CRITICAL: Per DOST spec, latitude/longitude MUST be strings
        if lat is not None and not isinstance(lat, (dict, list)):
            try:
                lat_float = float(lat)
                # Use string formatting to ensure string type
                loc_obj["latitude"] = f"{lat_float}"
            except (ValueError, TypeError):
                pass
        if lng is not None and not isinstance(lng, (dict, list)):
            try:
                lng_float = float(lng)
                # Use string formatting to ensure string type
                loc_obj["longitude"] = f"{lng_float}"
            except (ValueError, TypeError):
                pass
        if address and isinstance(address, str) and len(address) > 3:
            loc_obj["address"] = address
        if loc_obj:
            location = [loc_obj]

    # Build pricing - extract from price label/text
    # Per spec: value is number in INR (reasonable range)
    pricing = None

    # Try to find price in structuredDisplayPrice
    price_text = get_nested_value(item, "structuredDisplayPrice.primaryLine.accessibilityLabel")
    if not price_text:
        price_text = extract_field(item, "price")

    if price_text and isinstance(price_text, str):
        # Extract price from text like "₹7,995 for 5 nights"
        # Look for currency symbol followed by number
        price_match = re.search(r'[₹$€£]\s*([\d,]+)', price_text)
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            try:
                price_value = float(price_str)
                # Sanity check: reasonable INR price (₹100 to ₹1,000,000)
                if 100 <= price_value <= 1000000:
                    pricing = [{
                        "id": f"price_{item_id}",
                        "value": price_value,
                        "maxQuantity": 1,
                        "durationType": "day",
                        "durationValue": 1
                    }]
            except ValueError:
                pass
    elif isinstance(price_text, (int, float)):
        # Direct numeric price
        if 100 <= price_text <= 1000000:
            pricing = [{
                "id": f"price_{item_id}",
                "value": float(price_text),
                "maxQuantity": 1,
                "durationType": "day",
                "durationValue": 1
            }]

    # Build actions
    url = extract_field(item, "url")
    actions = []
    if url:
        actions.append({
            "displayText": "View Details",
            "url": url
        })
        actions.append({
            "displayText": "Book Now",
            "prompt": f"Book this listing",
            "url": url
        })

    # Build tags
    tags = extract_tags_from_item(item)

    # Build dostObject per spec
    dost_obj: Dict[str, Any] = {
        "id": str(item_id),
        "type": item_type,
        "title": str(title),
        "description": str(description) if description else None,
        "reputation": reputation
    }

    if media:
        dost_obj["media"] = media
    if location:
        dost_obj["location"] = location
    if pricing:
        dost_obj["pricing"] = pricing
    if actions:
        dost_obj["actions"] = actions
    if tags:
        dost_obj["tags"] = tags

    return dost_obj


# =============================================================================
# Detail Response Detection and Consolidation
# =============================================================================
# When an MCP tool returns details for a SINGLE entity (e.g., listing details,
# flight info, restaurant menu), the response often contains multiple "sections"
# like LOCATION, AMENITIES, POLICIES, etc. These should be consolidated into
# ONE dostObject, not multiple.

# Patterns in item IDs that indicate they are "sections" of one entity
SECTION_ID_PATTERNS = [
    "_DEFAULT", "SECTION_", "_SECTION", "_INFO", "_DETAILS",
    "LOCATION", "AMENITIES", "POLICIES", "DESCRIPTION", "HIGHLIGHTS",
    "PRICING", "REVIEWS", "PHOTOS", "RULES", "AVAILABILITY"
]


def is_detail_response(tool_name: str, items: List[Dict[str, Any]]) -> bool:
    """
    Dynamically detect if this is a single-entity detail response vs multi-entity list.

    Works generically for ANY domain (hotels, flights, food, rides, etc.)

    Detection strategy (in order of priority):
    1. Item structure analysis - most reliable
       - Section-like IDs (LOCATION_DEFAULT, AMENITIES_DEFAULT, etc.)
       - Items have different structures (detail sections) vs similar structures (search results)
    2. Tool name heuristics - fallback
       - Words like "detail", "info", "view" indicate single entity
       - Words like "search", "find", "browse" indicate multiple entities
    """
    # ==========================================================================
    # PRIMARY: Analyze item structure (most reliable, domain-agnostic)
    # ==========================================================================
    if items:
        # Check 1: Do items have section-like IDs?
        section_count = 0
        for item in items:
            item_id = str(item.get("id", "")).upper()
            if any(pattern in item_id for pattern in SECTION_ID_PATTERNS):
                section_count += 1

        # If majority of items have section-like IDs, it's a detail response
        if section_count > len(items) / 2:
            logger.debug(f"Detected detail response: {section_count}/{len(items)} items have section-like IDs")
            return True

        # Check 2: Do items have vastly different key structures?
        # (Search results have similar keys, detail sections have different keys)
        if len(items) >= 2:
            key_sets = [set(item.keys()) for item in items if isinstance(item, dict)]
            if key_sets:
                # Calculate average Jaccard similarity between consecutive items
                similarities = []
                for i in range(len(key_sets) - 1):
                    intersection = len(key_sets[i] & key_sets[i + 1])
                    union = len(key_sets[i] | key_sets[i + 1])
                    if union > 0:
                        similarities.append(intersection / union)

                if similarities:
                    avg_similarity = sum(similarities) / len(similarities)
                    # Low similarity = different structures = detail sections
                    if avg_similarity < 0.5:
                        logger.debug(f"Detected detail response: low key similarity ({avg_similarity:.2f})")
                        return True

    # ==========================================================================
    # SECONDARY: Tool name heuristics (fallback)
    # ==========================================================================
    # Split tool name into words for precise matching
    # e.g., "airbnb_listing_details" -> ["airbnb", "listing", "details"]
    name_words = set(re.split(r'[_\-\s]+', tool_name.lower()))

    # Detail keywords (single entity)
    detail_words = {"detail", "details", "info", "view", "get", "fetch", "show",
                    "booking", "reservation", "order", "trip", "ride", "profile"}

    # Search keywords (multiple entities)
    search_words = {"search", "list", "find", "browse", "explore", "discover",
                    "nearby", "results", "query", "lookup"}

    has_detail_word = bool(name_words & detail_words)
    has_search_word = bool(name_words & search_words)

    # Detail keyword without search keyword = detail response
    if has_detail_word and not has_search_word:
        logger.debug(f"Detected detail response: tool name has detail keywords")
        return True

    # Search keyword = not a detail response
    if has_search_word:
        logger.debug(f"Detected search response: tool name has search keywords")
        return False

    # ==========================================================================
    # DEFAULT: Assume search/list response (safer default)
    # ==========================================================================
    return False


def consolidate_detail_sections(
    items: List[Dict[str, Any]],
    tool_name: str,
    content: str
) -> Dict[str, Any]:
    """
    Consolidate multiple sections into a single dostObject.

    Generic implementation that works for any domain by extracting
    the best value for each field from all sections.

    Args:
        items: List of section items from the detail response
        tool_name: Name of the tool (for type inference)
        content: Raw content string (for extracting entity ID from URL)

    Returns:
        Single consolidated dostObject
    """
    obj_type = infer_object_type(tool_name)

    # Initialize consolidated object
    consolidated: Dict[str, Any] = {
        "id": None,
        "title": None,
        "description": None,
        "location": None,
        "pricing": None,
        "tags": [],
        "media": None,
        "reputation": None,
        "actions": [],
    }

    # ==========================================================================
    # STEP 1: Extract from raw content JSON (look for entity-level data)
    # ==========================================================================
    entity_url = None
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # Skip array containers (like "details", "sections") - those are handled in STEP 2
            # Only extract from root if it has actual entity data
            root_has_entity_data = any(
                data.get(k) for k in ["title", "name", "listingTitle", "displayName", "id", "listingId"]
            )

            if root_has_entity_data:
                # Extract entity ID from root or URL
                consolidated["id"] = data.get("id") or data.get("listingId") or data.get("entityId")

                # Extract title from root level (most reliable)
                consolidated["title"] = (
                    data.get("title") or data.get("name") or
                    data.get("listingTitle") or data.get("displayName") or
                    data.get("heading")
                )

                # Extract description from root (only if it's a string, not a dict/list)
                desc = data.get("description") or data.get("summary") or data.get("about")
                if desc and isinstance(desc, str):
                    consolidated["description"] = desc[:500]

                # Extract URL from root
                entity_url = data.get("url") or data.get("link") or data.get("webUrl")

                # Extract rating from root
                rating = data.get("rating") or data.get("avgRating") or data.get("stars")
                reviews = data.get("reviewsCount") or data.get("reviews")
                if rating:
                    if isinstance(rating, (int, float)):
                        consolidated["reputation"] = f"{rating}/5"
                        if reviews:
                            consolidated["reputation"] += f" ({reviews} reviews)"
                    elif isinstance(rating, str):
                        consolidated["reputation"] = rating

                # Extract price from root
                price = data.get("price") or data.get("totalPrice") or data.get("cost")
                if isinstance(price, (int, float)) and 100 <= price <= 1000000:
                    consolidated["pricing"] = [{
                        "id": f"price_{consolidated.get('id') or 'item'}",
                        "value": float(price),
                        "maxQuantity": 1,
                        "durationType": "day",
                        "durationValue": 1
                    }]

    except json.JSONDecodeError:
        pass

    # Try to extract entity ID from URL in content if not found
    if not consolidated["id"]:
        url_match = re.search(r'https?://[^\s"]+/(\d+)', content)
        if url_match:
            consolidated["id"] = url_match.group(1)

    # Try to extract full URL for actions if not found
    if not entity_url:
        full_url_match = re.search(r'(https?://[^\s"]+)', content)
        entity_url = full_url_match.group(1) if full_url_match else None

    # ==========================================================================
    # STEP 2: Process sections to extract additional data
    # ==========================================================================
    # Generic section titles to skip when looking for entity title
    skip_titles = {
        "where you'll be", "where you'll be", "things to know", "what this place offers",
        "house rules", "safety & property", "cancellation policy", "about this place",
        "highlights_default", "description_default", "amenities_default",
        "policies_default", "location_default", "location", "amenities",
        "policies", "description", "highlights", "reviews", "photos"
    }

    for item in items:
        item_id = str(item.get("id", "")).upper()

        # ------------------------------------------------------------------
        # Extract location from LOCATION sections
        # ------------------------------------------------------------------
        if "LOCATION" in item_id or item.get("lat") or item.get("latitude"):
            lat = item.get("lat") or item.get("latitude") or get_nested_value(item, "coordinate.latitude")
            lng = item.get("lng") or item.get("longitude") or get_nested_value(item, "coordinate.longitude")
            addr = item.get("subtitle") or item.get("address") or item.get("formattedAddress")

            # Don't use section title as address
            if addr and addr.lower() in skip_titles:
                addr = item.get("description") if item.get("description", "").lower() not in skip_titles else None

            if lat and lng and not consolidated["location"]:
                loc_obj: Dict[str, Any] = {}
                try:
                    loc_obj["latitude"] = f"{float(lat)}"
                    loc_obj["longitude"] = f"{float(lng)}"
                except (ValueError, TypeError):
                    pass
                if addr and isinstance(addr, str) and len(addr) > 3:
                    loc_obj["address"] = addr
                if loc_obj:
                    consolidated["location"] = [loc_obj]

        # ------------------------------------------------------------------
        # Extract description from DESCRIPTION sections
        # ------------------------------------------------------------------
        if "DESCRIPTION" in item_id and not consolidated["description"]:
            # Try nested htmlDescription.htmlText first (common pattern)
            html_desc = item.get("htmlDescription")
            if isinstance(html_desc, dict):
                html_text = html_desc.get("htmlText") or html_desc.get("text") or html_desc.get("html")
                if html_text and isinstance(html_text, str):
                    # Strip HTML tags
                    clean_desc = re.sub(r'<[^>]+>', ' ', html_text)
                    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                    # Take first 500 chars as description
                    consolidated["description"] = clean_desc[:500]
                    # Also extract title from first sentence if not found
                    if not consolidated["title"] or consolidated["title"] == "Details":
                        # Try to extract a meaningful title from first part
                        first_sentence = clean_desc.split('.')[0]
                        if len(first_sentence) < 100:
                            consolidated["title"] = first_sentence

            # Fallback to direct text fields
            if not consolidated["description"]:
                desc_sources = [
                    item.get("description"),
                    item.get("body"),
                    item.get("content"),
                    item.get("text"),
                    item.get("summary"),
                ]
                for src in desc_sources:
                    if src and isinstance(src, str) and len(src) > 20:
                        clean_desc = re.sub(r'<[^>]+>', ' ', src)
                        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                        consolidated["description"] = clean_desc[:500]
                        break

        # ------------------------------------------------------------------
        # Extract amenities/features from AMENITIES sections
        # ------------------------------------------------------------------
        if "AMENITIES" in item_id or "FEATURES" in item_id or "HIGHLIGHT" in item_id:
            # Try multiple keys where amenities might be stored
            amenity_sources = [
                item.get("amenities"),
                item.get("features"),
                item.get("items"),
                item.get("highlights"),
                item.get("seeAllAmenitiesGroups"),
            ]
            for amenities in amenity_sources:
                if amenities is None:
                    continue

                # Handle string format: "Bathroom: Shampoo, Body soap, Kitchen: Fridge, ..."
                if isinstance(amenities, str):
                    # Split by comma and extract individual items
                    parts = amenities.split(', ')
                    for part in parts[:20]:
                        # Skip category labels like "Bathroom:", "Kitchen:"
                        if ':' in part:
                            # Take the item after the colon if it's a value
                            after_colon = part.split(':', 1)[1].strip()
                            if after_colon and len(after_colon) > 2:
                                tag = after_colon
                            else:
                                continue
                        else:
                            tag = part.strip()

                        if tag and tag not in consolidated["tags"]:
                            if tag.lower() not in skip_titles and len(tag) > 2:
                                consolidated["tags"].append(tag)

                # Handle list format
                elif isinstance(amenities, list):
                    for amenity in amenities[:15]:
                        tag = None
                        if isinstance(amenity, str):
                            tag = amenity
                        elif isinstance(amenity, dict):
                            tag = (
                                amenity.get("title") or amenity.get("name") or
                                amenity.get("label") or amenity.get("headline") or
                                amenity.get("text")
                            )
                        if tag and isinstance(tag, str) and tag not in consolidated["tags"]:
                            if tag.lower() not in skip_titles and len(tag) > 2:
                                consolidated["tags"].append(tag)

        # ------------------------------------------------------------------
        # Extract title from section if not found at root
        # ------------------------------------------------------------------
        if not consolidated["title"]:
            item_title = item.get("listingTitle") or item.get("name") or item.get("heading")
            if item_title and isinstance(item_title, str):
                if item_title.lower() not in skip_titles:
                    consolidated["title"] = item_title

        # ------------------------------------------------------------------
        # Extract images from any section
        # ------------------------------------------------------------------
        if not consolidated["media"]:
            images = item.get("images") or item.get("photos") or item.get("pictures") or []
            if isinstance(images, list) and images:
                image_list = []
                for img in images[:5]:
                    if isinstance(img, str):
                        image_list.append({"data-type": "url", "data": img})
                    elif isinstance(img, dict):
                        img_url = img.get("url") or img.get("src") or img.get("picture")
                        if img_url:
                            image_list.append({"data-type": "url", "data": img_url})
                if image_list:
                    consolidated["media"] = {"images": image_list}

        # ------------------------------------------------------------------
        # Extract pricing from section if not found
        # ------------------------------------------------------------------
        if not consolidated["pricing"]:
            price = item.get("price") or item.get("totalPrice") or item.get("cost")
            if isinstance(price, (int, float)) and 100 <= price <= 1000000:
                consolidated["pricing"] = [{
                    "id": f"price_{consolidated.get('id') or 'item'}",
                    "value": float(price),
                    "maxQuantity": 1,
                    "durationType": "day",
                    "durationValue": 1
                }]

    # ==========================================================================
    # STEP 3: Build actions from URL
    # ==========================================================================
    if entity_url:
        consolidated["actions"] = [
            {"displayText": "View Details", "url": entity_url},
            {"displayText": "Book Now", "prompt": "Book this item", "url": entity_url}
        ]

    # ==========================================================================
    # STEP 4: Fallbacks for required fields
    # ==========================================================================
    if not consolidated["title"]:
        consolidated["title"] = "Details"

    if not consolidated["id"]:
        consolidated["id"] = f"detail_{abs(hash(content)) % 10**12}"

    # ==========================================================================
    # STEP 5: Build final dostObject
    # ==========================================================================
    dost_obj: Dict[str, Any] = {
        "id": str(consolidated["id"]),
        "type": obj_type,
        "title": str(consolidated["title"]),
        "description": consolidated["description"],
        "reputation": consolidated["reputation"]
    }

    if consolidated["media"]:
        dost_obj["media"] = consolidated["media"]
    if consolidated["location"]:
        dost_obj["location"] = consolidated["location"]
    if consolidated["pricing"]:
        dost_obj["pricing"] = consolidated["pricing"]
    if consolidated["actions"]:
        dost_obj["actions"] = consolidated["actions"]
    if consolidated["tags"]:
        dost_obj["tags"] = consolidated["tags"][:10]

    return dost_obj


# Keyword-based category inference (generic, no brand names)
CATEGORY_KEYWORDS = {
    "Accommodations": ["hotel", "stay", "room", "listing", "property", "lodging", "accommodation", "rental", "bnb"],
    "Restaurants": ["restaurant", "food", "dining", "eat", "cuisine", "cafe", "menu"],
    "Flights": ["flight", "airline", "travel", "booking", "trip"],
    "Products": ["product", "shop", "item", "goods", "merchandise", "store"],
    "Events": ["event", "ticket", "show", "concert", "movie"],
    "Services": ["service", "booking", "appointment", "schedule"],
}

# Keyword-based type inference (generic)
TYPE_KEYWORDS = {
    "accommodation": ["hotel", "stay", "room", "listing", "property", "lodging", "rental", "bnb"],
    "restaurant": ["restaurant", "food", "dining", "eat", "cuisine", "cafe"],
    "flight": ["flight", "airline"],
    "product": ["product", "shop", "item", "goods"],
    "event": ["event", "ticket", "show"],
    "service": ["service", "booking"],
}


def infer_category_title(tool_name: str) -> str:
    """Infer a category title from the tool name using keywords."""
    name_lower = tool_name.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return category

    # Default: convert tool_name to title case
    return tool_name.replace("_", " ").replace("-", " ").title()


def infer_object_type(tool_name: str) -> str:
    """Infer object type from tool name using keywords."""
    name_lower = tool_name.lower()

    for obj_type, keywords in TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return obj_type

    return "item"


def infer_event_hint(tool_results: List[Dict[str, Any]]) -> str:
    """Infer an appropriate eventHint from tool results."""
    for result in tool_results:
        tool_name = result.get("name", "").lower()
        if result.get("is_error"):
            continue

        # Map tool names to idiomatic event hints
        if any(kw in tool_name for kw in ["hotel", "stay", "room", "listing", "accommodation", "rental", "bnb"]):
            return "accommodation_list"
        if any(kw in tool_name for kw in ["restaurant", "food", "dining", "cafe"]):
            return "restaurant_list"
        if any(kw in tool_name for kw in ["flight", "airline"]):
            return "flight_list"
        if any(kw in tool_name for kw in ["product", "shop", "item"]):
            return "product_list"
        if any(kw in tool_name for kw in ["search"]):
            return "search_response"

    return "listing_response"


def build_dost_categories(
    tool_results: List[Dict[str, Any]],
    currency: str = "INR"
) -> Optional[Dict[str, Any]]:
    """
    Build dostCategories from tool results.

    Generic implementation that works with ANY MCP tool:
    - For SEARCH responses: Creates multiple dostObjects (one per result)
    - For DETAIL responses: Consolidates sections into ONE dostObject

    Args:
        tool_results: List of tool call results with name and content
        currency: Default currency

    Returns:
        dostCategories dict or None if no structured data
    """
    all_objects: List[Dict[str, Any]] = []
    category_title = "Results"

    for result in tool_results:
        tool_name = result.get("name", "")
        content = result.get("content", "")
        is_error = result.get("is_error", False)

        if is_error:
            logger.debug(f"Skipping error result from {tool_name}")
            continue

        logger.info(f"Processing tool result: {tool_name}")

        # Parse items from content
        items = parse_items_from_content(content)

        if items:
            category_title = infer_category_title(tool_name)
            obj_type = infer_object_type(tool_name)

            # Log first item's keys for debugging
            if items and isinstance(items[0], dict):
                logger.info(f"Sample item keys: {list(items[0].keys())}")

            # Check if this is a DETAIL response (single entity with sections)
            # vs a SEARCH response (multiple entities)
            if is_detail_response(tool_name, items):
                logger.info(f"Detected DETAIL response - consolidating {len(items)} sections into 1 object")
                # Consolidate all sections into ONE dostObject
                consolidated_obj = consolidate_detail_sections(items, tool_name, content)
                all_objects.append(consolidated_obj)
                # Update category title for detail view
                category_title = "Details"
            else:
                # SEARCH response - each item becomes a separate dostObject
                logger.info(f"Detected SEARCH response - converting {len(items)} items to dostObjects")
                for item in items:
                    if isinstance(item, dict):
                        dost_obj = item_to_dost_object(item, obj_type)
                        all_objects.append(dost_obj)

    logger.info(f"Total dostObjects created: {len(all_objects)}")

    if not all_objects:
        return None

    return {
        "currency": currency,
        "categories": [
            {
                "title": category_title,
                "objects": all_objects
            }
        ]
    }
