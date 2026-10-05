import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.db.mongodb import get_db
from app.rag.workflow import run_crag

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        # [NOTE] Wait for an initial auth frame instead of putting the token in the URL query string
        # This prevents reverse proxies (like Nginx) from logging the JWT token in plaintext
        auth_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_data = json.loads(auth_raw)
        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await websocket.close(code=4001)
            return

        payload = decode_token(auth_data["token"])
        if not payload:
            await websocket.close(code=4001)
            return
        
        user_id: str = payload.get("sub", "")
        logger.info(f"WebSocket connected for user {user_id}")
        
        db = get_db()

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=300)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            query = data.get("query", "").strip()
            if not query:
                await websocket.send_text(json.dumps({"type": "error", "message": "Empty query"}))
                continue

            session_id = data.get("session_id")
            
            chat_history = []
            # [NOTE] Fetch previous chat messages if session exists.
            # This enables conversational memory (so the LLM can understand follow-up questions).
            if session_id:
                session = await db["sessions"].find_one({"_id": session_id, "user_id": user_id})
                if not session:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Session not found"}))
                    continue
                cursor = db["messages"].find({"session_id": session_id}).sort("created_at", 1)
                msgs = await cursor.to_list(length=100)
                chat_history = [{"role": m["role"], "content": m["content"]} for m in msgs]
            else:
                session_id = str(uuid.uuid4())
                session_doc = {
                    "_id": session_id,
                    "user_id": user_id,
                    "title": query[:60],
                    "created_at": datetime.now(timezone.utc),
                }
                await db["sessions"].insert_one(session_doc)

            # Log user message
            await db["messages"].insert_one({
                "_id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "user",
                "content": query,
                "citations": [],
                "created_at": datetime.now(timezone.utc),
            })

            await websocket.send_text(json.dumps({"type": "start", "query": query, "session_id": session_id}))

            async def log_callback(log_line: str) -> None:
                try:
                    await websocket.send_text(json.dumps({"type": "log", "message": log_line}))
                except Exception:
                    pass

            try:
                # Pass user_id and chat_history
                result = await run_crag(query, user_id=user_id, log_callback=log_callback, chat_history=chat_history)
            except Exception as exc:
                logger.exception(f"CRAG error: {exc}")
                await websocket.send_text(
                    json.dumps({"type": "error", "message": f"Agent error: {str(exc)}"})
                )
                continue

            answer = result["answer"]
            citations = result["citations"]
            
            # Format answer with citations for DB
            if citations:
                sources_block = "\n\nSources:\n" + "\n".join(
                    f"- {c.filename} | Page: {c.page_number or 'N/A'} | Chunk: {c.chunk_id}"
                    for c in citations
                )
                formatted_answer = f"Answer: {answer}{sources_block}"
            else:
                formatted_answer = f"Answer: {answer}"

            # Log assistant message
            await db["messages"].insert_one({
                "_id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "assistant",
                "content": formatted_answer,
                "citations": [c.model_dump() for c in citations],
                "created_at": datetime.now(timezone.utc),
            })

            # Log trace
            await db["traces"].insert_one({
                "_id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "agent_logs": result["agent_logs"],
                "citation_count": len(citations),
                "created_at": datetime.now(timezone.utc),
            })

            await websocket.send_text(
                json.dumps({
                    "type": "result",
                    "answer": result["answer"],
                    "citations": [c.model_dump() for c in result["citations"]],
                    "agent_logs": result["agent_logs"],
                    "confidence": result.get("confidence", 0.0),
                    "used_web_fallback": result.get("used_web_fallback", False),
                    "retrieved_chunks": result.get("retrieved_chunks", []),
                })
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as exc:
        logger.exception(f"WebSocket error: {exc}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass