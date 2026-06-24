from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.config import settings

_client: AsyncQdrantClient = None


async def connect_qdrant() -> None:
    global _client
    _client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    await _ensure_collection()


async def _ensure_collection() -> None:
    exists = await _client.collection_exists(settings.QDRANT_COLLECTION)
    if not exists:
        await _client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


async def close_qdrant() -> None:
    global _client
    if _client:
        await _client.close()


def get_qdrant() -> AsyncQdrantClient:
    return _client
