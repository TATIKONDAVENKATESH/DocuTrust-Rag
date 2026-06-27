import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.security import decode_token
from app.rag.workflow import run_crag

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001)
        return

    user_id: str = payload.get("sub", "")
    await websocket.accept()
    logger.info(f"WebSocket connected for user {user_id}")

    try:
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

            await websocket.send_text(json.dumps({"type": "start", "query": query}))

            async def log_callback(log_line: str) -> None:
                try:
                    await websocket.send_text(json.dumps({"type": "log", "message": log_line}))
                except Exception:
                    pass

            try:
                # Pass user_id so Qdrant filters to this user's documents only
                result = await run_crag(query, user_id=user_id, log_callback=log_callback)
            except Exception as exc:
                logger.exception(f"CRAG error: {exc}")
                await websocket.send_text(
                    json.dumps({"type": "error", "message": f"Agent error: {str(exc)}"})
                )
                continue

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