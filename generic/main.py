"""
UrbanBot AI Agent - Main Application Entry Point.
REST API server with /talk and /help endpoints.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.urban_agent import UrbanBotAgent
from app.api.routes import router, set_agent
from app.core.database import get_mongodb
from config import initialize_environment, ServerConfig, LoggingConfig

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("Starting UrbanBot AI Agent...")
    
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
        
        # Initialize agent
        agent = UrbanBotAgent()
        set_agent(agent)
        logger.info("Agent initialized and registered with routes")
        
    except Exception as error:
        logger.error(f"Application initialization failed: {error}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down UrbanBot AI Agent...")
    await mongodb.disconnect()


application = FastAPI(
    title=ServerConfig.TITLE,
    version=ServerConfig.VERSION,
    lifespan=lifespan
)

application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include REST API routes
application.include_router(router)


@application.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Urban Company Agent",
        "version": ServerConfig.VERSION,
        "protocol": "DOST Event Specification v00.01.01",
        "entity_id": "com.urban.company",
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
        "version": ServerConfig.VERSION
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Urban Company Agent at http://localhost:{ServerConfig.PORT}")
    logger.info(f"POST /uc-agent - DOST-compliant chat (dostEvent in/out)")
    
    uvicorn.run(
        "main:application",
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        reload=False,
        log_level="info"
    )
