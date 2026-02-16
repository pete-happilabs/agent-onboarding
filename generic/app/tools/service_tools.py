"""
Service tools for UrbanBot AI Agent.

Uses ChromaDB-based semantic search for intelligent service matching
and MongoDB for booking persistence. All tools are LangChain @tool
functions consumed by the agent via URBAN_BOT_TOOLS.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pymongo import MongoClient
from pymongo.database import Database
from pydantic import BaseModel, Field

from app.core.vector_store import get_vector_store
from config import MongoDBConfig

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Pydantic models (type safety for service data)
# -----------------------------------------------------------------------------


class ServiceModel(BaseModel):
    """Type-safe representation of a service from the vector store."""

    id: str = Field(..., description="Service ID (e.g. srv_1001)")
    name: str = Field(..., description="Service display name")
    category: str = Field(..., description="Category name (e.g. Plumbing, Cleaning)")
    description: str = Field(..., description="Service description")
    availability: List[str] = Field(default_factory=list, description="City names where service is available")
    pricing: Dict[str, Any] = Field(default_factory=dict, description="Pricing info (base_price, rules, etc.)")
    rating: Optional[float] = Field(None, description="Optional average rating")
    reviews_count: Optional[int] = Field(None, description="Optional number of reviews")


class ServiceSearchResult(BaseModel):
    """Structured search result with services and applied filters."""

    services: List[ServiceModel] = Field(default_factory=list, description="Matching services")
    total_count: int = Field(..., description="Number of services returned")
    filters_applied: Dict[str, str] = Field(default_factory=dict, description="Active filters (e.g. city, category)")


def _dict_to_service_model(d: Dict[str, Any]) -> ServiceModel:
    """Build a ServiceModel from the raw service dict returned by the vector store."""
    availability_raw = d.get("availability") or []
    return ServiceModel(
        id=d.get("service_id", ""),
        name=d.get("name", ""),
        category=(d.get("category") or {}).get("name", ""),
        description=d.get("description", ""),
        availability=[a.get("city_name", "") for a in availability_raw],
        pricing=d.get("pricing", {}),
        rating=d.get("rating"),
        reviews_count=d.get("reviews_count"),
    )


# -----------------------------------------------------------------------------
# MongoDB connection (sync; LangChain tools are synchronous)
# -----------------------------------------------------------------------------

_sync_client: Optional[MongoClient] = None


def _get_sync_db() -> Database:
    """
    Return the synchronous MongoDB database instance for tools.

    Uses a module-level client singleton. Thread-safe for typical
    single-threaded agent usage.
    """
    global _sync_client
    if _sync_client is None:
        _sync_client = MongoClient(MongoDBConfig.URI)
    return _sync_client[MongoDBConfig.DATABASE_NAME]


# -----------------------------------------------------------------------------
# City normalization
# -----------------------------------------------------------------------------

CITY_ALIASES: Dict[str, str] = {
    "bengaluru": "bangaluru",
    "bengalore": "bangaluru",
    "bangalore": "bangaluru",
    "blr": "bangaluru",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "delhi": "delhi",
    "new delhi": "delhi",
    "ncr": "delhi",
}


def _normalize_city(city: str) -> str:
    """Return canonical city name for matching (lowercase, alias-resolved)."""
    return CITY_ALIASES.get(city.lower().strip(), city.lower().strip())


def _service_passes_filters(
    service: ServiceModel,
    city_normalized: str,
    category_lower: str,
) -> bool:
    """
    Return True if the service passes optional city and category filters.

    Args:
        service: Type-safe service model with availability (city names) and category.
        city_normalized: Canonical city name, or empty string for no filter.
        category_lower: Lowercase category substring, or empty for no filter.

    Returns:
        True when all non-empty filters match.
    """
    if city_normalized:
        service_cities = [_normalize_city(c) for c in service.availability]
        if city_normalized not in service_cities:
            return False
    if category_lower:
        cat_name = service.category.lower()
        if not (category_lower in cat_name or cat_name in category_lower):
            return False
    return True


# -----------------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------------


class BookingCreate(BaseModel):
    """Input model for creating a booking."""

    service_id: str = Field(..., description="Service ID (e.g. srv_1001)")
    customer_name: str = Field(..., description="Customer full name")
    phone: str = Field(..., description="10-digit phone number")
    address: str = Field(..., description="Full address")
    city: str = Field(..., description="City name")
    preferred_date: str = Field(..., description="Date in DD-MM-YYYY format")
    preferred_time_slot: str = Field(..., description="Time slot (e.g. 10:00-12:00)")
    user_id: str = Field(..., description="User/session identifier")


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------


@tool
def search_services(query: str, city: str = "", category: str = "") -> str:
    """
    Search for services using semantic search.

    Understands natural language and finds relevant services (handles typos/synonyms).
    Optionally filter by city and/or category.

    Args:
        query: Natural language description of what the user needs.
        city: Optional city filter (e.g. Mumbai, Delhi, Bangaluru).
        category: Optional category filter (e.g. Plumbing, Cleaning, Appliances).

    Returns:
        Formatted list of matching services with IDs, pricing, and availability.
    """
    logger.info("=== SEARCH_SERVICES CALLED === query=%r city=%r category=%r", query, city, category)

    try:
        vector_store = get_vector_store()
        results = vector_store.search(query, top_k=10)
    except Exception as e:
        logger.exception("Vector store search failed")
        return "Service search is temporarily unavailable. Please try again later."

    if not results:
        return "No services found matching your query. Please try describing what you need differently."

    city_norm = _normalize_city(city) if city else ""
    category_norm = category.lower().strip() if category else ""

    filtered: List[Dict[str, Any]] = []
    for result in results:
        raw = result["service"]
        sim = result["similarity"]
        if sim < 0.25:
            continue
        sm = _dict_to_service_model(raw)
        if not _service_passes_filters(sm, city_norm, category_norm):
            continue
        filtered.append(result)

    logger.info("After filtering: %d results", len(filtered))

    if not filtered:
        parts = []
        if city_norm:
            parts.append(f"in {city}")
        if category_norm:
            parts.append(f"in category '{category}'")
        msg = " and ".join(parts) if parts else ""
        return f"No services matching '{query}' {msg}. Try adjusting your filters."

    filters_applied: Dict[str, str] = {}
    if city_norm:
        filters_applied["city"] = city
    if category_norm:
        filters_applied["category"] = category

    search_result = ServiceSearchResult(
        services=[_dict_to_service_model(r["service"]) for r in filtered],
        total_count=len(filtered),
        filters_applied=filters_applied,
    )

    # Build response from ServiceSearchResult
    filter_parts = []
    if city_norm:
        filter_parts.append(f"in {city.title()}")
    if category_norm:
        filter_parts.append(f"in {category.title()} category")
    filter_text = " ".join(filter_parts) if filter_parts else "matching your request"
    lines = [f"Found {search_result.total_count} service(s) {filter_text}:\n"]

    for idx, sm in enumerate(search_result.services[:5], 1):
        cities = ", ".join(sm.availability)
        rules = sm.pricing.get("rules", [])
        has_addons = any(
            r.get("rule_type") in ("HOURLY", "PARTS", "ADDON", "EXTRA") for r in rules
        )
        base = sm.pricing.get("base_price", 0)
        duration = sm.pricing.get("base_duration_minutes", 0)
        lines.append(
            f"{idx}. {sm.name}\n"
            f"   ID: {sm.id}\n"
            f"   Category: {sm.category}\n"
            f"   Base Price: Rs.{base} for {duration} min\n"
            f"   Available in: {cities}\n"
        )
        if has_addons:
            lines.append("   Has add-ons/extra charges available\n")
        lines.append(f"   {sm.description}\n")

    return "\n".join(lines)


@tool
def get_service_details(service_id: str) -> str:
    """
    Get full details for a service by ID.

    Args:
        service_id: The service ID (e.g. srv_1001).

    Returns:
        Service info including pricing, availability, and policies.
    """
    try:
        vector_store = get_vector_store()
        service = vector_store.get_service_by_id(service_id)
    except Exception as e:
        logger.exception("Failed to fetch service details")
        return "Unable to load service details. Please try again later."

    if not service:
        return f"Service with ID {service_id} not found."

    availability = service.get("availability") or []
    cities = ", ".join(a["city_name"] for a in availability)
    time_slots = ", ".join(availability[0]["time_slots"]) if availability else ""

    details = [
        f"Service: {service['name']}",
        f"ID: {service['service_id']}",
        f"Category: {service['category']['name']} > {service['subcategory']['name']}",
        f"Description: {service['description']}",
        "\nPRICING:",
        f"  Base Price: Rs.{service['pricing']['base_price']} (for {service['pricing']['base_duration_minutes']} minutes)",
    ]
    for rule in service.get("pricing", {}).get("rules", []):
        if rule.get("value"):
            details.append(f"  - {rule['rule_type']}: Rs.{rule['value']} - {rule.get('notes', '')}")
        elif rule.get("notes"):
            details.append(f"  - {rule['rule_type']}: {rule['notes']}")

    details.extend(["\nAVAILABILITY:", f"  Cities: {cities}", f"  Time Slots: {time_slots}"])

    if service.get("policies"):
        details.append("\nPOLICIES:")
        for policy in service["policies"]:
            details.append(f"  - {policy['policy_type']}: {policy['details']}")

    return "\n".join(details)


@tool
def list_all_services(city: str = "", category: str = "") -> str:
    """
    List all available services, optionally filtered by city and/or category.

    Use city/category when the user asks for services in a specific place or category.

    Args:
        city: Optional city filter (e.g. Mumbai, Delhi, Bangaluru).
        category: Optional category filter (e.g. Plumbing, Cleaning).

    Returns:
        Services grouped by category with IDs and base prices.
    """
    logger.info("=== LIST_ALL_SERVICES CALLED === city=%r category=%r", city, category)

    try:
        vector_store = get_vector_store()
        services = vector_store.get_all_services()
    except Exception as e:
        logger.exception("Failed to list services")
        return "Unable to load services. Please try again later."

    city_norm = _normalize_city(city) if city else ""
    category_norm = category.lower().strip() if category else ""

    service_models = [_dict_to_service_model(s) for s in services]
    if city_norm:
        service_models = [sm for sm in service_models if _service_passes_filters(sm, city_norm, "")]
        if not service_models:
            return f"No services are currently available in {city}. We currently operate in: Delhi, Mumbai, Bangaluru."

    if category_norm:
        service_models = [sm for sm in service_models if _service_passes_filters(sm, "", category_norm)]
        if not service_models:
            return (
                f"No services found in category '{category}'. "
                "Available categories: Plumbing, Cleaning, Appliances, Salon for Men, "
                "Salon for Women, Painting, Pest Control, Electrician, Massage, Car Care."
            )

    filters_applied: Dict[str, str] = {}
    if city_norm:
        filters_applied["city"] = city
    if category_norm:
        filters_applied["category"] = category

    search_result = ServiceSearchResult(
        services=service_models,
        total_count=len(service_models),
        filters_applied=filters_applied,
    )

    by_category: Dict[str, List[ServiceModel]] = {}
    for sm in search_result.services:
        if sm.category not in by_category:
            by_category[sm.category] = []
        by_category[sm.category].append(sm)

    filter_parts = []
    if city_norm:
        filter_parts.append(f"in {city.title()}")
    if category_norm:
        filter_parts.append(f"in {category.title()} category")

    if filter_parts:
        lines = [f"Services available {' '.join(filter_parts)}:\n"]
    else:
        lines = ["Available Services by Category:\n"]

    for cat_name, cat_services in by_category.items():
        lines.append(f"\n{cat_name}:")
        for sm in cat_services:
            cities_str = ", ".join(sm.availability)
            base_price = sm.pricing.get("base_price", 0)
            if city_norm:
                lines.append(f"  - {sm.name} (ID: {sm.id}) - Rs.{base_price}")
            else:
                lines.append(f"  - {sm.name} (ID: {sm.id}) - Rs.{base_price} [Available in: {cities_str}]")

    return "\n".join(lines)


@tool
def save_booking(
    service_id: str,
    customer_name: str,
    phone: str,
    address: str,
    city: str,
    preferred_date: str,
    preferred_time_slot: str,
    user_id: str,
) -> str:
    """
    Save a booking for a service.

    Call this only after confirming city availability and collecting all details.
    Use user_id from session state.

    Args:
        service_id: Service ID (e.g. srv_1001).
        customer_name: Customer full name.
        phone: 10-digit phone number.
        address: Full address.
        city: City name.
        preferred_date: Date in DD-MM-YYYY format.
        preferred_time_slot: Time slot (e.g. 10:00-12:00).
        user_id: User/session identifier.

    Returns:
        Booking confirmation with booking ID, or an error message.
    """
    try:
        payload = BookingCreate(
            service_id=service_id,
            customer_name=customer_name,
            phone=phone,
            address=address,
            city=city,
            preferred_date=preferred_date,
            preferred_time_slot=preferred_time_slot,
            user_id=user_id,
        )
    except Exception as e:
        logger.warning("Invalid booking payload: %s", e)
        return f"Invalid booking details: {e!s}"

    try:
        vector_store = get_vector_store()
        service = vector_store.get_service_by_id(payload.service_id)
    except Exception as e:
        logger.exception("Failed to load service for booking")
        return "Unable to verify service. Please try again later."

    if not service:
        return f"Error: Service {payload.service_id} not found."

    service_model = _dict_to_service_model(service)
    city_norm = _normalize_city(payload.city)
    if not _service_passes_filters(service_model, city_norm, ""):
        available_list = ", ".join(service_model.availability)
        return (
            f"Error: {service['name']} is not available in {payload.city}. "
            f"This service is only available in: {available_list}. "
            "Please choose a different city or service."
        )

    valid_slots: List[str] = []
    for a in service["availability"]:
        valid_slots.extend(a.get("time_slots", []))
    if payload.preferred_time_slot not in valid_slots:
        return (
            f"Error: Invalid time slot '{payload.preferred_time_slot}'. "
            f"Available time slots are: {', '.join(valid_slots)}"
        )

    booking_id = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"
    record = {
        "booking_id": booking_id,
        "session_id": payload.user_id,
        "service_id": payload.service_id,
        "service_name": service["name"],
        "customer_name": payload.customer_name,
        "phone": payload.phone,
        "address": payload.address,
        "city": payload.city,
        "preferred_date": payload.preferred_date,
        "preferred_time_slot": payload.preferred_time_slot,
        "created_at": datetime.now(),
        "status": "confirmed",
    }

    try:
        db = _get_sync_db()
        db[MongoDBConfig.BOOKINGS_COLLECTION].insert_one(record)
        logger.info("Booking saved: %s for session %s", booking_id, payload.user_id)
        return (
            "BOOKING CONFIRMED!\n\n"
            "Booking Details:\n"
            f"   - Booking ID: {booking_id}\n"
            f"   - Service: {service['name']}\n"
            f"   - Date: {payload.preferred_date}\n"
            f"   - Time: {payload.preferred_time_slot}\n"
            f"   - Location: {payload.address}, {payload.city}\n"
            f"   - Contact: {payload.phone}\n"
            f"   - Base Price: Rs.{service['pricing']['base_price']}\n\n"
            "Thank you for choosing UrbanBot!"
        )
    except Exception as e:
        logger.error("Booking save failed: %s", e)
        return f"Error saving booking: {e!s}"


@tool
def get_user_bookings(user_id: str) -> str:
    """
    Get all bookings for a user/session.

    Args:
        user_id: Session identifier (from agent state).

    Returns:
        Formatted list of the user's bookings, or a short message if none.
    """
    try:
        db = _get_sync_db()
        cursor = db[MongoDBConfig.BOOKINGS_COLLECTION].find({"session_id": user_id}).sort(
            "created_at", -1
        )
        user_bookings = list(cursor)
    except Exception as e:
        logger.exception("Failed to retrieve bookings")
        return "Unable to retrieve bookings. Please try again later."

    if not user_bookings:
        return "You don't have any bookings yet. Would you like to book a service?"

    status_label = {"confirmed": "Confirmed", "pending": "Pending", "completed": "Completed", "cancelled": "Cancelled"}
    n = len(user_bookings)
    lines = [f"Your Booking History ({n} booking{'s' if n > 1 else ''})\n"]
    for idx, b in enumerate(user_bookings, 1):
        status = status_label.get(b.get("status", "confirmed"), "-")
        lines.extend([
            f"{idx}. [{status}] {b.get('service_name', 'Unknown')}",
            f"   ID: {b.get('booking_id', 'N/A')}",
            f"   Date: {b.get('preferred_date', 'N/A')} at {b.get('preferred_time_slot', 'N/A')}",
            f"   Location: {b.get('address', 'N/A')}, {b.get('city', 'N/A')}",
            "",
        ])
    return "\n".join(lines)


URBAN_BOT_TOOLS = [
    search_services,
    get_service_details,
    list_all_services,
    save_booking,
    get_user_bookings,
]

# Export tools for domain registry / generic agent loading
TOOLS = [
    search_services,
    list_all_services,
    get_service_details,
    save_booking,
    get_user_bookings,
]

