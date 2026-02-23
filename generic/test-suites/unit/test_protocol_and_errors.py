"""
Unit tests for protocol error handling - Generic agent
Tests error cases in real protocol.py
"""
import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add generic root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.protocol import (
    create_dost_event,
    create_dost_message,
    create_dost_object,
    create_dost_pricing,
    create_dost_location,
    extract_query_text,
    DOST_SPEC_VERSION,
    VALID_DURATION_TYPES,
)


@pytest.mark.unit
class TestProtocolErrorHandling:
    """Test error handling in protocol functions"""
    
    def test_dost_event_missing_content_raises_error(self):
        """dostEvent must have message OR categories"""
        with pytest.raises(ValueError, match="must contain at least message or categories"):
            create_dost_event(source_entity_id="agent.test")
        
        print(f"\n✓ dostEvent requires message or categories")
    
    def test_dost_event_with_message_only(self):
        """dostEvent can be created with just message"""
        event = create_dost_event(
            source_entity_id="agent.test",
            message=create_dost_message(text="Hello")
        )
        
        assert event["message"]["text"]["data"] == "Hello"
        assert "categories" not in event or event["categories"] is None
        
        print(f"\n✓ dostEvent with message only works")
    
    def test_dost_event_with_categories_only(self):
        """dostEvent can be created with just categories"""
        from app.core.protocol import create_dost_categories
        
        categories = create_dost_categories(
            currency="INR",
            categories=[]
        )
        
        event = create_dost_event(
            source_entity_id="agent.test",
            categories=categories
        )
        
        assert event["categories"]["currency"] == "INR"
        assert "message" not in event or event["message"] is None
        
        print(f"\n✓ dostEvent with categories only works")
    
    def test_dost_pricing_invalid_duration_type_raises_error(self):
        """dostPricing must have valid durationType"""
        with pytest.raises(ValueError, match="durationType must be one of"):
            create_dost_pricing(
                id="price1",
                value=100.0,
                duration_type="invalid_type",
                duration_value=1
            )
        
        print(f"\n✓ dostPricing validates durationType")
    
    def test_dost_pricing_all_valid_duration_types(self):
        """Test all valid duration types work"""
        for duration_type in VALID_DURATION_TYPES:
            pricing = create_dost_pricing(
                id=f"price_{duration_type}",
                value=100.0,
                duration_type=duration_type,
                duration_value=1
            )
            
            assert pricing["durationType"] == duration_type
            assert pricing["value"] == 100.0
            assert pricing["durationValue"] == 1
        
        print(f"\n✓ All valid duration types work: {VALID_DURATION_TYPES}")
    
    def test_dost_message_location_must_be_single_object(self):
        """dostMessage.location must be single object, not array"""
        # Should work with single object
        msg = create_dost_message(
            text="test",
            location={"address": "123 Main St"}
        )
        
        assert isinstance(msg["location"], dict)
        assert msg["location"]["address"] == "123 Main St"
        
        # Should fail with array
        with pytest.raises(TypeError, match="must be a single dostLocation"):
            create_dost_message(
                text="test",
                location=[{"address": "123 Main St"}]  # Wrong: array
            )
        
        print(f"\n✓ dostMessage.location validation works")
    
    def test_dost_object_location_must_be_array(self):
        """dostObject.location must be array (v00.01.01 spec)"""
        # Should work with array
        obj = create_dost_object(
            id="obj1",
            type="restaurant",
            title="Pizza Hut",
            location=[{"address": "123 Main St"}]
        )
        
        assert isinstance(obj["location"], list)
        assert len(obj["location"]) == 1
        assert obj["location"][0]["address"] == "123 Main St"
        
        # Should fail with non-array
        with pytest.raises(TypeError, match="must be an array"):
            create_dost_object(
                id="obj1",
                type="restaurant",
                title="Pizza Hut",
                location={"address": "123 Main St"}  # Wrong: not array
            )
        
        print(f"\n✓ dostObject.location validation works")


