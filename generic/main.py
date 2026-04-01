"""
Generic Agent - Main Application Entry Point.
REST API server with /uc-agent endpoint.
Dynamically loads domain config via DOMAIN_CONFIG env var.
"""
import importlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.generic_agent import GenericReActAgent
from app.api.routes import router, set_agent as set_routes_agent
from app.engine.talk import set_agent as set_talk_agent
from app.core.database import get_mongodb
from config import initialize_environment, get_settings, LoggingConfig

logging.basicConfig(level=LoggingConfig.LEVEL, format=LoggingConfig.FORMAT)
logger = logging.getLogger(__name__)

# Suppress noisy library logs
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

initialize_environment()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("Starting Generic Agent...")

    try:
        # Connect to MongoDB
        mongodb = get_mongodb()
        await mongodb.connect()
        logger.info("MongoDB connected")

        # Pre-load vector store (embedding model) at startup
        from app.core.vector_store import get_vector_store
        logger.info("Loading vector store and embedding model...")
        vector_store = get_vector_store()
        logger.info(f"Vector store ready with {len(vector_store.get_all_services())} services indexed")

        # Dynamically load domain config (whitelist allowed domains)
        domain_name = settings.generic.domain_config
        ALLOWED_DOMAINS = {"urban_company", "swiggy", "myntra"}
        if domain_name not in ALLOWED_DOMAINS:
            raise ValueError(f"Unknown domain: {domain_name}. Allowed: {ALLOWED_DOMAINS}")
        logger.info(f"Loading domain config: {domain_name}")
        config_module = importlib.import_module(f"app.domains.{domain_name}.config")
        domain_config = config_module.config

        # Initialize agent with domain config
        agent = GenericReActAgent(domain_config)
        set_routes_agent(agent)
        set_talk_agent(agent)
        logger.info(f"Agent initialized for domain={domain_name}, entity_id={settings.agent.entity_id}")

    except Exception as error:
        logger.error(f"Application initialization failed: {error}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Generic Agent...")
    await mongodb.disconnect()


application = FastAPI(
    title=settings.server.title,
    version=settings.server.version,
    lifespan=lifespan
)

_ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]

application.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=bool(os.getenv("CORS_ORIGINS")),  # only with explicit origins
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include REST API routes
application.include_router(router)


@application.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.agent.name,
        "version": settings.server.version,
        "protocol": "DOST Event Specification v00.01.01",
        "entity_id": settings.agent.entity_id,
        "domain": settings.generic.domain_config,
        "endpoints": {
            "uc-agent": "POST /uc-agent - DOST-compliant chat (dostEvent in/out)"
        }
    }


@application.get("/health")
async def health_check():
    """Health check endpoint."""
    mongodb = get_mongodb()
    try:
        await mongodb.db.command('ping')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "version": settings.server.version,
        "domain": settings.generic.domain_config,
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.agent.name} at http://localhost:{settings.server.port}")
    logger.info(f"POST /uc-agent - DOST-compliant chat (dostEvent in/out)")

    uvicorn.run(
        "main:application",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
        log_level="info"
    )
