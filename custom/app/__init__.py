# ============================================================================
# FILE: app/__init__.py
# ============================================================================
"""
Custom REST API Agent

Main exports for easy imports:
    from app import talk, get_settings
    from app.engine import talk
    from app.config import get_settings
"""

__version__ = "1.0.0"


# Lazy imports to avoid loading heavy dependencies on module import
def __getattr__(name):
    """Lazy import for heavy dependencies."""
    if name == "talk":
        from .engine.talk import talk
        return talk
    elif name == "get_settings":
        from .config import get_settings
        return get_settings
    elif name == "Settings":
        from .config import Settings
        return Settings
    elif name == "CustomClient":
        from .custom.client import CustomClient
        return CustomClient
    elif name == "ReActAgent":
        from .llm.agent import ReActAgent
        return ReActAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main functions
    "talk",
    # Config
    "get_settings",
    "Settings",
    # Client
    "CustomClient",
    # Agent
    "ReActAgent",
]
