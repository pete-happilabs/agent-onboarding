"""
Urban Company domain tools.

This module simply re-exports the shared service tools so that
domain configs can point to a stable tools module path:
    tools_module = "app.domains.urban_company.tools"
"""
from app.tools.service_tools import TOOLS

__all__ = ["TOOLS"]

