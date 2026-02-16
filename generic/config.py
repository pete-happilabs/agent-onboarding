"""
Configuration classes for UrbanBot AI Agent.
"""
import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


class ApplicationConfig:
    """OpenAI and runtime configuration."""
    OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY")
    TOKENIZERS_PARALLELISM: Final[str] = "false"


class LLMConfig:
    """LLM model configuration."""
    MODEL_NAME: Final[str] = "gpt-4o-mini"
    TEMPERATURE: Final[float] = 0.1
    MAX_TOKENS: Final[int] = 1000
    TIMEOUT: Final[int] = 30


class FilePathConfig:
    """File path configuration."""
    SERVICE_DATA_FILE: Final[str] = "data/service.json"
    VECTOR_STORE_DIR: Final[str] = "data/vector_store"


class ServerConfig:
    """Server configuration."""
    HOST: Final[str] = "0.0.0.0"
    PORT: Final[int] = 8000
    TITLE: Final[str] = "UrbanBot AI Agent"
    VERSION: Final[str] = "2.0.0"


class LoggingConfig:
    """Logging configuration."""
    FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LEVEL: Final[str] = "DEBUG"


class MongoDBConfig:
    """MongoDB configuration."""
    URI: Final[str] = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME: Final[str] = os.getenv("MONGODB_DATABASE", "urban_bot_db")
    SERVICES_COLLECTION: Final[str] = "services"
    BOOKINGS_COLLECTION: Final[str] = "bookings"
    SESSIONS_COLLECTION: Final[str] = "sessions"


def initialize_environment() -> None:
    """Initialize environment variables."""
    os.environ["OPENAI_API_KEY"] = ApplicationConfig.OPENAI_API_KEY or ""
    os.environ["TOKENIZERS_PARALLELISM"] = ApplicationConfig.TOKENIZERS_PARALLELISM
