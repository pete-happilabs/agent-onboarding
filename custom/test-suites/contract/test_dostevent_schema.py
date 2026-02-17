"""
Contract tests for dostEvent schema compliance - UNIFORM across all agents

These tests validate that dostEvent structures comply with the DOST specification.
They are IDENTICAL across MCP, Generic, and Custom agents since the protocol is shared.
"""
import pytest
from typing import Dict, Any


@pytest.mark.contract
class TestDostEventSchema:
    """Contract tests for dostEvent protocol - uniform across all agents"""
    
    def test_dostevent_input_schema_compliance(self, base_dostevent):
        """Test that input dostEvent complies with schema"""
        # Required fields per spec
        assert "version" in base_dostevent, "version is required"
        assert "sourceEntityId" in base_dostevent, "sourceEntityId is required"
        assert "sessionId" in base_dostevent, "sessionId is required"
        assert "isAiGenerated" in base_dostevent, "isAiGenerated is required"
        
        # Must have message OR categories (at least one)
        has_message = "message" in base_dostevent and base_dostevent["message"] is not None
        has_categories = "categories" in base_dostevent and base_dostevent["categories"] is not None
        assert has_message or has_categories, "dostEvent must have message or categories"
        
        # Type checks
        assert isinstance(base_dostevent["version"], str), "version must be string"
        assert isinstance(base_dostevent["sourceEntityId"], str), "sourceEntityId must be string"
        assert isinstance(base_dostevent["sessionId"], str), "sessionId must be string"
        assert isinstance(base_dostevent["isAiGenerated"], bool), "isAiGenerated must be boolean"
        
        # If message exists, validate structure
        if has_message:
            message = base_dostevent["message"]
            assert isinstance(message, dict), "message must be a dict"
            
            # If text exists, validate structure
            if "text" in message:
                text = message["text"]
                assert isinstance(text, dict), "message.text must be a dict"
                assert "data" in text, "message.text must have 'data' field"
                assert isinstance(text["data"], str), "message.text.data must be string"
        
        print(f"\n✓ Input dostEvent complies with schema")
    
    def test_version_format_validation(self, base_dostevent):
        """Test that version follows XX.XX.XX format"""
        version = base_dostevent["version"]
        
        # Split by dots
        parts = version.split(".")
        assert len(parts) == 3, f"Version must have 3 parts, got {len(parts)}"
        
        # Each part should be numeric
        for i, part in enumerate(parts):
            assert part.isdigit(), f"Version part {i} must be numeric, got '{part}'"
            assert len(part) == 2, f"Version part {i} must be 2 digits, got {len(part)}"
        
        # Current approved version is 00.01.01
        assert version == "00.01.01", f"Expected version 00.01.01, got {version}"
        
        print(f"\n✓ Version format is valid: {version}")
