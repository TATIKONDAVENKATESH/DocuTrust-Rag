import uuid
import asyncio
import logging
from typing import List
from datetime import datetime

from app.core.config import settings
from app.db.mongodb import get_db
from app.db.qdrant import get_qdrant
from app.models.schemas import DocumentChunk
from app.services.parser import extract_text_with_pages, chunk_text
from app.services.embedding import embed_texts
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)


async def ingest_document(
    document_id: str,
    filename: str,
    file_path: str,
    file_type: str,
    user_id: str,
) -> int:
    """
    Full ingestion pipeline:
    1. Extract text with page numbers
    2. Chunk text
    3. Embed chunks
    4. Store in Qdrant (chunk_id UUID in id field, also in payload for citation lookups)
    5. Store chunk metadata in MongoDB
    Returns total number of chunks stored.
    """
    db = get_db()
    qdrant = get_qdrant()

    try:
        # 1 & 2: Extract + chunk
        pages = extract_text_with_pages(file_path, file_type)
        all_chunks: List[DocumentChunk] = []
        chunk_index = 0
        for page_text, page_number in pages:
            raw_chunks = chunk_text(page_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            for raw in raw_chunks:
                if not raw.strip():
                    continue
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=document_id,
                        filename=filename,
                        text=raw,
                        page_number=page_number,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

        if not all_chunks:
            await db["documents"].update_one(
                {"_id": document_id},
                {"$set": {"status": "error", "chunk_count": 0, "error": "No text extracted"}},
            )
            return 0

        # 3: Embed (run in thread pool — sentence-transformers is sync)
        texts = [c.text for c in all_chunks]
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, embed_texts, texts)

        # 4: Upsert to Qdrant
        # IMPORTANT: qdrant-client 1.9.x requires id to be int or uuid.UUID (not str)
        points = [
            PointStruct(
                id=uuid.UUID(chunk.chunk_id),   # ← must be uuid.UUID, not raw string
                vector=embeddings[i],
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "filename": chunk.filename,
                    "text": chunk.text,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                },
            )
            for i, chunk in enumerate(all_chunks)
        ]

        # Upsert in batches of 256 to avoid request size limits
        batch_size = 256
        for i in range(0, len(points), batch_size):
            await qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points[i : i + batch_size],
            )

        # 5: Persist chunk metadata in MongoDB
        chunk_docs = [
            {
                "_id": c.chunk_id,
                "document_id": c.document_id,
                "filename": c.filename,
                "text": c.text,
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
            }
            for c in all_chunks
        ]
        await db["chunks"].insert_many(chunk_docs, ordered=False)

        # Update document status
        await db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": "ready", "chunk_count": len(all_chunks)}},
        )

        logger.info(f"Ingested {len(all_chunks)} chunks for document {document_id}")
        return len(all_chunks)

    except Exception as exc:
        logger.exception(f"Ingestion failed for document {document_id}: {exc}")
        await db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": "error", "error": str(exc)}},
        )
        return 0