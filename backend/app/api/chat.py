import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.db.mongodb import get_db
from app.models.schemas import QueryRequest, QueryResponse, ChatSession, ChatMessage, Citation
from app.rag.workflow import run_crag

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id: str = current_user["_id"]

    # ── Resolve or create chat session ───────────────────────────────────────
    session_id = payload.session_id
    if session_id:
        session = await db["sessions"].find_one(
            {"_id": session_id, "user_id": user_id}
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session_id = str(uuid.uuid4())
        session_doc = {
            "_id": session_id,
            "user_id": user_id,
            "title": payload.query[:60],
            "created_at": datetime.utcnow(),
        }
        await db["sessions"].insert_one(session_doc)

    # ── Log user message ─────────────────────────────────────────────────────
    await db["messages"].insert_one({
        "_id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": payload.query,
        "citations": [],
        "created_at": datetime.utcnow(),
    })

    # ── Run CRAG (now passes user_id for per-user Qdrant filtering) ──────────
    result = await run_crag(payload.query, user_id=user_id)

    answer = result["answer"]
    citations: list[Citation] = result["citations"]
    logs: list[str] = result["agent_logs"]

    # ── Format answer with source block ──────────────────────────────────────
    if citations:
        sources_block = "\n\nSources:\n" + "\n".join(
            f"- {c.filename} | Page: {c.page_number or 'N/A'} | Chunk: {c.chunk_id}"
            for c in citations
        )
        formatted_answer = f"Answer: {answer}{sources_block}"
    else:
        formatted_answer = f"Answer: {answer}"

    # ── Log assistant message ─────────────────────────────────────────────────
    await db["messages"].insert_one({
        "_id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "assistant",
        "content": formatted_answer,
        "citations": [c.model_dump() for c in citations],
        "created_at": datetime.utcnow(),
    })

    # ── Log interaction trace ────────────────────────────────────────────────
    await db["traces"].insert_one({
        "_id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_id": user_id,
        "query": payload.query,
        "agent_logs": logs,
        "citation_count": len(citations),
        "created_at": datetime.utcnow(),
    })

    return QueryResponse(
        session_id=session_id,
        answer=formatted_answer,
        citations=citations,
        agent_trace=logs,
    )


@router.get("/sessions", response_model=list[dict])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db["sessions"].find({"user_id": current_user["_id"]}).sort("created_at", -1)
    sessions = await cursor.to_list(length=100)
    return [{"id": s["_id"], "title": s["title"], "created_at": s["created_at"]} for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[dict])
async def get_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    session = await db["sessions"].find_one(
        {"_id": session_id, "user_id": current_user["_id"]}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cursor = db["messages"].find({"session_id": session_id}).sort("created_at", 1)
    msgs = await cursor.to_list(length=500)
    return [
        {
            "id": m["_id"],
            "role": m["role"],
            "content": m["content"],
            "citations": m.get("citations", []),
            "created_at": m["created_at"],
        }
        for m in msgs
    ]