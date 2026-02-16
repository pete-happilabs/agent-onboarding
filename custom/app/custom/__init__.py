# ============================================================================
# FILE: app/custom/__init__.py
# ============================================================================
"""
Custom REST API Integration Module.

Allows developers to create AI agents by hooking their REST APIs as tools.
Same talk() interface, dostEvent input AND output as MCP/DPA.

Usage:
    from app.custom import CustomClient, load_tools_from_config
    from app.custom import AuthHandler, RESTExecutor
"""

from .auth import AuthHandler, AuthConfig
from .registry import RESTTool, RESTParameter, load_tools_from_config, ServiceConfig
from .executor import RESTExecutor
from .client import CustomClient

__all__ = [
    "AuthHandler",
    "AuthConfig",
    "RESTTool",
    "RESTParameter",
    "load_tools_from_config",
    "ServiceConfig",
    "RESTExecutor",
    "CustomClient",
]
