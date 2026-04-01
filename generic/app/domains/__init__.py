"""
Domain registry for multi-domain support.

Each domain provides its own configuration class that subclasses
BaseDomainConfig. This module exposes a simple registry and a helper
to retrieve domain configurations by name.
"""
from app.domains.urban_company.config import UrbanCompanyConfig
from app.domains.swiggy.config import SwiggyConfig
from app.domains.myntra.config import MyntraConfig
from app.domains.uber.config import UberConfig


DOMAIN_REGISTRY = {
    "urban_company": UrbanCompanyConfig,
    "swiggy": SwiggyConfig,
    "myntra": MyntraConfig,
    "uber": UberConfig,
}


def get_domain_config(domain_name: str):
    """
    Get domain configuration by name.
    
    Args:
        domain_name: One of 'urban_company', 'swiggy', 'myntra'
    
    Returns:
        Instantiated domain config
    
    Raises:
        ValueError: If domain not found
    """
    if domain_name not in DOMAIN_REGISTRY:
        raise ValueError(
            f"Unknown domain: '{domain_name}'. "
            f"Available: {list(DOMAIN_REGISTRY.keys())}"
        )
    return DOMAIN_REGISTRY[domain_name]()
