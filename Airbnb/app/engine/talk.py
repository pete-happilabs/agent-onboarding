"""
Airbnb Talk Engine - delegates to MCP template's talk().

Ensures the MCP template is on sys.path and config is loaded
before forwarding the dostEvent to the MCP bridge.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Tuple

# Add MCP template to Python path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_MCP_DIR = os.path.join(_REPO_ROOT, "mcp")
if _MCP_DIR not in sys.path:
    sys.path.insert(0, _MCP_DIR)

# Set config path to Airbnb config
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MCP_CONFIG_PATH", os.path.join(_AGENT_DIR, "config.yaml"))

from app.engine.talk import talk as _mcp_talk  # noqa: E402


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Process a talk request via the MCP bridge."""
    return await _mcp_talk(event)
