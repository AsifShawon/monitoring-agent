"""MongoDB database connection and utilities.

Simple single database with three collections:
- users: for authentication and preferences
- targets: configuration per monitored source (with user_id reference)
- changes: detected differences with timestamps (with target_id reference)
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class Database:
    """MongoDB database manager."""
    
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB."""
        try:
            logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")
            cls.client = AsyncIOMotorClient(settings.mongodb_url)
            cls.db = cls.client[settings.mongodb_db_name]
            
            # Test connection
            await cls.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            await cls.create_indexes()
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    async def create_indexes(cls):
        """Create indexes for all collections."""
        try:
            # Users collection indexes
            await cls.db.users.create_index("email", unique=True)
            
            # Targets collection indexes
            await cls.db.targets.create_index("url", unique=True)
            await cls.db.targets.create_index("user_id")
            await cls.db.targets.create_index("last_checked")
            await cls.db.targets.create_index("type")
            await cls.db.targets.create_index("is_active")
            await cls.db.targets.create_index([("user_id", 1), ("is_active", 1)])
            
            # Changes collection indexes
            await cls.db.changes.create_index("target_id")
            await cls.db.changes.create_index("timestamp")
            await cls.db.changes.create_index("severity")
            await cls.db.changes.create_index([("timestamp", -1)])
            await cls.db.changes.create_index([("target_id", 1), ("timestamp", -1)])

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if cls.db is None:
            raise RuntimeError("Database not initialized. Call connect_db() first.")
        return cls.db
    
    @classmethod
    def get_sync_db(cls):
        """Get synchronous database instance for Celery tasks.
        
        This creates a new synchronous client independent of the async client.
        """
        from pymongo import MongoClient
        sync_client = MongoClient(settings.mongodb_url)
        return sync_client[settings.mongodb_db_name]


async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get database."""
    return Database.get_db()
