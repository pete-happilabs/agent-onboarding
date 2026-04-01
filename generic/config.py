"""
Configuration for Generic Agent — environment-based Settings.

Mirrors the Custom template's lazy-loaded pattern so the generic agent
can be reused across domains by changing .env only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from dotenv import load_dotenv

# Load .env from app directory (same location as Custom template)
_ENV_PATH = Path(__file__).parent / "app" / ".env"
load_dotenv(_ENV_PATH)
# Also try root-level .env as fallback
load_dotenv(Path(__file__).parent / ".env")


@dataclass(frozen=True)
class LLMConfig:
    """LLM model configuration."""
    model: str
    temperature: float
    max_tokens: int
    timeout: int
    api_key: str


@dataclass(frozen=True)
class AgentConfig:
    """Agent identity configuration."""
    entity_id: str
    name: str
    version: str = "2.0.0"


@dataclass(frozen=True)
class ServerConfig:
    """Server configuration."""
    host: str
    port: int
    title: str
    version: str


@dataclass(frozen=True)
class MongoDBConfig:
    """MongoDB configuration."""
    uri: str
    database_name: str
    services_collection: str = "services"
    bookings_collection: str = "bookings"
    sessions_collection: str = "sessions"


@dataclass(frozen=True)
class GenericConfig:
    """Generic agent-specific configuration."""
    domain_config: str
    currency: str = "INR"


@dataclass(frozen=True)
class FilePathConfig:
    """File path configuration."""
    service_data_file: str
    vector_store_dir: str


class LoggingConfig:
    """Logging configuration (kept as class constants for simplicity)."""
    FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LEVEL: Final[str] = os.getenv("LOG_LEVEL", "DEBUG")


class Settings:
    """
    Container for lazily loaded configuration sections.

    Values are resolved on-demand from environment variables.
    """

    def __init__(self):
        self._llm: Optional[LLMConfig] = None
        self._agent: Optional[AgentConfig] = None
        self._server: Optional[ServerConfig] = None
        self._mongodb: Optional[MongoDBConfig] = None
        self._generic: Optional[GenericConfig] = None
        self._file_paths: Optional[FilePathConfig] = None

    @property
    def llm(self) -> LLMConfig:
        if self._llm is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY environment variable is required")
            self._llm = LLMConfig(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
                timeout=int(os.getenv("LLM_TIMEOUT", "30")),
                api_key=api_key,
            )
        return self._llm

    @property
    def agent(self) -> AgentConfig:
        if self._agent is None:
            self._agent = AgentConfig(
                entity_id=os.getenv("AGENT_ENTITY_ID", "com.urban.company"),
                name=os.getenv("AGENT_NAME", "UrbanBot"),
                version=os.getenv("AGENT_VERSION", "2.0.0"),
            )
        return self._agent

    @property
    def server(self) -> ServerConfig:
        if self._server is None:
            self._server = ServerConfig(
                host=os.getenv("SERVER_HOST", "127.0.0.1"),
                port=int(os.getenv("SERVER_PORT", "8000")),
                title=os.getenv("SERVER_TITLE", "Generic Agent"),
                version=os.getenv("SERVER_VERSION", "2.0.0"),
            )
        return self._server

    @property
    def mongodb(self) -> MongoDBConfig:
        if self._mongodb is None:
            self._mongodb = MongoDBConfig(
                uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
                database_name=os.getenv("MONGODB_DATABASE", "urban_bot_db"),
            )
        return self._mongodb

    @property
    def generic(self) -> GenericConfig:
        if self._generic is None:
            self._generic = GenericConfig(
                domain_config=os.getenv("DOMAIN_CONFIG", "urban_company"),
                currency=os.getenv("CURRENCY", "INR"),
            )
        return self._generic

    @property
    def file_paths(self) -> FilePathConfig:
        if self._file_paths is None:
            self._file_paths = FilePathConfig(
                service_data_file=os.getenv("SERVICE_DATA_FILE", "data/service.json"),
                vector_store_dir=os.getenv("VECTOR_STORE_DIR", "data/vector_store"),
            )
        return self._file_paths


# Singleton instance
_SETTINGS = Settings()


def get_settings() -> Settings:
    """Expose shared singleton settings instance."""
    return _SETTINGS


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _SETTINGS
    _SETTINGS = Settings()


def initialize_environment() -> None:
    """Initialize environment variables."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