@pytest.mark.unit
class TestExtractQueryText:
    """Test extract_query_text function"""
    
    def test_extract_query_text_valid(self):
        """Test extracting query text from valid dostEvent"""
        event = {
            "message": {
                "text": {
                    "data": "Find restaurants"
                }
            }
        }
        
        text = extract_query_text(event)
        assert text == "Find restaurants"
        
        print(f"\n✓ extract_query_text works for valid input")
    
    def test_extract_query_text_missing_message(self):
        """Test extracting when message is missing"""
        assert extract_query_text({}) == ""
        assert extract_query_text({"message": None}) == ""
        
        print(f"\n✓ extract_query_text handles missing message")
    
    def test_extract_query_text_missing_text_field(self):
        """Test extracting when text field is missing"""
        assert extract_query_text({"message": {}}) == ""
        assert extract_query_text({"message": {"text": None}}) == ""
        assert extract_query_text({"message": {"text": {}}}) == ""
        
        print(f"\n✓ extract_query_text handles missing text field")
    
    def test_extract_query_text_malformed_input(self):
        """Test that extract_query_text doesn't crash on bad input"""
        # Should not raise exceptions
        assert extract_query_text(None) == ""
        assert extract_query_text("not a dict") == ""
        assert extract_query_text([]) == ""
        
        print(f"\n✓ extract_query_text handles malformed input gracefully")


@pytest.mark.unit
class TestDostEventVersioning:
    """Test dostEvent version handling"""
    
    def test_default_version_is_correct(self):
        """Test that default version matches spec"""
        event = create_dost_event(
            source_entity_id="agent.test",
            message=create_dost_message(text="Hello")
        )
        
        assert event["version"] == DOST_SPEC_VERSION
        assert event["version"] == "00.01.01"
        
        print(f"\n✓ Default version is {DOST_SPEC_VERSION}")
    
    def test_custom_version_can_be_set(self):
        """Test that custom version can be specified"""
        event = create_dost_event(
            source_entity_id="agent.test",
            version="00.02.00",
            message=create_dost_message(text="Hello")
        )
        
        assert event["version"] == "00.02.00"
        
        print(f"\n✓ Custom version can be set")
    
    def test_version_format_is_string(self):
        """Test that version is always a string"""
        event = create_dost_event(
            source_entity_id="agent.test",
            message=create_dost_message(text="Hello")
        )
        
        assert isinstance(event["version"], str)
        
        print(f"\n✓ Version is string type")


@pytest.mark.unit
class TestDostEventStructure:
    """Test dostEvent structure requirements"""
    
    def test_dost_event_has_required_fields(self):
        """Test that created dostEvent has all required fields"""
        event = create_dost_event(
            source_entity_id="agent.test",
            message=create_dost_message(text="Hello")
        )
        
        required_fields = [
            "version",
            "timestamp",
            "eventId",
            "sessionId",
            "sourceEntityId",
            "isAiGenerated"
        ]
        
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"
        
        print(f"\n✓ dostEvent has all required fields")
    
    def test_dost_event_auto_generates_ids(self):
        """Test that eventId and sessionId are auto-generated"""
        event = create_dost_event(
            source_entity_id="agent.test",
            message=create_dost_message(text="Hello")
        )
        
        assert event["eventId"] is not None
        assert event["sessionId"] is not None
        assert isinstance(event["eventId"], str)
        assert isinstance(event["sessionId"], str)
        assert len(event["eventId"]) > 0
        assert len(event["sessionId"]) > 0
        
        print(f"\n✓ IDs are auto-generated")
    
    def test_dost_event_preserves_custom_ids(self):
        """Test that custom IDs are preserved"""
        custom_event_id = "custom-event-123"
        custom_session_id = "custom-session-456"
        
        event = create_dost_event(
            source_entity_id="agent.test",
            event_id=custom_event_id,
            session_id=custom_session_id,
            message=create_dost_message(text="Hello")
        )
        
        assert event["eventId"] == custom_event_id
        assert event["sessionId"] == custom_session_id
        
        print(f"\n✓ Custom IDs are preserved")
