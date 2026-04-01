"""
Uber Talk Engine - delegates to Generic template's talk().

Sets up the Uber domain agent and forwards dostEvents
to the generic talk engine.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Tuple

# Add Generic template to Python path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_GENERIC_DIR = os.path.join(_REPO_ROOT, "generic")
if _GENERIC_DIR not in sys.path:
    sys.path.insert(0, _GENERIC_DIR)

# Set Uber-specific environment
os.environ.setdefault("DOMAIN_CONFIG", "uber")
os.environ.setdefault("AGENT_ENTITY_ID", "com.uber.rides")
os.environ.setdefault("AGENT_NAME", "UberBot")
os.environ.setdefault("CURRENCY", "INR")

from app.engine.talk import talk as _generic_talk  # noqa: E402
from app.engine.talk import set_agent, get_agent  # noqa: E402
from app.core.generic_agent import GenericReActAgent  # noqa: E402
from app.domains import get_domain_config  # noqa: E402


def _ensure_agent():
    """Initialize the Uber agent if not already set."""
    if get_agent() is None:
        config = get_domain_config("uber")
        agent = GenericReActAgent(config)
        set_agent(agent)


async def talk(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Process a talk request via the Generic agent."""
    _ensure_agent()
    return await _generic_talk(event)
