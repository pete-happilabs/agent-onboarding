"""
Unit tests for Uber ride booking tools.

Tests all 5 tools in generic/app/domains/uber/tools.py:
  - search_rides
  - list_ride_types
  - get_ride_details
  - book_ride
  - get_ride_status
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "generic"))

from app.domains.uber.tools import (
    search_rides,
    list_ride_types,
    get_ride_details,
    book_ride,
    get_ride_status,
    RIDE_CATALOG,
    TOOLS,
    _calculate_fare,
    _estimate_distance,
    _bookings,
)


@pytest.mark.unit
class TestRideCatalog:
    """Verify the static ride catalog data."""

    def test_catalog_has_five_ride_types(self):
        assert len(RIDE_CATALOG) == 5
        expected = {"uber_go", "uber_premier", "uber_xl", "uber_auto", "uber_moto"}
        assert set(RIDE_CATALOG.keys()) == expected

    def test_each_ride_has_required_fields(self):
        required = [
            "id", "name", "description", "base_fare", "per_km",
            "per_min", "min_fare", "capacity", "eta_minutes",
            "vehicle_types", "available_cities", "features",
        ]
        for ride_id, ride in RIDE_CATALOG.items():
            for field in required:
                assert field in ride, f"{ride_id} missing {field}"

    def test_fares_are_positive(self):
        for ride_id, ride in RIDE_CATALOG.items():
            assert ride["base_fare"] > 0
            assert ride["per_km"] > 0
            assert ride["per_min"] > 0
            assert ride["min_fare"] > 0

    def test_capacity_is_valid(self):
        for ride_id, ride in RIDE_CATALOG.items():
            assert 1 <= ride["capacity"] <= 10

    def test_eta_is_positive(self):
        for ride_id, ride in RIDE_CATALOG.items():
            assert ride["eta_minutes"] > 0

    def test_uber_go_is_cheapest_car(self):
        go = RIDE_CATALOG["uber_go"]
        premier = RIDE_CATALOG["uber_premier"]
        xl = RIDE_CATALOG["uber_xl"]
        assert go["base_fare"] < premier["base_fare"]
        assert go["base_fare"] < xl["base_fare"]

    def test_moto_has_capacity_one(self):
        assert RIDE_CATALOG["uber_moto"]["capacity"] == 1

    def test_xl_has_highest_capacity(self):
        xl_cap = RIDE_CATALOG["uber_xl"]["capacity"]
        for ride_id, ride in RIDE_CATALOG.items():
            if ride_id != "uber_xl":
                assert ride["capacity"] <= xl_cap


@pytest.mark.unit
class TestCalculateFare:
    """Test fare calculation logic."""

    def test_fare_includes_base_distance_time(self):
        ride = RIDE_CATALOG["uber_go"]
        fare = _calculate_fare(ride, 10.0)
        assert "base_fare" in fare
        assert "distance_charge" in fare
        assert "time_charge" in fare
        assert "total" in fare
        assert "currency" in fare

    def test_fare_total_is_sum(self):
        ride = RIDE_CATALOG["uber_go"]
        fare = _calculate_fare(ride, 10.0)
        expected_min = ride["base_fare"] + ride["per_km"] * 10.0 + ride["per_min"] * 30
        assert fare["total"] >= ride["min_fare"]
        assert fare["total"] == pytest.approx(max(expected_min, ride["min_fare"]), rel=0.01)

    def test_minimum_fare_enforced(self):
        ride = RIDE_CATALOG["uber_moto"]
        fare = _calculate_fare(ride, 0.1)  # Very short distance
        assert fare["total"] >= ride["min_fare"]

    def test_currency_is_inr(self):
        fare = _calculate_fare(RIDE_CATALOG["uber_go"], 5.0)
        assert fare["currency"] == "INR"

    def test_longer_distance_costs_more(self):
        ride = RIDE_CATALOG["uber_go"]
        fare_short = _calculate_fare(ride, 5.0)
        fare_long = _calculate_fare(ride, 20.0)
        assert fare_long["total"] > fare_short["total"]


@pytest.mark.unit
class TestEstimateDistance:
    """Test distance estimation."""

    def test_default_distance(self):
        assert _estimate_distance("random place", "another place") == 10.0

    def test_returns_positive_float(self):
        d = _estimate_distance("A", "B")
        assert isinstance(d, float)
        assert d > 0


@pytest.mark.unit
class TestSearchRides:
    """Test search_rides tool."""

    def test_returns_string(self):
        result = search_rides.invoke({"pickup": "MG Road", "destination": "Airport"})
        assert isinstance(result, str)

    def test_contains_all_ride_types(self):
        result = search_rides.invoke({"pickup": "Koramangala", "destination": "Whitefield"})
        for ride in RIDE_CATALOG.values():
            assert ride["name"] in result

    def test_contains_fare_info(self):
        result = search_rides.invoke({"pickup": "A", "destination": "B"})
        assert "Rs." in result

    def test_contains_locations(self):
        result = search_rides.invoke({"pickup": "Indiranagar", "destination": "HSR Layout"})
        assert "Indiranagar" in result
        assert "HSR Layout" in result


@pytest.mark.unit
class TestListRideTypes:
    """Test list_ride_types tool."""

    def test_returns_string(self):
        result = list_ride_types.invoke({})
        assert isinstance(result, str)

    def test_contains_all_ride_names(self):
        result = list_ride_types.invoke({})
        for ride in RIDE_CATALOG.values():
            assert ride["name"] in result

    def test_contains_pricing(self):
        result = list_ride_types.invoke({})
        assert "Rs." in result
        assert "Per km" in result


@pytest.mark.unit
class TestGetRideDetails:
    """Test get_ride_details tool."""

    def test_valid_ride_type(self):
        result = get_ride_details.invoke({"ride_type": "uber_go"})
        assert "UberGo" in result
        assert "Base Fare" in result
        assert "Per km" in result

    def test_invalid_ride_type(self):
        result = get_ride_details.invoke({"ride_type": "uber_helicopter"})
        assert "not found" in result

    def test_case_insensitive(self):
        result = get_ride_details.invoke({"ride_type": "UBER_GO"})
        assert "UberGo" in result

    def test_contains_city_availability(self):
        result = get_ride_details.invoke({"ride_type": "uber_premier"})
        assert "Delhi" in result or "Mumbai" in result


@pytest.mark.unit
class TestBookRide:
    """Test book_ride tool."""

    def test_successful_booking(self):
        result = book_ride.invoke({
            "pickup": "MG Road",
            "destination": "Airport",
            "ride_type": "uber_go",
            "passenger_name": "Test User",
            "phone": "9876543210",
        })
        assert "CONFIRMED" in result
        assert "UB" in result  # Booking ID prefix

    def test_invalid_ride_type_booking(self):
        result = book_ride.invoke({
            "pickup": "A",
            "destination": "B",
            "ride_type": "uber_flying",
            "passenger_name": "Test",
            "phone": "9876543210",
        })
        assert "not found" in result.lower() or "error" in result.lower()

    def test_invalid_phone(self):
        result = book_ride.invoke({
            "pickup": "A",
            "destination": "B",
            "ride_type": "uber_go",
            "passenger_name": "Test",
            "phone": "123",
        })
        assert "phone" in result.lower() or "error" in result.lower()

    def test_booking_contains_fare(self):
        result = book_ride.invoke({
            "pickup": "Koramangala",
            "destination": "Electronic City",
            "ride_type": "uber_premier",
            "passenger_name": "Jane Doe",
            "phone": "9998887770",
        })
        assert "Rs." in result

    def test_booking_id_stored(self):
        initial_count = len(_bookings)
        book_ride.invoke({
            "pickup": "A",
            "destination": "B",
            "ride_type": "uber_auto",
            "passenger_name": "Stored Test",
            "phone": "1234567890",
        })
        assert len(_bookings) > initial_count


@pytest.mark.unit
class TestGetRideStatus:
    """Test get_ride_status tool."""

    def test_valid_booking_id(self):
        # First create a booking
        result = book_ride.invoke({
            "pickup": "A",
            "destination": "B",
            "ride_type": "uber_go",
            "passenger_name": "Status Test",
            "phone": "5555555555",
        })
        # Extract booking ID from result
        for line in result.split("\n"):
            if "Booking ID" in line:
                booking_id = line.split(":")[-1].strip()
                break
        else:
            pytest.fail("Could not find booking ID in result")

        status = get_ride_status.invoke({"booking_id": booking_id})
        assert "CONFIRMED" in status
        assert booking_id in status

    def test_invalid_booking_id(self):
        result = get_ride_status.invoke({"booking_id": "INVALID123"})
        assert "not found" in result.lower() or "no booking" in result.lower()


@pytest.mark.unit
class TestToolsExport:
    """Test that TOOLS list is correctly defined."""

    def test_tools_list_has_five(self):
        assert len(TOOLS) == 5

    def test_all_tools_are_callable(self):
        for tool in TOOLS:
            assert callable(tool.invoke)

    def test_tool_names(self):
        names = {t.name for t in TOOLS}
        expected = {"search_rides", "list_ride_types", "get_ride_details", "book_ride", "get_ride_status"}
        assert names == expected
