"""
MongoDB Connection

Async MongoDB client using motor.
"""

import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

# Global client instance
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


def get_mongo_url() -> str:
    """Get MongoDB connection URL from environment."""
    return os.getenv("MONGO_URL", "mongodb://localhost:27017")


def get_database_name() -> str:
    """Get database name from environment."""
    return os.getenv("MONGO_DB_NAME", "research_assistant")


async def connect_mongodb() -> AsyncIOMotorDatabase:
    """Connect to MongoDB and return database instance."""
    global _client, _database
    
    if _database is not None:
        return _database
    
    mongo_url = get_mongo_url()
    db_name = get_database_name()
    
    logger.info(f"Connecting to MongoDB: {mongo_url}")
    _client = AsyncIOMotorClient(mongo_url)
    _database = _client[db_name]
    
    # Test connection
    await _client.admin.command('ping')
    logger.info(f"Connected to MongoDB database: {db_name}")
    
    return _database


async def close_mongodb():
    """Close MongoDB connection."""
    global _client, _database
    
    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get current database instance (must be connected first)."""
    if _database is None:
        raise RuntimeError("MongoDB not connected. Call connect_mongodb() first.")
    return _database


# Collection names
PAPERS_COLLECTION = "papers"
CLUSTERS_COLLECTION = "clusters"
REPORTS_COLLECTION = "reports"
PLANS_COLLECTION = "plans"
