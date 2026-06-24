import uuid
import os
import asyncio
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
import aiofiles

from app.api.auth import get_current_user
from app.core.config import settings
from app.db.mongodb import get_db
from app.models.schemas import DocumentOut
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}


def _get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ext = _get_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    document_id = str(uuid.uuid4())
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")

    async with aiofiles.open(save_path, "wb") as out_file:
        await out_file.write(content)

    db = get_db()
    now = datetime.utcnow()
    doc = {
        "_id": document_id,
        "filename": file.filename,
        "file_type": ext,
        "size_bytes": len(content),
        "chunk_count": 0,
        "uploaded_by": current_user["_id"],
        "uploaded_at": now,
        "status": "processing",
        "file_path": save_path,
    }
    await db["documents"].insert_one(doc)

    background_tasks.add_task(
        ingest_document,
        document_id,
        file.filename,
        save_path,
        ext,
        current_user["_id"],
    )

    return DocumentOut(
        id=document_id,
        filename=file.filename or "",
        file_type=ext,
        size_bytes=len(content),
        chunk_count=0,
        uploaded_at=now,
        status="processing",
    )


@router.get("/", response_model=list[DocumentOut])
async def list_documents(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db["documents"].find({"uploaded_by": current_user["_id"]}).sort("uploaded_at", -1)
    docs = await cursor.to_list(length=200)
    return [
        DocumentOut(
            id=d["_id"],
            filename=d["filename"],
            file_type=d["file_type"],
            size_bytes=d["size_bytes"],
            chunk_count=d.get("chunk_count", 0),
            uploaded_at=d["uploaded_at"],
            status=d.get("status", "processing"),
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    d = await db["documents"].find_one({"_id": document_id, "uploaded_by": current_user["_id"]})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut(
        id=d["_id"],
        filename=d["filename"],
        file_type=d["file_type"],
        size_bytes=d["size_bytes"],
        chunk_count=d.get("chunk_count", 0),
        uploaded_at=d["uploaded_at"],
        status=d.get("status", "processing"),
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    doc = await db["documents"].find_one(
        {"_id": document_id, "uploaded_by": current_user["_id"]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove matching vectors from Qdrant using the correct 1.9.x API
    try:
        from app.db.qdrant import get_qdrant
        from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
        qdrant = get_qdrant()
        await qdrant.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                )
            ),
        )
    except Exception as exc:
        # Non-fatal — Qdrant entry may not exist if ingestion failed
        import logging
        logging.getLogger(__name__).warning(f"Qdrant delete failed (non-fatal): {exc}")

    # Remove chunks and document from MongoDB
    await db["chunks"].delete_many({"document_id": document_id})
    await db["documents"].delete_one({"_id": document_id})

    # Remove file from disk
    file_path = doc.get("file_path", "")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)