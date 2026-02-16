"""
Domain configuration models for multi-domain agents.

This module defines a base configuration object that can be reused for
different verticals (e.g., Urban Company, Uber, etc.), along with a
concrete implementation for the Urban Company domain.
"""
from typing import Dict, Literal, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class BaseDomainConfig(BaseSettings):
    """
    Base configuration for a conversational domain.

    This model is intended to be subclassed per domain (e.g. Urban Company,
    Uber, Swiggy). All fields are designed to be serializable and safe to
    load from environment variables or configuration files.
    """

    domain_name: str = Field(..., description="Short slug for the domain (e.g. 'urban_company').")
    system_prompt: str = Field(..., description="Primary system prompt used to steer the agent.")
    tools_module: str = Field(
        ...,
        description="Dotted Python path to the module that exports the LangChain tools for this domain.",
    )
    database_collection: str = Field(
        ...,
        description="MongoDB collection name (or equivalent) used to store domain-specific data.",
    )
    enable_vector_search: bool = Field(
        default=True,
        description="Whether vector search (e.g. ChromaDB) is used for this domain.",
    )
    entity_id: str = Field(
        ...,
        description="Stable identifier for the domain entity (e.g. reverse-DNS 'com.urban.company').",
    )
    currency: str = Field(
        default="INR",
        description="ISO currency code used for prices in this domain.",
    )
    api_mode: Literal["mock", "real"] = Field(
        default="mock",
        description="API mode for external integrations (e.g., Uber sandbox vs production).",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for real external APIs when api_mode='real'.",
    )

    class Config:
        """Pydantic configuration for environment-based loading."""

        env_prefix = "DOMAIN_"
        case_sensitive = False

    def validate(self) -> bool:
        """
        Ensure all required fields are set and consistent.

        Returns:
            True if validation passes, otherwise raises an AssertionError.

        Raises:
            AssertionError: If required fields like domain_name or entity_id are missing.
        """
        assert self.domain_name, "domain_name required"
        assert self.entity_id, "entity_id required"
        return True


class UrbanCompanyConfig(BaseDomainConfig):
    """
    Default configuration for the Urban Company home-services domain.

    This mirrors the current UrbanBot implementation and can be used as the
    single source of truth for prompts, tools, and persistence settings.
    """

    domain_name: str = "urban_company"
    entity_id: str = "com.urban.company"
    system_prompt: str = """You are UrbanBot, a smart booking assistant for home services.

RESPONSE FORMAT:
- Use PLAIN TEXT only. No markdown (no **, no ###, no -)
- NO bullet points or numbered lists in responses
- Write in flowing conversational sentences
- Keep responses short and friendly, like a WhatsApp message
- When asking for information, ask ONE question at a time

CRITICAL RULES:
1. NEVER generate fake booking confirmations - MUST call save_booking tool
2. NEVER say "booking confirmed" unless save_booking tool returned success
3. ALWAYS verify city availability BEFORE collecting user details
4. If service isn't in user's city: STOP and tell them immediately

DATE HANDLING:
- Today's date is provided in context. Use it for "tomorrow" calculations
- Date format must be DD-MM-YYYY

BOOKING WORKFLOW:
1. User requests service -> search_services or list_all_services
2. User selects -> get_service_details to show full info
3. User confirms -> Ask for details ONE BY ONE:
   a. City FIRST (must match service availability)
   b. If city unavailable: STOP, suggest alternatives
   c. If city OK: name, phone, address, date, time
4. Have all details -> MUST call save_booking tool
5. Tool returns success -> THEN say confirmed

TOOLS:
- search_services(query, city="", category=""): Find services by query, optionally filter by city and category
- list_all_services(city="", category=""): List all services, optionally filter by city and category
- get_service_details(service_id): Full service info
- save_booking(...): Confirm booking
- get_user_bookings(user_id): View booking history

REMEMBER:
- Always use user_id from state for save_booking/get_user_bookings
- Service availability is city-specific
"""
    tools_module: str = "app.domains.urban_company.tools"
    database_collection: str = "services"

