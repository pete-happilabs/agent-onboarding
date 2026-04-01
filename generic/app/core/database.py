"""
MongoDB connection manager for Urban Bot.
Uses motor for async MongoDB operations.
"""
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING

from config import get_settings

logger = logging.getLogger(__name__)


class MongoDB:
    """Singleton MongoDB connection manager."""
    
    _instance: Optional['MongoDB'] = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self) -> None:
        """Initialize MongoDB connection and create indexes."""
        if self._client is not None:
            return
        
        try:
            self._client = AsyncIOMotorClient(get_settings().mongodb.uri)
            self._db = self._client[get_settings().mongodb.database_name]
            
            # Verify connection
            await self._client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {get_settings().mongodb.database_name}")
            
            # Create indexes for performance
            await self._create_indexes()
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
    
    async def _create_indexes(self) -> None:
        """Create indexes for fast lookups."""
        # Sessions collection indexes
        sessions = self._db[get_settings().mongodb.sessions_collection]
        await sessions.create_indexes([
            IndexModel([("session_id", ASCENDING)], unique=True)
        ])
        
        # Bookings collection indexes
        bookings = self._db[get_settings().mongodb.bookings_collection]
        await bookings.create_indexes([
            IndexModel([("session_id", ASCENDING)]),
            IndexModel([("booking_id", ASCENDING)], unique=True)
        ])
        
        # Services collection indexes
        services = self._db[get_settings().mongodb.services_collection]
        await services.create_indexes([
            IndexModel([("service_id", ASCENDING)], unique=True),
            IndexModel([("category.name", ASCENDING)])
        ])
        
        logger.info("MongoDB indexes created")
    
    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB disconnected")
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self._db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self._db
    
    @property
    def sessions(self):
        """Get sessions collection."""
        return self.db[get_settings().mongodb.sessions_collection]
    
    @property
    def bookings(self):
        """Get bookings collection."""
        return self.db[get_settings().mongodb.bookings_collection]
    
    @property
    def services(self):
        """Get services collection."""
        return self.db[get_settings().mongodb.services_collection]


# Global instance
_mongodb: Optional[MongoDB] = None


def get_mongodb() -> MongoDB:
    """Get the singleton MongoDB instance."""
    global _mongodb
    if _mongodb is None:
        _mongodb = MongoDB()
    return _mongodb
