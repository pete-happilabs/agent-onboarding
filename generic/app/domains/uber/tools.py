"""
Uber ride booking tools (mock implementation).

Uses in-memory data for demo purposes - no MongoDB or ChromaDB needed.
All tools are LangChain @tool functions consumed by the agent via TOOLS.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory ride catalog
# ---------------------------------------------------------------------------

RIDE_CATALOG: Dict[str, Dict[str, Any]] = {
    "uber_go": {
        "id": "uber_go",
        "name": "UberGo",
        "description": "Affordable everyday rides in compact sedans and hatchbacks",
        "base_fare": 50,
        "per_km": 12,
        "per_min": 1.5,
        "min_fare": 80,
        "capacity": 4,
        "eta_minutes": 5,
        "vehicle_types": ["Sedan", "Hatchback"],
        "available_cities": ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata"],
        "features": ["AC", "4 seats", "Affordable"],
    },
    "uber_premier": {
        "id": "uber_premier",
        "name": "Uber Premier",
        "description": "Premium rides with top-rated drivers and comfortable sedans",
        "base_fare": 100,
        "per_km": 18,
        "per_min": 2.0,
        "min_fare": 150,
        "capacity": 4,
        "eta_minutes": 8,
        "vehicle_types": ["Sedan"],
        "available_cities": ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai"],
        "features": ["AC", "Top-rated drivers", "Premium sedan", "4 seats"],
    },
    "uber_xl": {
        "id": "uber_xl",
        "name": "UberXL",
        "description": "Spacious SUVs and MPVs for groups and extra luggage",
        "base_fare": 150,
        "per_km": 22,
        "per_min": 2.5,
        "min_fare": 200,
        "capacity": 6,
        "eta_minutes": 10,
        "vehicle_types": ["SUV", "MPV"],
        "available_cities": ["Delhi", "Mumbai", "Bangalore"],
        "features": ["AC", "6 seats", "Extra luggage space"],
    },
    "uber_auto": {
        "id": "uber_auto",
        "name": "Uber Auto",
        "description": "Quick and budget-friendly auto-rickshaw rides",
        "base_fare": 25,
        "per_km": 8,
        "per_min": 1.0,
        "min_fare": 30,
        "capacity": 3,
        "eta_minutes": 3,
        "vehicle_types": ["Auto-rickshaw"],
        "available_cities": ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata", "Jaipur"],
        "features": ["No AC", "3 seats", "Budget-friendly"],
    },
    "uber_moto": {
        "id": "uber_moto",
        "name": "Uber Moto",
        "description": "Fastest and cheapest way to beat traffic on a bike",
        "base_fare": 15,
        "per_km": 5,
        "per_min": 0.5,
        "min_fare": 25,
        "capacity": 1,
        "eta_minutes": 2,
        "vehicle_types": ["Motorcycle"],
        "available_cities": ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata", "Jaipur"],
        "features": ["No AC", "1 passenger", "Fastest in traffic"],
    },
}

# Simulated distances for common routes (km)
ROUTE_DISTANCES: Dict[str, float] = {
    "delhi_airport": 15.0,
    "mumbai_airport": 12.0,
    "default": 10.0,
}

# In-memory bookings
_bookings: Dict[str, Dict[str, Any]] = {}
_booking_counter = 0


def _estimate_distance(pickup: str, destination: str) -> float:
    """Estimate distance between two points (mock)."""
    key = f"{pickup.lower().split()[0]}_{destination.lower().split()[0]}"
    return ROUTE_DISTANCES.get(key, ROUTE_DISTANCES["default"])


def _calculate_fare(ride: Dict[str, Any], distance_km: float) -> Dict[str, Any]:
    """Calculate fare for a ride type and distance."""
    base = ride["base_fare"]
    km_charge = ride["per_km"] * distance_km
    time_charge = ride["per_min"] * (distance_km * 3)  # ~3 min per km avg
    total = max(base + km_charge + time_charge, ride["min_fare"])
    return {
        "base_fare": base,
        "distance_charge": round(km_charge, 2),
        "time_charge": round(time_charge, 2),
        "total": round(total, 2),
        "currency": "INR",
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def search_rides(pickup: str, destination: str) -> str:
    """
    Search for available rides between two locations.

    Shows all available ride types with fare estimates and ETAs.

    Args:
        pickup: Pickup location (address or landmark).
        destination: Drop-off location (address or landmark).

    Returns:
        List of available rides with pricing and ETA.
    """
    logger.info("=== SEARCH_RIDES CALLED === pickup=%r destination=%r", pickup, destination)

    distance = _estimate_distance(pickup, destination)

    lines = [f"Available rides from {pickup} to {destination} (~{distance} km):\n"]

    for ride_id, ride in RIDE_CATALOG.items():
        fare = _calculate_fare(ride, distance)
        lines.append(
            f"{ride['name']}\n"
            f"   Type: {ride_id}\n"
            f"   Fare: Rs.{fare['total']}\n"
            f"   ETA: {ride['eta_minutes']} min\n"
            f"   Capacity: {ride['capacity']} passenger(s)\n"
            f"   {ride['description']}\n"
        )

    return "\n".join(lines)


@tool
def list_ride_types() -> str:
    """
    List all available vehicle types with base pricing.

    Returns:
        Overview of all ride types, their features, and starting fares.
    """
    logger.info("=== LIST_RIDE_TYPES CALLED ===")

    lines = ["Available Ride Types:\n"]
    for ride_id, ride in RIDE_CATALOG.items():
        features = ", ".join(ride["features"])
        cities = ", ".join(ride["available_cities"][:4])
        more = f" +{len(ride['available_cities']) - 4} more" if len(ride["available_cities"]) > 4 else ""
        lines.append(
            f"{ride['name']}\n"
            f"   Type: {ride_id}\n"
            f"   Starting at: Rs.{ride['min_fare']}\n"
            f"   Per km: Rs.{ride['per_km']}\n"
            f"   Capacity: {ride['capacity']} passengers\n"
            f"   Features: {features}\n"
            f"   Available in: {cities}{more}\n"
        )

    return "\n".join(lines)


@tool
def get_ride_details(ride_type: str) -> str:
    """
    Get full details for a specific ride type.

    Args:
        ride_type: The ride type ID (uber_go, uber_premier, uber_xl, uber_auto, uber_moto).

    Returns:
        Complete pricing, features, and availability info.
    """
    logger.info("=== GET_RIDE_DETAILS CALLED === ride_type=%r", ride_type)

    ride = RIDE_CATALOG.get(ride_type.lower())
    if not ride:
        available = ", ".join(RIDE_CATALOG.keys())
        return f"Ride type '{ride_type}' not found. Available types: {available}"

    cities = ", ".join(ride["available_cities"])
    vehicles = ", ".join(ride["vehicle_types"])
    features = ", ".join(ride["features"])

    return (
        f"Ride Details: {ride['name']}\n\n"
        f"Type: {ride['id']}\n"
        f"Description: {ride['description']}\n\n"
        f"PRICING:\n"
        f"  Base Fare: Rs.{ride['base_fare']}\n"
        f"  Per km: Rs.{ride['per_km']}\n"
        f"  Per minute: Rs.{ride['per_min']}\n"
        f"  Minimum Fare: Rs.{ride['min_fare']}\n\n"
        f"VEHICLE INFO:\n"
        f"  Types: {vehicles}\n"
        f"  Max Passengers: {ride['capacity']}\n"
        f"  ETA: ~{ride['eta_minutes']} minutes\n\n"
        f"FEATURES: {features}\n\n"
        f"AVAILABILITY:\n"
        f"  Cities: {cities}"
    )


@tool
def book_ride(
    pickup: str,
    destination: str,
    ride_type: str,
    passenger_name: str,
    phone: str,
) -> str:
    """
    Book a ride.

    Call this only after showing ride options and confirming with the user.

    Args:
        pickup: Pickup location (address or landmark).
        destination: Drop-off location (address or landmark).
        ride_type: Ride type (uber_go, uber_premier, uber_xl, uber_auto, uber_moto).
        passenger_name: Passenger full name.
        phone: 10-digit phone number.

    Returns:
        Booking confirmation with booking ID, or an error message.
    """
    global _booking_counter
    logger.info(
        "=== BOOK_RIDE CALLED === pickup=%r dest=%r type=%r name=%r",
        pickup, destination, ride_type, passenger_name,
    )

    ride = RIDE_CATALOG.get(ride_type.lower())
    if not ride:
        available = ", ".join(RIDE_CATALOG.keys())
        return f"Error: Ride type '{ride_type}' not found. Available: {available}"

    if not phone or len(phone.replace(" ", "").replace("-", "")) < 10:
        return "Error: Please provide a valid 10-digit phone number."

    distance = _estimate_distance(pickup, destination)
    fare = _calculate_fare(ride, distance)

    _booking_counter += 1
    booking_id = f"UB{datetime.now().strftime('%Y%m%d%H%M%S')}{_booking_counter:03d}"

    booking = {
        "booking_id": booking_id,
        "ride_type": ride["name"],
        "pickup": pickup,
        "destination": destination,
        "distance_km": distance,
        "fare": fare["total"],
        "currency": "INR",
        "passenger_name": passenger_name,
        "phone": phone,
        "eta_minutes": ride["eta_minutes"],
        "status": "confirmed",
        "booked_at": datetime.now().isoformat(),
    }
    _bookings[booking_id] = booking

    return (
        "RIDE CONFIRMED!\n\n"
        "Booking Details:\n"
        f"   Booking ID: {booking_id}\n"
        f"   Ride: {ride['name']}\n"
        f"   Pickup: {pickup}\n"
        f"   Destination: {destination}\n"
        f"   Distance: ~{distance} km\n"
        f"   Fare: Rs.{fare['total']}\n"
        f"   ETA: {ride['eta_minutes']} minutes\n"
        f"   Contact: {phone}\n\n"
        "Your driver is on the way. Thank you for choosing Uber!"
    )


@tool
def get_ride_status(booking_id: str) -> str:
    """
    Check the status of a ride booking.

    Args:
        booking_id: The booking ID (e.g. UB20260402...).

    Returns:
        Current status and details of the ride.
    """
    logger.info("=== GET_RIDE_STATUS CALLED === booking_id=%r", booking_id)

    booking = _bookings.get(booking_id)
    if not booking:
        return f"No booking found with ID {booking_id}. Please check the booking ID."

    return (
        f"Ride Status for {booking['booking_id']}\n\n"
        f"Status: {booking['status'].upper()}\n"
        f"Ride: {booking['ride_type']}\n"
        f"From: {booking['pickup']}\n"
        f"To: {booking['destination']}\n"
        f"Fare: Rs.{booking['fare']}\n"
        f"Booked at: {booking['booked_at']}\n"
    )


TOOLS = [
    search_rides,
    list_ride_types,
    get_ride_details,
    book_ride,
    get_ride_status,
]
