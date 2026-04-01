# ============================================================================
# FILE: app/config.py
# ============================================================================
"""
Central configuration management for Custom REST API Agent.

Provides lazy-loaded settings for LLM, Agent, and Custom REST integration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from app directory (where config.py lives)
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for language model access."""

    model: str
    temperature: float
    api_key: str


@dataclass(frozen=True)
class AgentConfig:
    """Metadata that identifies the running agent."""

    name: str
    entity_id: str
    version: str = "1.0.0"


@dataclass(frozen=True)
class CustomConfig:
    """Configuration for Custom REST API integration."""

    config_path: str
    currency: str = "INR"


class Settings:
    """
    Container for lazily loaded configuration sections.

    Values are resolved on-demand to avoid requiring unrelated environment
    variables for modules that do not use them.
    """

    def __init__(self):
        self._llm: Optional[LLMConfig] = None
        self._agent: Optional[AgentConfig] = None
        self._custom: Optional[CustomConfig] = None

    @property
    def llm(self) -> LLMConfig:
        """Get LLM configuration."""
        if self._llm is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY environment variable is required")

            try:
                temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
            except ValueError:
                temperature = 0.7
            self._llm = LLMConfig(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                temperature=max(0.0, min(2.0, temperature)),
                api_key=api_key,
            )
        return self._llm

    @property
    def agent(self) -> AgentConfig:
        """Get agent configuration."""
        if self._agent is None:
            self._agent = AgentConfig(
                name=os.getenv("AGENT_NAME", "Custom Agent"),
                entity_id=os.getenv("AGENT_ENTITY_ID", "agent.custom.default"),
                version=os.getenv("AGENT_VERSION", "1.0.0"),
            )
        return self._agent

    @property
    def custom(self) -> CustomConfig:
        """Get custom REST API configuration."""
        if self._custom is None:
            config_path = os.getenv("CUSTOM_CONFIG_PATH")
            if not config_path:
                # Default to configs/custom.yaml relative to project root
                config_path = str(Path(__file__).parent.parent / "configs" / "custom.yaml")

            self._custom = CustomConfig(
                config_path=config_path,
                currency=os.getenv("CUSTOM_CURRENCY", "INR"),
            )
        return self._custom


# Singleton instance
_SETTINGS = Settings()


def get_settings() -> Settings:
    """Expose shared singleton settings instance."""
    return _SETTINGS


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _SETTINGS
    _SETTINGS = Settings()


__all__ = [
    "LLMConfig",
    "AgentConfig",
    "CustomConfig",
    "Settings",
    "get_settings",
    "reset_settings",
]
