# ============================================================================
# FILE: app/custom/registry.py
# ============================================================================
"""
Tool Registry - Load REST tool definitions from YAML config.

Parses YAML files to create RESTTool objects for the agent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RESTParameter:
    """Parameter definition for a REST tool."""

    name: str
    type: str  # string, number, integer, boolean, array, object
    required: bool = False
    description: Optional[str] = None
    location: str = "body"  # body, path, query, header
    default: Optional[Any] = None
    enum: Optional[List[str]] = None
    items_type: Optional[str] = None  # For array types


@dataclass
class RESTTool:
    """REST API tool definition."""

    name: str
    description: str
    endpoint: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    parameters: List[RESTParameter] = field(default_factory=list)
    response_mapping: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class ServiceConfig:
    """Service configuration from YAML."""

    name: str
    base_url: str
    auth: Dict[str, Any] = field(default_factory=dict)
    tools: List[RESTTool] = field(default_factory=list)
    agent: Dict[str, Any] = field(default_factory=dict)


def load_tools_from_config(config_path: str) -> ServiceConfig:
    """
    Load service and tools configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        ServiceConfig with all tools loaded

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is invalid
    """
    path = Path(config_path).resolve()
    # Ensure config is within the repo directory (prevent path traversal)
    project_root = Path(__file__).resolve().parent.parent.parent
    repo_root = project_root.parent
    if not (str(path).startswith(str(project_root)) or str(path).startswith(str(repo_root))):
        raise ValueError(f"Config path must be within the project directory")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not path.suffix in (".yaml", ".yml"):
        raise ValueError("Config file must be a YAML file (.yaml or .yml)")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a YAML mapping")

    # Parse service section
    service_config = config.get("service", {})
    if not service_config.get("name") or not service_config.get("base_url"):
        raise ValueError("Service config must have 'name' and 'base_url'")

    # Parse tools
    tools = []
    for tool_def in config.get("tools", []):
        tool = _parse_tool(tool_def)
        tools.append(tool)
        logger.debug(f"Loaded tool: {tool.name}")

    logger.info(f"Loaded {len(tools)} tools from {config_path}")

    return ServiceConfig(
        name=service_config["name"],
        base_url=service_config["base_url"].rstrip("/"),
        auth=config.get("auth", {}),
        tools=tools,
        agent=config.get("agent", {})
    )


def _parse_tool(tool_def: Dict[str, Any]) -> RESTTool:
    """Parse a single tool definition from YAML."""
    if not tool_def.get("name"):
        raise ValueError("Tool must have a 'name'")

    # Parse parameters
    parameters = []
    for param_def in tool_def.get("parameters", []):
        param = RESTParameter(
            name=param_def["name"],
            type=param_def.get("type", "string"),
            required=param_def.get("required", False),
            description=param_def.get("description"),
            location=param_def.get("in", "body"),
            default=param_def.get("default"),
            enum=param_def.get("enum"),
            items_type=param_def.get("items_type")
        )
        parameters.append(param)

    return RESTTool(
        name=tool_def["name"],
        description=tool_def.get("description", f"Call {tool_def['name']} API"),
        endpoint=tool_def.get("endpoint", f"/{tool_def['name']}"),
        method=tool_def.get("method", "POST").upper(),
        parameters=parameters,
        response_mapping=tool_def.get("response_mapping"),
        headers=tool_def.get("headers")
    )


def list_tools(config: ServiceConfig) -> List[str]:
    """Return list of tool names from config."""
    return [tool.name for tool in config.tools]


def get_tool(config: ServiceConfig, name: str) -> Optional[RESTTool]:
    """Get a specific tool by name."""
    for tool in config.tools:
        if tool.name == name:
            return tool
    return None
