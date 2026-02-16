# ============================================================================
# FILE: app/llm/tool_converter.py
# ============================================================================
"""
Tool Converter - Convert REST tools to OpenAI function calling format.
"""
from typing import List, Dict, Any

# Type mapping from YAML to JSON Schema
TYPE_MAP = {
    "string": "string",
    "number": "number",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def tools_to_openai_format(tools: List[Any]) -> List[Dict[str, Any]]:
    """
    Convert REST tool definitions to OpenAI function calling format.

    Args:
        tools: List of RESTTool objects

    Returns:
        List of OpenAI tool definitions
    """
    openai_tools = []

    for tool in tools:
        # Build properties and required list from parameters
        properties = {}
        required = []

        for param in tool.parameters:
            param_type = TYPE_MAP.get(param.type, "string")

            prop = {
                "type": param_type,
                "description": param.description or f"The {param.name} parameter"
            }

            # Handle array type with items
            if param_type == "array" and hasattr(param, "items_type"):
                prop["items"] = {"type": TYPE_MAP.get(param.items_type, "string")}

            # Handle enum values
            if hasattr(param, "enum") and param.enum:
                prop["enum"] = param.enum

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        # Build OpenAI tool definition
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

        openai_tools.append(openai_tool)

    return openai_tools
