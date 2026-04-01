"""
Zomato Talk Engine - delegates to Custom template's talk().

Sets up environment for the Zomato agent (config path, entity ID)
and forwards the dostEvent to the Custom REST API engine.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Tuple

# Add Custom template to Python path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_CUSTOM_DIR = os.path.join(_REPO_ROOT, "custom")
if _CUSTOM_DIR not in sys.path:
    sys.path.insert(0, _CUSTOM_DIR)

# Set Zomato-specific config
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CUSTOM_CONFIG_PATH", os.path.join(_AGENT_DIR, "config.yaml"))
os.environ.setdefault("AGENT_ENTITY_ID", "agent.custom.zomato")
os.environ.setdefault("AGENT_NAME", "Zomato Food Assistant")

from app.engine.talk import talk as _custom_talk  # noqa: E402


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Process a talk request via the Custom REST API agent."""
    return await _custom_talk(event)
