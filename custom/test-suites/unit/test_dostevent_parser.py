"""
Unit tests for dostEvent parsing - Custom agent
"""
import pytest
import sys
from pathlib import Path

# Add custom root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.protocol import (
    create_dost_event,
    create_dost_message,
    extract_query_text,
    create_dost_object,
    DOST_SPEC_VERSION,
)


@pytest.mark.unit
class TestDostEventParser:
    """Basic unit tests around the dostEvent shape/fields"""
    
    def test_parse_valid_dostevent(self, base_dostevent):
        """Base fixture should look like a valid dostEvent"""
        assert base_dostevent["version"] == "00.01.01"
        assert base_dostevent["sourceEntityId"] == "hum.user.test123"
        assert base_dostevent["destinationEntityId"] == "agent.custom.test"
        assert base_dostevent["message"]["text"]["data"] == "test query"
    
    def test_required_fields_present(self, base_dostevent):
        """Check required keys exist"""
        required = ["version", "sourceEntityId", "destinationEntityId", "message"]
        for key in required:
            assert key in base_dostevent
    
    def test_session_id_present(self, base_dostevent):
        """Session id should be present for multi-turn support"""
        assert "sessionId" in base_dostevent
        assert isinstance(base_dostevent["sessionId"], str)


@pytest.mark.unit
class TestRealProtocolFunctions:
    """Test the actual protocol.py functions"""
    
    def test_create_dost_event_minimal(self):
        """Test creating minimal dostEvent with real function"""
        event = create_dost_event(
            source_entity_id="agent.custom.test",
            message=create_dost_message(text="Hello")
        )
        
        assert event["version"] == DOST_SPEC_VERSION
        assert event["sourceEntityId"] == "agent.custom.test"
        assert event["isAiGenerated"] is False
        assert event["message"]["text"]["data"] == "Hello"
        assert "eventId" in event
        assert "timestamp" in event
        
        print(f"\n✓ Created minimal dostEvent correctly")
    
    def test_create_dost_event_requires_message_or_categories(self):
        """Test that dostEvent requires at least message or categories"""
        with pytest.raises(ValueError, match="must contain at least message or categories"):
            create_dost_event(source_entity_id="agent.custom.test")
        
        print(f"\n✓ dostEvent validation works")
    
    def test_extract_query_text_valid(self):
        """Test extracting query text from dostEvent"""
        event = {
            "message": {
                "text": {
                    "data": "Find meals"
                }
            }
        }
        
        text = extract_query_text(event)
        assert text == "Find meals"
        
        print(f"\n✓ extract_query_text works correctly")
    
    def test_extract_query_text_missing_fields(self):
        """Test extracting query text with missing fields returns empty"""
        assert extract_query_text({}) == ""
        assert extract_query_text({"message": {}}) == ""
        assert extract_query_text({"message": {"text": {}}}) == ""
        
        print(f"\n✓ extract_query_text handles missing fields")
    
    def test_create_dost_object_location_must_be_array(self):
        """Test that dostObject.location must be array (v00.01.01 spec)"""
        # Should work with array
        obj = create_dost_object(
            id="meal1",
            type="meal",
            title="Chicken Curry",
            location=[{"address": "India"}]
        )
        assert isinstance(obj["location"], list)
        
        # Should fail with non-array
        with pytest.raises(TypeError, match="must be an array"):
            create_dost_object(
                id="meal1",
                type="meal",
                title="Chicken Curry",
                location={"address": "India"}  # Wrong: not array
            )
        
        print(f"\n✓ dostObject.location validation works")
    
    def test_create_dost_message_text_only(self):
        """Test creating message with text only"""
        msg = create_dost_message(text="Hello world")
        
        assert msg["text"]["data"] == "Hello world"
        assert len(msg) == 1  # Only text field
        
        print(f"\n✓ Simple text message created correctly")
    
    def test_create_dost_event_full(self):
        """Test creating complete dostEvent with all fields"""
        event = create_dost_event(
            source_entity_id="agent.custom.mealdb",
            destination_entity_id="hum.user.123",
            session_id="session-456",
            event_hint="response",
            is_ai_generated=True,
            message=create_dost_message(text="Here are your meals")
        )
        
        assert event["version"] == DOST_SPEC_VERSION
        assert event["sourceEntityId"] == "agent.custom.mealdb"
        assert event["destinationEntityId"] == "hum.user.123"
        assert event["sessionId"] == "session-456"
        assert event["eventHint"] == "response"
        assert event["isAiGenerated"] is True
        assert event["message"]["text"]["data"] == "Here are your meals"
        
        print(f"\n✓ Complete dostEvent created correctly")
