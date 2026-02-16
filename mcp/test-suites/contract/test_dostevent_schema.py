"""
Contract tests for dostEvent schema compliance - UNIFORM across all agents
"""
import pytest
from jsonschema import validate, ValidationError


@pytest.mark.contract
class TestDostEventSchema:
    """Contract tests for dostEvent protocol - uniform across all agents"""
    
    def test_dostevent_input_schema_compliance(self, base_dostevent):
        """Test that input dostEvent complies with schema"""
        schema = {
            "type": "object",
            "required": ["version", "sourceEntityId", "destinationEntityId", "message"],
            "properties": {
                "version": {"type": "string", "pattern": "^\\d{2}\\.\\d{2}\\.\\d{2}$"},
                "sourceEntityId": {"type": "string"},
                "destinationEntityId": {"type": "string"},
                "message": {"type": "object"}
            }
        }
        
        # Should not raise validation error
        validate(instance=base_dostevent, schema=schema)
        print(f"\n✓ Input dostEvent complies with schema")
    
    def test_version_format_validation(self):
        """Test that version follows XX.XX.XX format"""
        import re
        version_pattern = r"^\d{2}\.\d{2}\.\d{2}$"
        
        valid_versions = ["00.01.01", "01.23.45", "99.99.99"]
        
        for version in valid_versions:
            assert re.match(version_pattern, version), f"{version} should be valid"
        
        print(f"\n✓ Version format validation works correctly")
