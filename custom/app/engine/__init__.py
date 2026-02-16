# ============================================================================
# FILE: app/engine/__init__.py
# ============================================================================
"""
Engine Module - Main talk function.

Provides the same talk() signature as MCP/DPA:
    talk(dostEvent) -> (response_dostEvent, metrics)
"""

from .talk import talk

__all__ = ["talk"]
