import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)
_client: AsyncIOMotorClient = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    await _ensure_indexes()
    logger.info("MongoDB connected and indexes ensured.")


async def _ensure_indexes() -> None:
    db = _client[settings.MONGODB_DB]
    # users
    await db["users"].create_index("email", unique=True)
    # documents
    await db["documents"].create_index("uploaded_by")
    await db["documents"].create_index("status")
    # chunks
    await db["chunks"].create_index("document_id")
    # sessions
    await db["sessions"].create_index("user_id")
    await db["sessions"].create_index([("created_at", -1)])
    # messages
    await db["messages"].create_index("session_id")
    await db["messages"].create_index([("session_id", 1), ("created_at", 1)])
    # traces
    await db["traces"].create_index("user_id")
    await db["traces"].create_index("session_id")


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    return _client[settings.MONGODB_DB]